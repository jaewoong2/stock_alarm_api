from tkinter import NO
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Dict, Literal, Optional

Strategy = Literal[
    "PULLBACK",
    "OVERSOLD",
    "MACD_LONG",
    "GAPPER",
    "VOL_DRY_BOUNCE",
    "GOLDEN_CROSS",
    "MEAN_REVERSION",
    "BREAKOUT",
    "GAP_UP",
    "VWAP_BOUNCE",
    "MOMENTUM_SURGE",
    "VOLUME_SPIKE",
    "TREND_UP",
    "TREND_DOWN",
    "DONCHIAN_BREAKOUT",
    "VOLUME_EXPANSION",
    "QUIET_PULLBACK",
    "VOLATILITY_COMPRESSION",
]

DefaultStrategies: List[Strategy] = [
    "PULLBACK",
    "OVERSOLD",
    "MACD_LONG",
    "GAPPER",
    "VOL_DRY_BOUNCE",
    "GOLDEN_CROSS",
    "MEAN_REVERSION",
    "BREAKOUT",
    "GAP_UP",
    "VWAP_BOUNCE",
    "MOMENTUM_SURGE",
    "VOLUME_SPIKE",
    "TREND_UP",
    "TREND_DOWN",
    "DONCHIAN_BREAKOUT",
    "VOLUME_EXPANSION",
    "QUIET_PULLBACK",
    "VOLATILITY_COMPRESSION",
]

DefaultTickers = [
    # ETF
    "SPY",  # SPDR S&P 500 ETF Trust
    "QQQ",  # Invesco QQQ Trust
    "IWM",  # iShares Russell 2000 ETF
    "XLK",  # Technology Select Sector SPDR Fund
    "XLF",  # Financial Select Sector SPDR Fund
    "TQQQ",  # ProShares UltraPro QQQ
    "SQQQ",  # ProShares UltraPro QQQ
    "SOXL",  # Direxion Daily Semiconductor Bull 3X Shares
    "SPXL",  # S&P 500 Bull 3X Shares
    "XBI",  # SPDR S&P Biotech ETF
    "XOP",  # SPDR S&P Oil & Gas Exploration & Production ETF
    "KRE",  # SPDR S&P Regional Banking ETF
    "SMH",  # VanEck Vectors Semiconductor ETF
    "XLE",  # Energy Select Sector SPDR Fund
    "GDX",  # VanEck Vectors Gold Miners ETF
    "XRT",  # SPDR S&P Retail ETF
    "UVXY",  # ProShares Ultra VIX Short-Term Futures ETF
    "VWO",  # Vanguard FTSE Emerging Markets ETF
    "ARKK",  # ARK Innovation ETF
    # Stocks
    "META",  # Meta Platforms, Inc.
    "MU",  # Micron Technology, Inc.
    "GOOGL",  # Alphabet Inc. (Class A)
    "AVGO",  # Broadcom, Inc.
    "NFLX",  # Netflix, Inc.
    "AAPL",  # Apple Inc.
    "MSFT",  # Microsoft Corporation
    "NVDA",  # NVIDIA Corporation
    "AMD",  # Advanced Micro Devices, Inc.
    "TSLA",  # Tesla, Inc.
    "JPM",  # JPMGan Chase & Co.
    "BAC",  # Bank of America Corporation
    "AMZN",  # Amazon.com, Inc.
    "WMT",  # Walmart Inc.
    "COIN",  # Coinbase Global, Inc.
    "HOOD",  # Robinhood Markets, Inc.
    "MSTR",  # MicroStrategy
    "SMCI",  # Super Micro Computer, Inc.
    "CRM",  # Salesforce, Inc.
    "MRVL",  # Marvell Technology, Inc.
    "FSLR",  # First Solar, Inc.
    "PLTR",  # Palantir Technologies Inc.
    "RBLX",  # Roblox Corporation
    "LMT",  # Lockheed Martin Corporation
    "MMM",  # 3M Company
]


class SignalPassAIInQuery(BaseModel):
    """
    SignalPassAIInQuery는 SignalPassAI에 대한 쿼리 파라미터를 정의합니다.
    """

    inquery_date: date | None = None
    ticker: str | None = None
    description: str | None = None


class SignalRequest(BaseModel):
    tickers: List[str] | None = DefaultTickers
    strategies: List[Strategy] = Field(
        # default=["PULLBACK", "OVERSOLD", "MACD_LONG", "GAPPER"],
        default_factory=lambda: DefaultStrategies,
    )
    # start: date | None = None  # 없으면 settings.START_DAYS_BACK 로 계산
    with_fundamental: bool = True
    with_news: bool = True


