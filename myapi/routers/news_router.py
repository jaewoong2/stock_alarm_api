from typing import Literal, Optional
import datetime as dt

from myapi.domain.signal.signal_schema import DefaultTickers
from myapi.utils.date_utils import validate_date
from fastapi import APIRouter, Depends

from myapi.utils.auth import verify_bearer_token
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import (
    MahaneyAnalysisRequest,
    MahaneyAnalysisResponse,
    WebSearchMarketResponse,
)
from myapi.services.signal_service import SignalService
from myapi.services.ai_service import AIService
from myapi.services.web_search_service import WebSearchService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/")
@inject
def get_news(
    ticker: Optional[str] = "",
    news_type: Literal["ticker", "market"] = "market",
    news_date: Optional[dt.date] = dt.date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
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
):
    today_str = dt.date.today().strftime("%Y-%m-%d")
    prompt = signal_service.generate_us_market_prompt(today_str)
    result = ai_service.gemini_search_grounding(
        prompt=prompt,
        schema=WebSearchMarketResponse,
    )

    if isinstance(result, WebSearchMarketResponse):
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


@router.get("/tech-stock/analysis")
@inject
async def get_mahaney_analysis(
    target_date: Optional[dt.date] = dt.date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    target_date = validate_date(target_date if target_date else dt.date.today())
    return await websearch_service.get_mahaney_analysis(target_date)


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
