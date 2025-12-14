from typing import Literal, Optional
import datetime as dt
import logging

from myapi.domain.ai.ai_schema import ChatModel
from myapi.services.translate_service import TranslateService
from myapi.utils.date_utils import validate_date
from fastapi import APIRouter, Depends

from myapi.utils.auth import verify_bearer_token
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import (
    MahaneyAnalysisRequest,
    MahaneyAnalysisGetRequest,
    MahaneyAnalysisGetResponse,
    WebSearchMarketResponse,
    ETFAnalysisRequest,
    ETFAnalysisGetRequest,
    ETFAnalysisGetResponse,
    ETFAnalystSummaryResponse,
    InsiderTrendGetRequest,
    InsiderTrendGetResponse,
    InsiderTrendResponse,
    AnalystPTGetRequest,
    AnalystPTGetResponse,
    AnalystPTResponse,
    ETFWeeklyFlowGetRequest,
    ETFWeeklyFlowGetResponse,
    ETFWeeklyFlowResponse,
    LiquidityWeeklyResponse,
    MarketBreadthResponse,
    FundamentalAnalysisGetResponse,
    FundamentalAnalysisResponse,
)
from myapi.domain.signal.signal_schema import WebSearchTickerResponse
from myapi.services.signal_service import SignalService
from myapi.services.ai_service import AIService
from myapi.services.web_search_service import WebSearchService

router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)


