import dis
import json
from typing import List
from unittest import result
from fastapi import APIRouter, Depends
from datetime import date, timedelta

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.signal.signal_schema import (
    DefaultStrategies,
    DefaultTickers,
    SignalPromptData,
    SignalPromptResponse,
    SignalRequest,
    SignalResponse,
    TechnicalSignal,
    TickerReport,
)
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.discord_service import DiscordService
from myapi.services.signal_service import SignalService
from myapi.utils.utils import format_signal_response

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/llm-query", response_model=SignalResponse)
@inject
def llm_query(
    req: SignalPromptData,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    """
    LLM 쿼리를 처리하는 엔드포인트입니다.
    """
    prompt = signal_service.generate_prompt(data=req)

    result = ai_service.completions_parse(
        system_prompt="",
        prompt=prompt,
        image_url=None,
        schema=SignalPromptResponse,
        chat_model=ChatModel.O4_MINI,
    )

    discord_service.send_message(content=f"{format_signal_response(result)}")

    return result


@router.post("/", response_model=SignalResponse)
@inject
def get_signals(
    req: SignalRequest,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    START_DAYS_BACK: int = 100
    run_date = date.today()
    tickers = req.tickers or DefaultTickers
    strategies = req.strategies or DefaultStrategies

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
        news = signal_service.fetch_news(t) if req.with_news else None

        reports.append(
            TickerReport(
                ticker=t,
                last_price=df["Close"].iloc[-1],
                price_change_pct=df["Close"].pct_change().iloc[-1],
                signals=tech_sigs,
                fundamentals=funda,
                news=news,
                dataframe=df.tail(20).to_csv(),
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

        data = SignalPromptData(
            ticker=report.ticker,
            dataframe=report.dataframe,
            last_price=report.last_price or 0.0,
            price_change_pct=report.price_change_pct,
            triggered_strategies=triggered_strategies,
            technical_details=technical_details,
            fundamentals=report.fundamentals,
            news=report.news,
            additional_info=None,
        )

        message = {
            "body": data.model_dump_json(),
            "resource": "/{proxy+}",
            "path": "/signals/llm-query",
            "httpMethod": "POST",
            "isBase64Encoded": False,
            "pathParameters": {"proxy": "signals/llm-query"},
            "queryStringParameters": {},
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, sdch",
                "Accept-Language": "ko",
                "Accept-Charset": "utf-8",
            },
            "requestContext": {
                "path": "/signals/llm-query",
                "resourcePath": "/{proxy+}",
                "httpMethod": "POST",
            },
        }

        try:
            aws_service.send_sqs_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto",
                message_body=json.dumps(message),
            )
        except Exception as e:
            print(f"Error sending SQS message: {e}")
            raise

        discord_service.send_message(
            content=f"SQS Message For AI Query Sended, Signal detected for {report.ticker} with strategies: {triggered_strategies}"
        )

    return SignalResponse(
        run_date=run_date,
        reports=reports,
        market_condition=(
            "시장 컨디션이 좋습니다. (예: 지수가 50 SMA 위)"
            if mkt_ok
            else "시장 컨디션이 좋지 않습니다. (예: 지수가 50 SMA 아래)"
        ),
    )
