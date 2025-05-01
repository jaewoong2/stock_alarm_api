from fastapi import APIRouter, Depends
from datetime import date, timedelta

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.signal.signal_schema import (
    SignalRequest,
    SignalResponse,
    TickerReport,
)
from myapi.services.discord_service import DiscordService
from myapi.services.signal_service import SignalService

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/", response_model=SignalResponse)
@inject
def get_signals(
    req: SignalRequest,
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    DEFAULT_UNIVERSE: str = "SPY,QQQ,AAPL,MSFT,TSLA,COIN"
    START_DAYS_BACK: int = 365
    run_date = date.today()
    tickers = req.tickers or DEFAULT_UNIVERSE.split(",")

    start = req.start or (run_date - timedelta(days=START_DAYS_BACK))

    reports: list[TickerReport] = []
    for t in tickers:
        df = signal_service.fetch_ohlcv(t, start=start)

        if df is None or df.empty:
            continue

        df = signal_service.add_indicators(df)
        tech_sigs = signal_service.evaluate_signals(df, req.strategies)

        funda = signal_service.fetch_fundamentals(t) if req.with_fundamental else None
        news = signal_service.fetch_news(t) if req.with_news else None

        reports.append(
            TickerReport(ticker=t, signals=tech_sigs, fundamentals=funda, news=news)
        )

    return SignalResponse(run_date=run_date, reports=reports)
