from pydantic import BaseModel, Field, validator
from datetime import date
from typing import List, Dict, Literal, Optional

Strategy = Literal["PULLBACK", "OVERSOLD", "MACD_LONG", "GAPPER", "VOL_DRY_BOUNCE"]


class SignalRequest(BaseModel):
    tickers: List[str] | None = [
        "SPY",
        "QQQ",
        "AAPL",
        "MSFT",
        "TSLA",
        "COIN",
        "SOXX",
        "NVDA",
        "AMD",
        "PLTR",
        "AMZN",
    ]
    strategies: List[Strategy] = Field(
        # default=["PULLBACK", "OVERSOLD", "MACD_LONG", "GAPPER"],
        default_factory=lambda: [
            "PULLBACK",
            "OVERSOLD",
            "MACD_LONG",
            "GAPPER",
            "VOL_DRY_BOUNCE",
        ],
    )
    start: date | None = None  # 없으면 settings.START_DAYS_BACK 로 계산
    with_fundamental: bool = True
    with_news: bool = True


class TechnicalSignal(BaseModel):
    strategy: Strategy
    triggered: bool
    details: Dict[str, float | None]


class FundamentalData(BaseModel):
    trailing_pe: float | None = None
    eps_surprise_pct: float | None = None
    revenue_growth: float | None = None


class NewsHeadline(BaseModel):
    title: str
    url: str
    sentiment: Optional[Literal["positive", "neutral", "negative"]]


class TickerReport(BaseModel):
    ticker: str
    signals: List[TechnicalSignal]
    fundamentals: FundamentalData | None = None
    news: List[NewsHeadline] | None = None


class SignalResponse(BaseModel):
    run_date: date
    reports: List[TickerReport]
    market_condition: Optional[str] = None
