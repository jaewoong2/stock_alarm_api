import datetime as dt
import json
import logging
from typing import List, Literal, Optional
from urllib import response
from fastapi import APIRouter, Depends

from myapi.services.translate_service import TranslateService
from myapi.utils.auth import verify_bearer_token
from datetime import timedelta

from myapi.utils.config import Settings
from myapi.utils.date_utils import validate_date, get_latest_market_date

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.signal.signal_schema import (
    ChartPattern,
    DefaultStrategies,
    DefaultTickers,
    DiscordMessageRequest,
    GenerateSignalResultRequest,
    GetSignalByDateResponse,
    GetSignalByOnlyAIPromptSchema,
    GetSignalByOnlyAIRequest,
    GetSignalRequest,
    OptionsData,
    SignalBaseResponse,
    SignalPromptData,
    SignalPromptResponse,
    SignalRequest,
    TechnicalSignal,
    TickerReport,
    TrendContext,
    VixData,
    WebSearchTickerResponse,
)
from myapi.repositories.signals_repository import SignalsRepository
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.db_signal_service import DBSignalService
from myapi.services.discord_service import DiscordService
from myapi.services.signal_service import SignalService
from myapi.utils.utils import (
    export_slim_tail_csv,
)


router = APIRouter(
    prefix="/signals",
    tags=["signals"],
)

logger = logging.getLogger(__name__)