class TechnicalSignal(BaseModel):
    strategy: Strategy
    triggered: bool
    details: Dict[str, float | None]
    triggered_description: str | None = None

    @property
    def description(self) -> str:
        """
        각 전략에 대한 설명을 반환합니다.
        """
        if self.strategy == "PULLBACK":
            return "주가가 단기 이동평균선(10일 SMA)에 근접하거나 약간 하락한 후 장기 이동평균선(50일 SMA) 위에서 반등 가능성 포착. (상승 추세에서 일시적 조정을 매수 기회)"
        elif self.strategy == "OVERSOLD":
            return "주가가 과매도 상태(RSI < 35)이고 볼린저 밴드 하단 아래로 떨어졌을 때 반등 가능성 포착. (과도한 매도로 저평가된 종목)"
        elif self.strategy == "MACD_LONG":
            return "MACD 히스토그램이 음수에서 양수로 전환될 때 추세 전환(상승)을 가능성을 포착. (단기 모멘텀 강화)"
        elif self.strategy == "VOL_DRY_BOUNCE":
            return "거래량이 낮은 'Dry-Up' 구간(최근 10일) 후 주가가 단기 이동평균선(5일 SMA)을 돌파하며 반등 가능성 포착. (저유동성 후 돌파를 활용)"
        elif self.strategy == "GOLDEN_CROSS":
            return "단기 이동평균선(50일 SMA)이 장기 이동평균선(200일 SMA)을 상향 돌파할 때 강한 상승 추세의 시작 가능성 포착. (장기 투자)"
        elif self.strategy == "MEAN_REVERSION":
            return "주가가 평균(20일 SMA)에서 크게 벗어났다가 다시 복귀할 때 반전 기회를 포착 가능성. (단기 변동성)"
        elif self.strategy == "BREAKOUT":
            return "주가가 최근 52주 최고가를 돌파할 때 강한 상승 모멘텀을 포착 가능성. (새로운 고점 돌파로 추가 상승)"
        else:
            return "알 수 없는 전략입니다."


class FundamentalData(BaseModel):
    trailing_pe: float | None = None
    eps_surprise_pct: float | None = None
    revenue_growth: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    fcf_yield: float | None = None


class NewsHeadline(BaseModel):
    title: str
    url: str
    sentiment: Optional[Literal["positive", "neutral", "negative"]]


class TickerReport(BaseModel):
    ticker: str
    last_price: float | None = None
    price_change_pct: float | None = None

    signals: List[TechnicalSignal]
    fundamentals: FundamentalData | None = None
    news: List[NewsHeadline] | None = None
    dataframe: str | None = None


class SignalPromptData(BaseModel):
    """
    SignalPromptData는 SignalPassAI에 대한 쿼리 파라미터를 정의합니다.
    """

    ticker: str
    dataframe: str | None = None
    last_price: float | None = None
    price_change_pct: float | None = None
    triggered_strategies: list[str]
    technical_details: Dict[str, Dict[str, float | None]]
    fundamentals: FundamentalData | None = None
    news: List[NewsHeadline] | None = None
    additional_info: str | None = None

    spy_description: str | None = None


class AnalyticsReportPromptResponse(BaseModel):
    # 1) Price Action
    # 2) Volume
    # 3) Trend & Pattern
    # 4) Technical Signals
    # 5) Support & Resistance
    # 6) Expected Volatility & Risk
    # 7) Overall Assessment.

    price_action: str
    volume: str
    trend_and_pattern: str
    technical_signals: str
    support_and_resistance: str
    expected_volatility_and_risk: str
    overall_assessment: str


class SignalPromptResponse(BaseModel):

    # ticker: Stock/ETF ticker.
    # reasoning: Step-by-step explanation of the recommendation.
    # recommendation: "BUY", "SELL", or "HOLD".
    # entry_price: Suggested entry price (null for HOLD).
    # stop_loss_price: Suggested stop-loss price (null for HOLD).
    # take_profit_price: Suggested take-profit price (null for HOLD).

    ticker: str
    reasoning: str
    probability_of_rising_up: str
    recommendation: Literal["BUY", "SELL", "HOLD"]
    senarios: str | None = None
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    # additional_info: Additional information or context for the recommendation.


class SignalResponse(BaseModel):
    run_date: date
    reports: List[TickerReport]
    market_condition: Optional[str] = None


class SignalBase(BaseModel):
    """시그널 기본 스키마"""

    ticker: str
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    action: str  # "buy" or "sell" or "hold"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    probability: Optional[str] = None
    result_description: Optional[str] = None
    report_summary: Optional[str] = None


class SignalVO(SignalBase):
    """시그널 값 객체(Value Object) 스키마"""

    id: Optional[int] = None

    class Config:
        from_attributes = True


class SignalCreate(SignalBase):
    """시그널 생성 요청 스키마"""

    pass


class SignalBaseResponse(SignalBase):
    """시그널 응답 스키마"""

    id: int

    class Config:
        from_attributes = True


class SignalUpdate(BaseModel):
    """시그널 업데이트 요청 스키마"""

    ticker: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    action: Optional[str] = None
    probability: Optional[float] = None
    result_description: Optional[str] = None


# models.py
from datetime import date, datetime
from typing import Literal, List
from pydantic import BaseModel, Field


class Article(BaseModel):
    id: str
    title: str
    summary: str
    url: str
    published: datetime
    category: str = Field(..., examples=["earnings", "m&a", "regulatory"])


class NewsResponse(BaseModel):
    date: date
    articles: List[Article]


class TickerImpact(BaseModel):
    ticker: str
    catalyst: str
    sentiment: Literal["positive", "neutral", "negative"]
    source_article_id: str


class DateRange(BaseModel):
    start: date
    end: date
