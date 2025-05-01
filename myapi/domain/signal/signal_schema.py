from pydantic import BaseModel, Field, validator
from datetime import date
from typing import List, Dict, Literal

Strategy = Literal["PULLBACK", "OVERSOLD", "MACD_LONG", "GAPPER"]


class SignalRequest(BaseModel):
    tickers: List[str] | None = None
    strategies: List[Strategy] = Field(
        default_factory=lambda: ["PULLBACK", "OVERSOLD", "MACD_LONG"]
    )
    start: date | None = None  # 없으면 settings.START_DAYS_BACK 로 계산
    with_fundamental: bool = True
    with_news: bool = True


class TechnicalSignal(BaseModel):
    strategy: Strategy
    triggered: bool
    details: Dict[str, float]


class FundamentalData(BaseModel):
    trailing_pe: float | None = None
    eps_surprise_pct: float | None = None
    revenue_growth: float | None = None


class NewsHeadline(BaseModel):
    title: str
    url: str
    sentiment: Literal["positive", "neutral", "negative"]


class TickerReport(BaseModel):
    ticker: str
    signals: List[TechnicalSignal]
    fundamentals: FundamentalData | None = None
    news: List[NewsHeadline] | None = None


class SignalResponse(BaseModel):
    run_date: date
    reports: List[TickerReport]
