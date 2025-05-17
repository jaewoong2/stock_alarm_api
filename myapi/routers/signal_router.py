from asyncio import sleep
import json
import logging
from venv import logger
from fastapi import APIRouter, Depends, Path
from datetime import date, timedelta

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.signal.signal_schema import (
    DefaultStrategies,
    DefaultTickers,
    NewsResponse,
    SignalPromptData,
    SignalPromptResponse,
    SignalRequest,
    SignalResponse,
    TechnicalSignal,
    TickerImpact,
    TickerReport,
)
from myapi.repositories.signals_repository import SignalsRepository
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.discord_service import DiscordService
from myapi.services.signal_service import SignalService
from myapi.utils.utils import format_signal_response

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


@router.post("/llm-query")
@inject
def llm_query(
    req: SignalPromptData,
    signals_repository: SignalsRepository = Depends(
        Provide[Container.repositories.signals_repository]
    ),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """

    pdf_report, summary = None, None

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

    result = ai_service.completions_parse(
        system_prompt="",
        prompt=prompt,
        image_url=None,
        schema=SignalPromptResponse,
        chat_model=ChatModel.O4_MINI,
    )

    try:
        signals_repository.create_signal(
            ticker=req.ticker,
            action=result.recommendation.lower(),
            entry_price=result.entry_price or 0.0,
            stop_loss=result.stop_loss_price,
            take_profit=result.take_profit_price,
            probability=result.probability_of_rising_up,
            strategy=",".join(req.triggered_strategies),
            result_description=result.reasoning,
            report_summary=summary,
        )
    except Exception as e:
        logger.error(f"Error saving signal to database: {e}")

    discord_service.send_message(content=f"{format_signal_response(result)}")

    return result


@router.post("/", response_model=SignalResponse)
@inject
async def get_signals(
    req: SignalRequest,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
):
    START_DAYS_BACK: int = 100
    run_date = date.today()
    tickers = req.tickers or DefaultTickers
    strategies = DefaultStrategies

    start = run_date - timedelta(days=START_DAYS_BACK)

    reports: list[TickerReport] = []
    for t in tickers:
        df = signal_service.fetch_ohlcv(t, start=start)

        if df is None or df.empty:
            continue

        df = signal_service.add_indicators(df)

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
                dataframe=df.tail(20).round(3).to_csv(),
            )
        )

    mkt_ok = signal_service.market_ok()

    triggered_report = [
        report
        for report in reports
        if any(signal.triggered for signal in report.signals)
    ]

    for report in triggered_report:
        triggered_strategies = [
            signal.strategy for signal in report.signals if signal.triggered
        ]

        technical_details = {
            signal.strategy: signal.details
            for signal in report.signals
            if signal.triggered
        }

        try:
            news = signal_service.fetch_news(report.ticker) if req.with_news else None
            report.news = news
        except Exception as e:
            logger.error(f"Error fetching news for {report.ticker}: {e}")
            report.news = None

        data = SignalPromptData(
            ticker=report.ticker,
            dataframe=report.dataframe,
            last_price=report.last_price or 0.0,
            price_change_pct=report.price_change_pct,
            triggered_strategies=triggered_strategies,
            technical_details=technical_details,
            fundamentals=report.fundamentals,
            news=report.news,
            spy_description=(
                "S&P500(SPY) is Abobe SMA20" if mkt_ok else "S&P500(SPY) is Below SMA20"
            ),
            additional_info=None,
        )

        await sleep(3)

        message = aws_service.generate_queue_message_http(
            body=data.model_dump_json(),
            path="signals/llm-query",
            method="POST",
            query_string_parameters={},
        )

        try:
            aws_service.send_sqs_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto",
                message_body=json.dumps(message),
            )
        except Exception as e:
            print(f"Error sending SQS message: {e}")

    return SignalResponse(
        run_date=run_date,
        reports=reports,
        market_condition=(
            "시장 컨디션이 좋습니다. (예: 지수가 50 SMA 위)"
            if mkt_ok
            else "시장 컨디션이 좋지 않습니다. (예: 지수가 50 SMA 아래)"
        ),
    )


@router.get("/naver/news/today")
@inject
async def naver_today_news(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    return await signal_service.get_today_items()