@router.get("/")
@inject
def get_news(
    ticker: Optional[str] = "",
    news_type: Literal["ticker", "market"] = "market",
    news_date: Optional[dt.date] = dt.date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    """Get news with proper database session management"""
    today_str = validate_date(news_date if news_date else dt.date.today())

    result = signal_service.get_web_search_summary(
        type=news_type,
        ticker=ticker,
        date=today_str,
    )
    return {"result": result}


@router.get("/recommendations")
@inject
def news_recommendations(
    recommendation: Literal["Buy", "Hold", "Sell"] = "Buy",
    limit: int = 5,
    request_date: Optional[dt.date] = dt.date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    valid_date = validate_date(
        request_date if request_date is not None else dt.date.today()
    )
    results = signal_service.get_ticker_news_by_recommendation(
        recommendation=recommendation,
        limit=limit,
        date=valid_date,
    )
    return {"results": results}


@router.get(
    "/summary",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def news_summary(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    translate_service: TranslateService = Depends(
        Provide[Container.services.translate_service]
    ),
):
    today_str = dt.date.today().strftime("%Y-%m-%d")
    prompt = signal_service.generate_us_market_prompt(today_str)

    result = ai_service.gemini_search_grounding(
        prompt=prompt,
        schema=WebSearchMarketResponse,
    )

    if isinstance(result, WebSearchMarketResponse):

        result = translate_service.translate_schema(result)

        signal_service.save_web_search_results(
            result_type="market",
            results=result.search_results,
        )

    return result


@router.get("/market-forecast")
@inject
async def market_forecast(
    forecast_date: dt.date = dt.date.today(),
    source: Literal["Major", "Minor"] = "Major",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    forecast_date = validate_date(forecast_date)

    return await websearch_service.get_market_forecast(forecast_date, source=source)


@router.post(
    "/market-forecast",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def create_market_forecast(
    forecast_date: dt.date = dt.date.today(),
    source: Literal["Major", "Minor"] = "Major",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    forecast_date = validate_date(forecast_date)

    return await websearch_service.create_market_forecast(forecast_date, source=source)


@router.get("/market-analysis")
@inject
def market_analysis(
    today: dt.date = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    today = validate_date(today)
    return websearch_service.get_market_analysis(today)


@router.post(
    "/market-analysis",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def create_market_analysis(
    today: dt.date = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    today = validate_date(today)
    return websearch_service.create_market_analysis(today)


@router.get("/tech-stock/analysis", response_model=MahaneyAnalysisGetResponse)
@inject
async def get_mahaney_analysis(
    target_date: Optional[dt.date] = dt.date.today(),
    tickers: Optional[str] = None,
    recommendation: Optional[Literal["Buy", "Sell", "Hold"]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[
        Literal["recommendation_score", "final_assessment", "stock_name"]
    ] = "stock_name",
    sort_order: Optional[Literal["asc", "desc"]] = "asc",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    Mahaney 분석 결과를 조회합니다.
    :param target_date: 조회할 날짜
    :param tickers: 필터할 티커 목록 (쉼표로 구분)
    :param recommendation: 추천 등급으로 필터
    :param limit: 결과 제한
    :param sort_by: 정렬 기준
    :param sort_order: 정렬 순서
    :return: Mahaney 분석 결과
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    # 쉼표로 구분된 티커 문자열을 리스트로 변환
    ticker_list = None
    if tickers:
        ticker_list = [ticker.strip().upper() for ticker in tickers.split(",")]

    request_params = MahaneyAnalysisGetRequest(
        target_date=target_date,
        tickers=ticker_list,
        recommendation=recommendation,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return await websearch_service.get_mahaney_analysis_with_filters(request_params)


@router.post(
    "/tech-stock/analysis",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def create_mahaney_analysis(
    request: MahaneyAnalysisRequest,
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    Mahaney 분석을 생성합니다.
    :param tickers: 분석할 티커 목록
    :return: Mahaney 분석 결과
    """
    tickers, target_date = request.tickers, request.target_date
    target_date = validate_date(target_date if target_date else dt.date.today())

    return await websearch_service.create_mahaney_analysis(tickers, target_date)


@router.get("/etf/portfolio", response_model=ETFAnalysisGetResponse)
@inject
async def get_etf_portfolio_analysis(
    target_date: Optional[dt.date] = dt.date.today(),
    etf_tickers: Optional[str] = None,
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    ETF 포트폴리오 변동 분석 결과를 조회합니다.
    :param target_date: 조회할 날짜
    :param etf_tickers: 필터할 ETF 티커 목록 (쉼표로 구분)
    :param limit: 결과 제한
    :param sort_by: 정렬 기준
    :param sort_order: 정렬 순서
    :return: ETF 포트폴리오 분석 결과
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    # 쉼표로 구분된 ETF 티커 문자열을 리스트로 변환
    etf_ticker_list = None
    if etf_tickers:
        etf_ticker_list = [ticker.strip().upper() for ticker in etf_tickers.split(",")]

    request_params = ETFAnalysisGetRequest(
        target_date=target_date,
        etf_tickers=etf_ticker_list,
    )

    return await websearch_service.get_etf_analysis_with_filters(request_params)


@router.post(
    "/etf/portfolio",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def create_etf_portfolio_analysis(
    request: ETFAnalysisRequest,
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    ETF 포트폴리오 변동 분석을 생성합니다.
    :param request: ETF 분석 요청 데이터
    :return: ETF 포트폴리오 분석 결과
    """
    etf_tickers, target_date = request.etf_tickers, request.target_date
    target_date = validate_date(target_date if target_date else dt.date.today())
    responses = []

    for ticker in etf_tickers:
        if not ticker:
            continue
        try:
            # ETF 분석 요청을 생성
            response = await websearch_service.create_etf_analysis(
                etf_tickers=[ticker.upper()], target_date=target_date
            )

            responses.append(response.etf_portfolios)
        except Exception as e:
            logger.error(f"Failed to create ETF analysis for {ticker}: {e}")
            responses.append({"ticker": ticker, "error": str(e)})

    return responses


@router.get("/insider-trend", response_model=InsiderTrendGetResponse)
@inject
async def get_insider_trend(
    target_date: Optional[dt.date] = dt.date.today(),
    tickers: Optional[str] = None,
    action: Optional[Literal["BUY", "SELL"]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[Literal["date", "value"]] = None,
    sort_order: Optional[Literal["asc", "desc"]] = "desc",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    ticker_list = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]

    req = InsiderTrendGetRequest(
        target_date=target_date,
        tickers=ticker_list,
        action=action,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return await websearch_service.get_insider_trend_with_filters(req)


@router.post(
    "/insider-trend",
    dependencies=[Depends(verify_bearer_token)],
    response_model=InsiderTrendResponse,
)
@inject
async def create_insider_trend(
    tickers: Optional[list[str]] = None,
    target_date: Optional[dt.date] = dt.date.today(),
    llm_policy: Literal[
        "AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"
    ] = "AUTO",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.create_insider_trend(
        tickers=tickers, target_date=target_date, llm_policy=llm_policy
    )


# Analyst Price Targets
@router.get("/analyst-price-targets", response_model=AnalystPTGetResponse)
@inject
async def get_analyst_price_targets(
    target_date: Optional[dt.date] = dt.date.today(),
    tickers: Optional[str] = None,
    action: Optional[Literal["UP", "DOWN", "INIT", "DROP"]] = None,
    limit: Optional[int] = None,
    sort_by: Optional[Literal["impact", "date"]] = None,
    sort_order: Optional[Literal["asc", "desc"]] = "desc",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    ticker_list = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]

    req = AnalystPTGetRequest(
        target_date=target_date,
        tickers=ticker_list,
        action=action,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return await websearch_service.get_analyst_price_targets_with_filters(req)


@router.post(
    "/analyst-price-targets",
    dependencies=[Depends(verify_bearer_token)],
    response_model=AnalystPTResponse,
)
@inject
async def create_analyst_price_targets(
    tickers: Optional[list[str]] = None,
    target_date: Optional[dt.date] = dt.date.today(),
    llm_policy: Literal[
        "AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"
    ] = "AUTO",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.create_analyst_price_targets(
        tickers=tickers, target_date=target_date, llm_policy=llm_policy
    )


# ETF Weekly Flows
@router.get("/etf/flows", response_model=ETFWeeklyFlowGetResponse)
@inject
async def get_etf_flows(
    target_date: Optional[dt.date] = dt.date.today(),
    provider: Optional[str] = None,
    sector_only: Optional[bool] = False,
    tickers: Optional[str] = None,
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    ticker_list = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]

    req = ETFWeeklyFlowGetRequest(
        target_date=target_date,
        provider=provider,
        sector_only=sector_only,
        tickers=ticker_list,
    )

    return await websearch_service.get_etf_weekly_flows_with_filters(req)


@router.post(
    "/etf/flows",
    dependencies=[Depends(verify_bearer_token)],
    response_model=ETFWeeklyFlowResponse,
)
@inject
async def create_etf_flows(
    universe: Optional[list[str]] = None,
    provider: Optional[str] = None,
    target_date: Optional[dt.date] = dt.date.today(),
    llm_policy: Literal[
        "AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"
    ] = "AUTO",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.create_etf_weekly_flows(
        universe=universe,
        target_date=target_date,
        provider=provider,
        llm_policy=llm_policy,
    )


# Liquidity Weekly
@router.get("/liquidity", response_model=LiquidityWeeklyResponse)
@inject
def get_liquidity(
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return websearch_service.get_liquidity_weekly(target_date)


@router.post(
    "/liquidity",
    dependencies=[Depends(verify_bearer_token)],
    response_model=LiquidityWeeklyResponse,
)
@inject
async def create_liquidity(
    target_date: Optional[dt.date] = dt.date.today(),
    llm_policy: Literal[
        "AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"
    ] = "AUTO",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.create_liquidity_weekly(target_date, llm_policy)


# Market Breadth Daily
@router.get("/market-breadth", response_model=MarketBreadthResponse)
@inject
def get_market_breadth_route(
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return websearch_service.get_market_breadth(target_date)


@router.post(
    "/market-breadth",
    dependencies=[Depends(verify_bearer_token)],
    response_model=MarketBreadthResponse,
)
@inject
async def create_market_breadth_route(
    target_date: Optional[dt.date] = dt.date.today(),
    llm_policy: Literal[
        "AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"
    ] = "AUTO",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.create_market_breadth_daily(target_date, llm_policy)


@router.post(
    "/etf/analyst-summary",
    dependencies=[Depends(verify_bearer_token)],
    response_model=ETFAnalystSummaryResponse,
)
@inject
async def create_etf_analyst_summary(
    etf_ticker: str,
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    특정 ETF의 포트폴리오 변동에 대한 애널리스트 수준의 상세 분석을 생성합니다.
    :param etf_ticker: 분석할 ETF 티커
    :param target_date: 분석 날짜
    :return: 애널리스트 분석 결과
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    # 먼저 해당 ETF의 포트폴리오 데이터를 가져옵니다
    etf_analyses = await websearch_service.get_etf_analysis(
        target_date=target_date, etf_tickers=[etf_ticker.upper()]
    )

    if not etf_analyses:
        return {
            "error": f"No ETF portfolio data found for {etf_ticker} on {target_date}. "
            f"Please create ETF analysis first using POST /news/etf/portfolio"
        }

    # 가장 최근의 ETF 데이터 사용
    etf_portfolio_data = etf_analyses[0].value

    # 애널리스트 요약 생성 (ETFAnalystSummaryResponse 직접 반환)
    analyst_summary = await websearch_service.create_etf_analyst_summary(
        etf_portfolio_data, target_date
    )

    return analyst_summary


@router.post(
    "/etf/signal-pipeline",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def create_etf_signal_pipeline(
    etf_ticker: str,
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
):
    """
    ETF 포트폴리오 변동 분석을 기반으로 해당 종목들의 시그널 분석을 수행합니다.
    1. ETF 포트폴리오 변동 데이터 수집
    2. 애널리스트 분석 수행
    3. 변동 종목들에 대한 차트/시그널 분석
    4. 통합 투자 인사이트 제공
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    try:
        # Step 1: ETF 포트폴리오 데이터 가져오기
        etf_analyses = await websearch_service.get_etf_analysis(
            target_date=target_date, etf_tickers=[etf_ticker.upper()]
        )

        if not etf_analyses:
            # ETF 분석이 없으면 생성
            await websearch_service.create_etf_analysis(
                [etf_ticker.upper()], target_date
            )
            etf_analyses = await websearch_service.get_etf_analysis(
                target_date=target_date, etf_tickers=[etf_ticker.upper()]
            )

        if not etf_analyses:
            return {
                "error": f"Failed to create or retrieve ETF analysis for {etf_ticker}"
            }

        etf_portfolio_data = etf_analyses[0].value

        # Step 2: 애널리스트 분석 수행
        analyst_summary = await websearch_service.create_etf_analyst_summary(
            etf_portfolio_data, target_date
        )

        # Step 3: 포트폴리오 변동 종목들 추출
        changed_tickers = []
        for change in etf_portfolio_data.changes:
            changed_tickers.append(change.ticker.upper())

        # Step 4: 각 종목에 대해 차트 분석 및 웹서치 수행
        ticker_signals = []
        for ticker in changed_tickers[:5]:  # 최대 5개 종목만 분석 (API 제한)
            try:
                # 웹서치를 통한 최신 뉴스/분석 수집
                today_str = target_date.strftime("%Y-%m-%d")
                web_search_result = ai_service.perplexity_completion(
                    prompt=signal_service.generate_web_search_prompt(ticker, today_str),
                    schema=WebSearchTickerResponse,
                )

                # ETF 변동 사유와 함께 종합 분석 프롬프트 생성
                etf_context = f"""
                ETF Context: {etf_portfolio_data.etf_name} ({etf_portfolio_data.etf_ticker}) recently {
                    next((change.action for change in etf_portfolio_data.changes if change.ticker == ticker), 'TRADED')
                } {ticker}.
                
                Portfolio Summary: {etf_portfolio_data.summary}
                
                Analyst Summary: {str(analyst_summary)[:500]}...
                """

                enhanced_prompt = f"""
                {etf_context}
                
                Based on this ETF portfolio change and the analyst summary above, 
                analyze {ticker} from both technical and fundamental perspectives.
                Consider why institutional ETF managers made this decision and what it signals for individual investors.
                
                Web Search Results: {web_search_result.model_dump_json() if web_search_result else 'No recent data'}
                
                Provide trading recommendations considering:
                1. ETF manager's rationale for this position change
                2. Technical chart patterns and momentum
                3. Fundamental outlook and recent news
                4. Risk/reward profile for retail investors
                """

                ticker_signals.append(
                    {
                        "ticker": ticker,
                        "etf_action": next(
                            (
                                change.action
                                for change in etf_portfolio_data.changes
                                if change.ticker == ticker
                            ),
                            "UNKNOWN",
                        ),
                        "web_search_data": (
                            web_search_result.model_dump()
                            if web_search_result
                            else None
                        ),
                        "enhanced_context": enhanced_prompt,
                        "analysis_status": "completed",
                    }
                )

            except Exception as e:
                logger.error(f"Error analyzing ticker {ticker}: {e}")
                ticker_signals.append(
                    {"ticker": ticker, "error": str(e), "analysis_status": "failed"}
                )

        # Step 5: 통합 결과 반환
        pipeline_result = {
            "etf_ticker": etf_ticker.upper(),
            "analysis_date": target_date,
            "etf_portfolio_data": etf_portfolio_data.model_dump(),
            "analyst_summary": analyst_summary,
            "analyzed_tickers": ticker_signals,
            "pipeline_status": "completed",
            "total_tickers_analyzed": len(ticker_signals),
            "successful_analyses": len(
                [t for t in ticker_signals if t.get("analysis_status") == "completed"]
            ),
        }

        # ai_analysis 테이블에 통합 결과 저장
        websearch_service.websearch_repository.create_analysis(
            analysis_date=target_date,
            analysis=pipeline_result,
            name="etf_signal_pipeline",
        )

        return pipeline_result

    except Exception as e:
        logger.error(f"Error in ETF signal pipeline for {etf_ticker}: {e}")
        return {
            "error": f"Pipeline failed: {str(e)}",
            "etf_ticker": etf_ticker.upper(),
            "analysis_date": target_date,
            "pipeline_status": "failed",
        }


# ---------------------- Fundamental Analysis ----------------------
@router.get("/fundamental-analysis", response_model=FundamentalAnalysisGetResponse)
@inject
async def get_fundamental_analysis(
    ticker: str,
    force_refresh: bool = False,
    analysis_request: bool = True,
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    티커에 대한 종합적인 펀더멘탈 분석을 조회합니다.

    **캐싱 로직**:
    - DB에 해당 티커 분석이 존재하지 않으면: 새로 분석 생성 후 응답
    - 티커 분석이 존재하면:
      - 30일 이내 데이터: 캐시된 분석 응답
      - 30일 이상 경과: 새로 분석 생성 후 응답
    - force_refresh=True: 캐시 무시하고 새로 분석 생성

    **분석 내용**:
    1. 네러티브 및 비전 분석 (검색 기반)
    2. 섹터 분석 및 현황 (검색 기반)
    3. 펀더멘탈 지표 (성장률, 수익성, 부채비율 등) (검색 기반)
    4. 경영진 분석 (CEO, 인사이더 거래 등) (검색 기반)
    5. AI 기반 투자 추천 (OpenAI)

    :param ticker: 분석할 티커 심볼
    :param force_refresh: 캐시 무시하고 새로 생성 여부
    :param analysis_request: True이면 분석을 수행하고 False이면 DB 캐시만 조회
    :param target_date: 분석 기준 날짜
    :return: 펀더멘탈 분석 결과 (캐시 메타데이터 포함)
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    return await websearch_service.get_fundamental_analysis(
        ticker=ticker.upper(),
        target_date=target_date,
        force_refresh=force_refresh,
        analysis_request=analysis_request,
    )


@router.post(
    "/fundamental-analysis",
    dependencies=[Depends(verify_bearer_token)],
    response_model=FundamentalAnalysisResponse,
)
@inject
async def create_fundamental_analysis(
    ticker: str,
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    """
    티커에 대한 펀더멘탈 분석을 강제로 새로 생성합니다.

    **이 엔드포인트는 인증이 필요합니다 (Bearer Token)**

    분석 내용:
    1. 네러티브 및 비전 분석
    2. 섹터 분석 및 현황
    3. 펀더멘탈 지표 (성장률, 수익성, 부채비율 등)
    4. 경영진 분석
    5. AI 기반 투자 추천

    :param ticker: 분석할 티커 심볼
    :param target_date: 분석 기준 날짜
    :return: 새로 생성된 펀더멘탈 분석 결과
    """
    target_date = validate_date(target_date if target_date else dt.date.today())

    return await websearch_service.create_fundamental_analysis(
        ticker=ticker.upper(),
        target_date=target_date,
    )