@router.post(
    "/investment-pdf",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def get_investment_pdf(
    ticker: str,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    """
    투자 PDF를 얻어오는 엔드포인트.
    """
    pdf_bytes, text_content = None, None
    try:
        pdf_bytes = signal_service.fetch_pdf_stock_investment(ticker=ticker.upper())

    except Exception as err:
        return None

    if pdf_bytes is not None:
        text_content = signal_service.extract_text_only(pdf_bytes)

    if text_content:
        return text_content

    return None


@router.post(
    "/generate-signal-reult",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def generate_signal_result(
    request: GenerateSignalResultRequest,
    signals_repository: SignalsRepository = Depends(
        Provide[Container.repositories.signals_repository]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    translate_service: TranslateService = Depends(
        Provide[Container.services.translate_service]
    ),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """
    result = None

    try:
        if request.ai == "GOOGLE":
            result = ai_service.gemini_completion(
                prompt=request.prompt
                + "\n\n If you are finished, please summarized the result.",
                schema=SignalPromptResponse,
            )

        if request.ai == "OPENAI":
            result = ai_service.completions_parse(
                system_prompt="",
                prompt=request.prompt,
                image_url=None,
                schema=SignalPromptResponse,
                chat_model=ChatModel.O4_MINI,
            )

        if not isinstance(result, SignalPromptResponse):
            return result

        try:
            result = translate_service.translate_schema(result)
        except Exception as e:
            logger.warning(f"Failed to translate signal result: {e}")

        signals_repository.create_signal(
            ticker=request.data.ticker,
            action=result.recommendation.lower(),
            entry_price=result.entry_price or 0.0,
            stop_loss=result.stop_loss_price,
            take_profit=result.take_profit_price,
            close_price=result.close_price,
            probability=str(result.probability_of_rising_up_percentage),
            strategy=",".join(request.data.triggered_strategies),
            result_description=result.reasoning,
            report_summary=request.summary,
            ai_model=request.ai,  # Store the AI model used for the signal
            senario=result.senarios,
            good_things=result.good_things,
            bad_things=result.bad_things,
            chart_pattern=ChartPattern(
                name=result.chart_pattern.name,
                description=result.chart_pattern.description,
                pattern_type=result.chart_pattern.pattern_type,
                confidence_level=result.chart_pattern.confidence_level,
            ),
        )

        return result

    except Exception as e:
        logger.error(f"Error generating signal result: {e}")
        return {"error": str(e)}


@router.post(
    "/llm-query",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def llm_query(
    req: SignalPromptData,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
    settings: Settings = Depends(Provide[Container.config.config]),
    translate_service: TranslateService = Depends(
        Provide[Container.services.translate_service]
    ),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """

    pdf_report, summary, web_search_gemini_result = None, None, None
    market_reference_date = get_latest_market_date()

    try:
        today_YYYY_MM_DD = market_reference_date.strftime("%Y-%m-%d")
        web_search_gemini_result = ai_service.perplexity_completion(
            prompt=signal_service.generate_web_search_prompt(
                req.ticker, today_YYYY_MM_DD
            ),
            schema=WebSearchTickerResponse,
            model=ChatModel.SONAR,
        )

        if not web_search_gemini_result:
            raise ValueError("Invalid response format from AI service for web search")

        if isinstance(web_search_gemini_result, WebSearchTickerResponse):
            logger.info(
                f"Web search results for {req.ticker} on {today_YYYY_MM_DD}: {web_search_gemini_result.search_results}"
            )

            result = translate_service.translate_schema(web_search_gemini_result)

            signal_service.save_web_search_results(
                result_type="ticker",
                results=result.search_results,
                ticker=req.ticker,
            )

        if req.additional_info and web_search_gemini_result:
            req.additional_info = (
                req.additional_info
                + "\n\n Web Search Results:\n"
                + web_search_gemini_result.model_dump_json()
            )
        else:
            if web_search_gemini_result:
                req.additional_info = (
                    "\n Web Search Result: "
                    + web_search_gemini_result.model_dump_json()
                    + "\n"
                )
    except Exception as e:
        logger.error(f"Error fetching web search results: {e}")
        web_search_gemini_result = None

    try:
        pdf_report = get_investment_pdf(ticker=req.ticker)
    except Exception as e:
        logger.error(f"Error fetching PDF report: {e}")

    if isinstance(pdf_report, str):
        report_system_prompt, report_prompt = signal_service.report_summary_prompt(
            ticker=req.ticker, report_text=pdf_report
        )

        summary = ai_service.completion(
            system_prompt=report_system_prompt,
            prompt=report_prompt,
            chat_model=ChatModel.GPT_4_1_MINI,
        )

    prompt = signal_service.generate_prompt(data=req, report_summary=summary)

    google_result, openai_result = None, None

    try:
        body = GenerateSignalResultRequest(
            data=req,
            summary=summary or "No summary available",
            prompt=prompt,
            ai="GOOGLE",  # Default to Google for the first request
        )
        google_result = aws_service.generate_queue_message_http(
            body=body.model_dump_json(),
            path="signals/generate-signal-reult",
            method="POST",
            query_string_parameters={},
            auth_token=settings.auth_token,  # Use auth token from settings
        )
        aws_service.send_sqs_fifo_message(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
            message_body=json.dumps(google_result),
            message_group_id="google",
            message_deduplication_id=req.ticker
            + "google"
            + market_reference_date.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error generating Google signal result: {e}")
        logger.error(f"Error Sending SQS message: {e}")
        google_result = None

    try:
        body = GenerateSignalResultRequest(
            data=req,
            summary=summary or "No summary available",
            prompt=prompt,
            ai="OPENAI",  # Default to OpenAI for the second request
        )
        openai_result = aws_service.generate_queue_message_http(
            body=body.model_dump_json(),
            path="signals/generate-signal-reult",
            method="POST",
            query_string_parameters={},
            auth_token=settings.auth_token,  # Use auth token from settings
        )
        aws_service.send_sqs_fifo_message(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
            message_body=json.dumps(openai_result),
            message_group_id="openai",
            message_deduplication_id=req.ticker
            + "openai"
            + market_reference_date.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error generating OpenAI signal result: {e}")
        openai_result = None

    return [google_result, openai_result]


@router.post(
    "/",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def get_signals(
    req: SignalRequest,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
    settings: Settings = Depends(Provide[Container.config.config]),
):
    START_DAYS_BACK: int = 400
    market_reference_date = get_latest_market_date()
    run_date = market_reference_date
    tickers = req.tickers or DefaultTickers
    strategies = DefaultStrategies

    start = run_date - timedelta(days=START_DAYS_BACK)

    spy_persentage_from_200ma = 0.0
    mkt_ok = False
    reports: list[TickerReport] = []

    spy_df = signal_service.fetch_ohlcv("SPY", start=start)

    # Fetch market-wide volatility and options data (once for all tickers)
    logger.info("Fetching VIX market volatility data...")
    vix_data = signal_service.fetch_market_volatility_data()

    logger.info("Fetching SPY options data...")
    spy_options = signal_service.fetch_index_options_data("SPY")

    logger.info("Fetching QQQ options data...")
    qqq_options = signal_service.fetch_index_options_data("QQQ")

    # Determine overall options sentiment
    options_sentiment = "neutral"
    if spy_options.get("put_call_ratio") and qqq_options.get("put_call_ratio"):
        avg_pc_ratio = (
            spy_options["put_call_ratio"] + qqq_options["put_call_ratio"]
        ) / 2
        if avg_pc_ratio > 1.2:
            options_sentiment = "bearish"
        elif avg_pc_ratio < 0.8:
            options_sentiment = "bullish"

    for t in tickers:
        df = signal_service.fetch_ohlcv(t, start=start)

        if df is None or df.empty:
            continue

        df = signal_service.add_indicators(df, spy_df)

        if t == "SPY":
            spy_persentage_from_200ma = (
                ((df["Close"].iloc[-1] - df["SMA200"].iloc[-1]) / df["SMA200"].iloc[-1])
                * 100
            ) or 0.0
            mkt_ok = spy_persentage_from_200ma > 0.0

        tech_sigs = [
            TechnicalSignal(
                strategy=signal.strategy,
                triggered=signal.triggered,
                details=signal.details,
                triggered_description=signal.description if signal.triggered else None,
            )
            for signal in signal_service.evaluate_signals(df, strategies)
        ]

        funda = signal_service.fetch_fundamentals(t) if req.with_fundamental else None

        reports.append(
            TickerReport(
                ticker=t,
                last_price=df["Close"].iloc[-1],
                price_change_pct=df["Close"].pct_change().iloc[-1],
                signals=tech_sigs,
                fundamentals=funda,
                news=None,
                dataframe=export_slim_tail_csv(df, 100),
            )
        )

    triggered_report = []

    # Filter triggered reports more efficiently
    triggered_tickers = set()
    triggered_report = []

    for report in reports:
        # Skip if already processed
        if report.ticker in triggered_tickers:
            continue

        # Check if any signal is triggered
        if any(signal.triggered for signal in report.signals):
            triggered_report.append(report)
            triggered_tickers.add(report.ticker)

    for report in triggered_report:
        triggered_strategies = [
            signal.strategy for signal in report.signals if signal.triggered
        ]

        technical_details = {
            signal.strategy: signal.details
            for signal in report.signals
            if signal.triggered
        }

        # Analyze trend context for this ticker
        ticker_df = signal_service.fetch_ohlcv(report.ticker, start=start)
        if ticker_df is not None and not ticker_df.empty:
            ticker_df = signal_service.add_indicators(ticker_df, spy_df)
            trend_data = signal_service.analyze_trend_context(ticker_df, spy_df)
        else:
            trend_data = signal_service._get_default_trend_context()

        data = SignalPromptData(
            ticker=report.ticker,
            dataframe=report.dataframe,
            last_price=report.last_price or 0.0,
            price_change_pct=report.price_change_pct or 0.0,
            triggered_strategies=triggered_strategies,
            technical_details=technical_details,
            fundamentals=report.fundamentals,
            news=None,
            spy_description=(
                f"S&P500(SPY) is Abobe SMA20 above {round(spy_persentage_from_200ma, 3)}%"
                if mkt_ok
                else f"S&P500(SPY) is Below SMA20 below {round(spy_persentage_from_200ma, 3)}%"
            ),
            additional_info=None,
            vix_data=VixData(**vix_data),
            options_data=OptionsData(
                spy_put_call_ratio=spy_options.get("put_call_ratio"),
                spy_put_call_avg_30d=spy_options.get("put_call_avg_30d"),
                qqq_put_call_ratio=qqq_options.get("put_call_ratio"),
                qqq_put_call_avg_30d=qqq_options.get("put_call_avg_30d"),
                sentiment=options_sentiment,
                iv_percentile=spy_options.get("iv_percentile"),
            ),
            trend_context=TrendContext(**trend_data),
        )

        message = None

        try:
            message = aws_service.generate_queue_message_http(
                body=data.model_dump_json(),
                path="signals/llm-query",
                method="POST",
                query_string_parameters={},
                auth_token=settings.auth_token,  # Use auth token from settings
            )
        except Exception as e:
            logger.error(f"Error generating SQS message: {e}")

        try:
            aws_service.send_sqs_fifo_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
                message_body=json.dumps(message),
                message_group_id="signal",
                message_deduplication_id=report.ticker
                + "signal"
                + market_reference_date.isoformat(),
            )
        except Exception as e:
            logger.error(f"Error Sending SQS message: {e}")

    return {
        "status": "success",
        "message": "Signal generation requests have been queued successfully.",
    }


@router.get(
    "/naver/news/today",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def naver_today_news(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    return await signal_service.get_today_items()


@router.post("/get-signals", response_model=List[SignalBaseResponse])
@inject
async def get_all_signals(
    request: GetSignalRequest,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    모든 시그널을 조회합니다.
    """
    return await db_signal_service.get_all_signals(request=request)


@router.get("/today", response_model=List[SignalBaseResponse])
@inject
async def get_today_signals(
    action: Literal["buy", "sell", "hold", "all"] = "buy",
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    오늘 생성된 모든 시그널을 조회합니다.
    """
    return await db_signal_service.get_today_signals(action=action)


@router.get("/today/{ticker}", response_model=List[SignalBaseResponse])
@inject
async def get_today_signals_by_ticker(
    ticker: str,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    오늘 생성된 특정 티커의 시그널을 조회합니다.
    """
    # 오늘 날짜에 해당하는 모든 시그널 가져오기
    all_today_signals = await db_signal_service.get_today_signals()

    # 특정 티커에 해당하는 시그널만 필터링
    ticker_signals = [
        signal
        for signal in all_today_signals
        if signal.ticker.upper() == ticker.upper()
    ]

    return ticker_signals


@router.get("/weekly/action-count")
@inject
async def get_weekly_action_count(
    tickers: Optional[str] = None,
    reference_date: Optional[dt.date] = None,
    action: Literal["Buy", "Sell"] = "Buy",
    order_by: Optional[Literal["counts"]] = None,
    limit: int = 10,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """지정한 날짜 기준 일주일간 액션별 시그널 개수를 조회합니다."""

    ticker_list = (
        [t.strip().upper() for t in tickers.split(",") if t]
        if tickers
        else DefaultTickers
    )

    market_reference_date = get_latest_market_date()
    selected_reference_date = reference_date or market_reference_date
    reference_date = validate_date(selected_reference_date)

    result = await db_signal_service.get_weekly_action_counts(
        ticker_list, reference_date, action, order_by, limit
    )

    return {
        "signals": result,
    }


@router.get("/date", response_model=GetSignalByDateResponse)
@inject
async def get_signal_by_date(
    date: str,
    symbols: str = "",
    strategy_type: Optional[str] = None,
    limit: Optional[int] = None,
    order_by: Optional[Literal["probability"]] = None,
    order_by_direction: Optional[Literal["asc", "desc"]] = "desc",
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    특정 날짜에 생성된 시그널을 조회합니다.

    Args:
        date: 조회할 날짜 (YYYY-MM-DD 형식)
        symbols: 쉼표로 구분된 티커 심볼 목록
        strategy_type: 조회할 전략 유형 ('AI_GENERATED', 'NOT_AI_GENERATED', None=모든 전략)
    """
    symbol_list = symbols.split(",") if symbols and symbols.strip() else []

    date_value = dt.datetime.strptime(date, "%Y-%m-%d").date()
    validate_date(date_value)

    response = await db_signal_service.get_signals_result(
        date=date_value,
        symbols=symbol_list,
        strategy_type=strategy_type,
        limit=limit,
        order_by=order_by,
        order_by_direction=order_by_direction,
    )

    return {"signals": response}


@router.post(
    "/signals/by-only-ai",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def get_signals_by_only_ai(
    request: GetSignalByOnlyAIRequest,
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    signals_repository: SignalsRepository = Depends(
        Provide[Container.repositories.signals_repository]
    ),
):
    """
    AI로 생성된 시그널만 조회합니다.
    """
    try:
        # 티커 목록 설정 (없으면 기본 티커 사용)
        tickers = request.tickers if request.tickers else DefaultTickers

        market_reference_date = get_latest_market_date()
        target_date = request.date or market_reference_date

        # Convert target_date to date object if it's datetime
        if isinstance(target_date, dt.datetime):
            target_date = target_date.date()

        target_date = validate_date(target_date)
        date_str = target_date.strftime("%Y-%m-%d")

        logger.info(f"Generating AI signals for {len(tickers)} tickers on {date_str}")

        # AI 모델을 사용하여 시그널 생성
        prompt = f"""
        You are a top-tier quantitative analyst and stock market expert with 20+ years of experience on Wall Street. Your analysis is known for accuracy, depth, and actionable insights.

        TASK: Generate investment recommendations for a carefully selected list of stocks based on current market data.

        CONTEXT:
        - Current date for analysis: {date_str}
        - Ticker symbols to analyze: {', '.join(tickers)}
        - Required output: Forecast Today's "BUY/SELL" recommendations For Tickers Today with supporting evidence

        STEP-BY-STEP PROCESS:
        1. For each ticker, thoroughly research the latest information as of {date_str}, including:
            * Recent earnings reports and guidance
            * Analyst ratings and price targets
            * Key news events and press releases
            * Technical indicators and price action
            * Sector-specific trends and competitive positioning

        2. Evaluate each stock using a multi-factor decision framework:
            * Current valuation metrics vs historical and sector averages
            * Revenue/EPS growth trajectory and future outlook
            * Recent price momentum and technical setup
            * Potential catalysts or risks on the horizon
            * Overall market sentiment and sector rotation dynamics

        3. For each stock, determine if there is sufficient evidence for a BUY or SELL recommendation.
            * Assign a recommendation ONLY if you have high conviction
            * If evidence is mixed or insufficient, exclude the stock from your recommendations

        4. For each recommendation, provide a concise, evidence-based justification (2-4 sentences maximum).

        OUTPUT FORMAT:
        Respond ONLY with a single valid JSON object structured exactly as follows:
        ```json
        {{
        "ai_model": "[Your model name]",
        "buy_tickers": (forecast more than 5 tickers) [
            {{"ticker": "XYZ", "result_description": "Clear rationale for buying based on specific metrics, catalysts, and analysis", "action": "buy"}}
        ],
        "sell_tickers": (forecast more than 5 tickers) [
            {{"ticker": "ABC", "result_description": "Clear rationale for selling based on specific metrics, risks, and analysis", "action": "sell"}}
        ]
        }}
        ```
        
        IMPORTANT CONSTRAINTS: Include ONLY stocks where you have high conviction (approximately 30-40% of the provided tickers)
        """

        # AI 모델에 따라 다른 메서드 호출
        results = {}

        if request.ai_model.upper() == "GOOGLE":
            results = {
                "GOOGLE": ai_service.gemini_search_grounding(
                    prompt=prompt, schema=GetSignalByOnlyAIPromptSchema
                )
            }

        elif request.ai_model.upper() == "PERPLEXITY":
            results = {
                "PERPLEXITY": ai_service.perplexity_completion(
                    prompt=prompt, schema=GetSignalByOnlyAIPromptSchema
                )
            }

        elif request.ai_model.upper() == "ALL":
            results["GOOGLE"] = ai_service.gemini_search_grounding(
                prompt=prompt, schema=GetSignalByOnlyAIPromptSchema
            )

            results["PERPLEXITY"] = ai_service.perplexity_completion(
                prompt=prompt, schema=GetSignalByOnlyAIPromptSchema
            )

        if not results:
            return {"status": "error", "message": "AI model failed to generate signals"}

        for ai_model in results:
            result = results[ai_model]
            if not isinstance(result, GetSignalByOnlyAIPromptSchema):
                logger.error(
                    f"Invalid result type: {type(result)}. Expected GetSignalByOnlyAIPromptSchema."
                )
                return {"status": "error", "message": "Invalid AI response format"}

            # 결과를 DB에 저장
            signals_created = []

            # 매수 추천 처리
            for ticker_data in result.buy_tickers:
                try:
                    signal = signals_repository.create_signal(
                        ticker=ticker_data.ticker,
                        action="buy",
                        entry_price=0.0,  # 기본값 설정
                        stop_loss=None,
                        take_profit=None,
                        close_price=None,
                        probability=None,
                        strategy="AI_GENERATED",
                        result_description=ticker_data.result_description,
                        report_summary=None,
                        ai_model=ai_model,
                        senario=None,
                        good_things=None,
                        bad_things=None,
                    )
                    signals_created.append(signal)
                except Exception as e:
                    logger.error(
                        f"Error creating buy signal for {ticker_data.ticker}: {e}"
                    )

            # 매도 추천 처리
            for ticker_data in result.sell_tickers:
                try:
                    signal = signals_repository.create_signal(
                        ticker=ticker_data.ticker,
                        action="sell",
                        entry_price=0.0,  # 기본값 설정
                        stop_loss=None,
                        take_profit=None,
                        close_price=None,
                        probability=None,
                        strategy="AI_GENERATED",
                        result_description=ticker_data.result_description,
                        report_summary=None,
                        ai_model=ai_model,
                        senario=None,
                        good_things=None,
                        bad_things=None,
                    )
                    signals_created.append(signal)
                except Exception as e:
                    logger.error(
                        f"Error creating sell signal for {ticker_data.ticker}: {e}"
                    )

        return {
            "status": "success",
            "message": f"Generated signals using {request.ai_model}",
            "ai_response": results,
        }

    except Exception as e:
        logger.error(f"Error fetching AI-generated signals: {e}")
        return {"status": "error", "message": str(e)}


@router.post(
    "/discord/message", tags=["discord"], dependencies=[Depends(verify_bearer_token)]
)
@inject
def send_discord_message(
    request: DiscordMessageRequest,
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    """
    디스코드 메시지를 전송하는 헬퍼 함수입니다.
    """
    try:
        result = discord_service.send_message(
            content=request.content, embeds=request.embed
        )
        logger.info(f"Discord message sent successfully: {result}")
        return {"status": "success", "message": "Discord message sent successfully."}
    except Exception as e:
        result = discord_service.send_message(
            content="Error sending Discord message: " + str(e), embeds=None
        )
        logger.error(f"Error sending Discord message: {e}")


@router.get("/ticker/{ticker}", response_model=List[SignalBaseResponse])
@inject
async def get_signals_by_ticker(
    ticker: str,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    특정 티커의 모든 시그널을 조회합니다.
    """
    return await db_signal_service.get_signals_by_ticker(ticker)


@router.get("/recent", response_model=List[SignalBaseResponse])
@inject
async def get_recent_signals(
    limit: int = 10,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    최근 시그널들을 조회합니다.
    """
    return await db_signal_service.get_recent_signals(limit=limit)


@router.get("/high-probability", response_model=List[SignalBaseResponse])
@inject
async def get_high_probability_signals(
    threshold: float = 70.0,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    높은 확률의 시그널들을 조회합니다.
    """
    return await db_signal_service.get_high_probability_signals(threshold=threshold)


@router.get("/stats/{by_type}")
@inject
async def get_signals_stats(
    by_type: Literal["ticker", "strategy"] = "ticker",
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    시그널 통계를 조회합니다.
    """
    return await db_signal_service.get_signals_stats(by_type=by_type)
