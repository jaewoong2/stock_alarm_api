from asyncio import sleep
import datetime
import json
import logging
from typing import List, Literal
from venv import logger
from fastapi import APIRouter, Depends
from datetime import date, timedelta

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.signal.signal_schema import (
    DefaultStrategies,
    DefaultTickers,
    DiscordMessageRequest,
    GenerateSignalResultRequest,
    GetSignalRequest,
    SignalBaseResponse,
    SignalPromptData,
    SignalPromptResponse,
    SignalRequest,
    TechnicalSignal,
    TickerReport,
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
    format_signal_embed,
)

# 티커 생성을 위한 데이터 준비
from myapi.domain.ticker.ticker_schema import TickerCreate

router = APIRouter(prefix="/signals", tags=["signals"])

logger = logging.getLogger(__name__)


@router.post(
    "/investment-pdf",
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


@router.post("/generate-signal-reult")
@inject
def generate_signal_result(
    request: GenerateSignalResultRequest,
    signals_repository: SignalsRepository = Depends(
        Provide[Container.repositories.signals_repository]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """
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

        signals_repository.create_signal(
            ticker=request.data.ticker,
            action=result.recommendation.lower(),
            entry_price=result.entry_price or 0.0,
            stop_loss=result.stop_loss_price,
            take_profit=result.take_profit_price,
            probability=str(result.probability_of_rising_up_percentage),
            strategy=",".join(request.data.triggered_strategies),
            result_description=result.reasoning,
            report_summary=request.summary,
            ai_model=request.ai,  # Store the AI model used for the signal
            senario=result.senarios,
            good_things=result.good_things,
            bad_things=result.bad_things,
        )

        try:
            embed = format_signal_embed(result, model=request.ai)
            discord_content = DiscordMessageRequest(embed=embed)
            discord_result = aws_service.generate_queue_message_http(
                body=discord_content.model_dump_json(),
                path="signals/discord/message",
                method="POST",
                query_string_parameters={},
            )
            aws_service.send_sqs_fifo_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
                message_body=json.dumps(discord_result),
                message_group_id="discord",
                message_deduplication_id="discord_"
                + str(request.data.ticker)
                + str(request.ai)
                + str(date.today()),
            )

            return discord_content
        except Exception as e:
            logger.error(f"Error SendingDiscord: {e}")

        return result

    except Exception as e:
        logger.error(f"Error generating signal result: {e}")
        return {"error": str(e)}


@router.post("/llm-query")
@inject
def llm_query(
    req: SignalPromptData,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """

    pdf_report, summary, web_search_gemini_result = None, None, None

    try:
        today = date.today()
        today_YYYY_MM_DD = today.strftime("%Y-%m-%d")
        web_search_gemini_result = ai_service.gemini_search_grounding(
            prompt=signal_service.generate_web_search_prompt(
                req.ticker, today_YYYY_MM_DD
            ),
            schema=WebSearchTickerResponse,
        )
        if web_search_gemini_result:
            signal_service.save_web_search_results(
                result_type="ticker",
                results=web_search_gemini_result.search_results,
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
        )
        aws_service.send_sqs_fifo_message(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
            message_body=json.dumps(google_result),
            message_group_id="google",
            message_deduplication_id=req.ticker + "google" + str(date.today()),
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
        )
        aws_service.send_sqs_fifo_message(
            queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
            message_body=json.dumps(openai_result),
            message_group_id="openai",
            message_deduplication_id=req.ticker + "openai" + str(date.today()),
        )

    except Exception as e:
        logger.error(f"Error generating OpenAI signal result: {e}")
        openai_result = None

    return [google_result, openai_result]


@router.post("/")
@inject
async def get_signals(
    req: SignalRequest,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
):
    START_DAYS_BACK: int = 400
    run_date = date.today()
    tickers = req.tickers or DefaultTickers
    strategies = DefaultStrategies

    start = run_date - timedelta(days=START_DAYS_BACK)

    spy_persentage_from_200ma = 0.0
    mkt_ok = False
    reports: list[TickerReport] = []
    for t in tickers:
        df = signal_service.fetch_ohlcv(t, start=start)

        if df is None or df.empty:
            continue

        df = signal_service.add_indicators(df)

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
            for signal in signal_service.evaluate_signals(df, strategies, ticker=t)
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
                dataframe=export_slim_tail_csv(df, 260),
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
        )

        try:
            message = aws_service.generate_queue_message_http(
                body=data.model_dump_json(),
                path="signals/llm-query",
                method="POST",
                query_string_parameters={},
            )
        except Exception as e:
            logger.error(f"Error generating SQS message: {e}")

        await sleep(1)  # To avoid throttling issues with SQS

        try:
            aws_service.send_sqs_fifo_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo",
                message_body=json.dumps(message),
                message_group_id="signal",
                message_deduplication_id=report.ticker + "signal" + str(date.today()),
            )
        except Exception as e:
            logger.error(f"Error Sending SQS message: {e}")

    return {
        "status": "success",
        "message": "Signal generation requests have been queued successfully.",
    }


@router.get("/naver/news/today")
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


@router.get("/date")
@inject
async def get_signal_by_date(
    date: str,
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    특정 날짜에 생성된 시그널을 조회합니다.
    """
    date_value = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    response = await db_signal_service.get_signals_result(date=date_value)

    return {
        "date": date_value,
        "signals": response,
    }


@router.post("/discord/message", tags=["discord"])
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
