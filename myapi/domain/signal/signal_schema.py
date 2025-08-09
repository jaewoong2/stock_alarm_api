from myapi.domain.signal.signal_models import Signals
from pydantic import BaseModel, Field
from datetime import date, datetime, timezone
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
    "VCP_DAILY",
    "RS_SHORT",
    "RS_MID",
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
    "VCP_DAILY",
    "RS_SHORT",
    "RS_MID",
]

DefaultTickers = [
    "CRWV",
    "SPY",
    "QQQ",
    "AMAT",
    "AMD",
    "ANET",
    "ASML",
    "AVGO",
    "COHR",
    "GFS",
    "KLAC",
    "MRVL",
    "MU",
    "NVDA",
    "NVMI",
    "ONTO",
    "SMCI",
    "STX",
    "TSM",
    "VRT",
    "WDC",
    "AXON",
    "LMT",
    "NOC",
    "RCAT",
    "AFRM",
    "APP",
    "COIN",
    "HOOD",
    "IREN",
    "MQ",
    "MSTR",
    "NVEI",
    "SOFI",
    "TOST",
    "CEG",
    "FSLR",
    "LNG",
    "NRG",
    "OKLO",
    "PWR",
    "SMR",
    "VST",
    "CRWD",
    "FTNT",
    "GTLB",
    "KNBE",
    "NET",
    "OKTA",
    "PANW",
    "S",
    "TENB",
    "ZS",
    "AAPL",
    "ADBE",
    "ADSK",
    "AI",
    "AMZN",
    "ASAN",
    "BILL",
    "CRM",
    "DDOG",
    "DOCN",
    "GOOGL",
    "HUBS",
    "META",
    "MNDY",
    "MSFT",
    "NOW",
    "PCOR",
    "PLTR",
    "SNOW",
    "VEEV",
    "IONQ",
    "QBTS",
    "RGTI",
    "PL",
    "RKLB",
    "LUNR",
    "ACHR",
    "ARBE",
    "JOBY",
    "TSLA",
    "UBER",
    "ORCL",
    "CFLT",
    "CRNC",
    "DXCM",
    "INTU",
    "IOT",
    "LRCX",
    "NFLX",
    "PODD",
    "PSTG",
    "RBLX",
    "RDDT",
    "SERV",
    "SHOP",
    "SOUN",
    "TDOC",
    "PATH",
    "DXYZ",
    "NKE",
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

    def model_post_init(self, __context):
        """
        Post-initialization hook to round float values in details to 2 decimal places.
        """
        if self.details:
            for key, value in self.details.items():
                if isinstance(value, float) and value is not None:
                    self.details[key] = round(value, 2)

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


class ChartPattern(BaseModel):
    name: str
    description: str
    pattern_type: Literal["bullish", "bearish", "neutral"]
    confidence_level: float = (
        0.0  # Confidence level of the pattern detection (0.0 to 1.0)
    )


class SignalPromptResponse(BaseModel):
    ticker: str
    good_things: str = ""
    bad_things: str = ""
    reasoning: str
    think_steps: str = ""
    probability_of_rising_up_percentage: float
    probability_of_rising_up: str
    recommendation: Literal["BUY", "SELL", "HOLD"]
    senarios: str = ""
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    close_price: float = 0.0
    chart_pattern: ChartPattern


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    probability: Optional[str] = None
    result_description: Optional[str] = None
    report_summary: Optional[str] = None
    strategy: Optional[str] = None
    close_price: Optional[float] = None  # 거래 종료 가격
    ai_model: Optional[str] = "OPENAI"  # AI 모델 이름
    senario: Optional[str] = None  # 시나리오 설명 250606 추가
    good_things: Optional[str] = None  # 좋은 점 250606 추가
    bad_things: Optional[str] = None  # 나쁜 점 250606 추가
    chart_pattern: Optional[ChartPattern] = None  # 차트 패턴 정보


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
from datetime import date, datetime, timezone
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


class WebSearchTickerResult(BaseModel):
    issued_YYYYMMDD: str
    summary: str
    full_description: str
    recommendation: Literal["Buy", "Hold", "Sell"]
    recommendation_with_why: str


class WebSearchTickerResponse(BaseModel):
    search_results: List[WebSearchTickerResult]
    total_detail_description_with_why: str
    total_recommendation: Literal["Buy", "Hold", "Sell", "None"]


class GenerateSignalResultRequest(BaseModel):
    """
    Response schema for the generate signal result endpoint.
    """

    ai: Literal["OPENAI", "GOOGLE"] = "OPENAI"  # Store the AI model used for the signal
    data: SignalPromptData
    summary: str
    prompt: str


class DiscordMessageRequest(BaseModel):
    """
    Schema for Discord messages.
    """

    content: str = ""
    embed: Optional[List] = None  # Optional embed data for rich content


class GetSignalRequest(BaseModel):
    """
    Request schema for getting signals.
    """

    tickers: List[str] | None = None  # Optional ticker filter
    start_date: str | None = None  # Optional start date for filtering
    end_date: str | None = None  # Optional end date for filtering
    actions: List[Literal["Buy", "Sell", "Hold"]] | None = (
        None  # Optional action filter
    )


class SignalWithTicker(BaseModel):
    """
    Signal with ticker information.
    """

    id: int
    ticker: str
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    action: Literal["buy", "sell", "hold"]
    timestamp: datetime
    probability: Optional[str] = None
    result_description: Optional[str] = None
    report_summary: Optional[str] = None
    strategy: Optional[str] = None


class SignalJoinTickerResponse(BaseModel):
    class Signal(BaseModel):
        ticker: str
        strategy: Optional[str] = None
        entry_price: Optional[float]
        stop_loss: Optional[float] = None
        take_profit: Optional[float] = None
        action: Optional[str]
        timestamp: Optional[datetime]
        probability: Optional[str] = None
        result_description: Optional[str] = None
        ai_model: Optional[str] = "OPENAI_O4MINI"
        senario: Optional[str] = None
        good_things: Optional[str] = None
        bad_things: Optional[str] = None
        close_price: Optional[float] = None
        chart_pattern: Optional[ChartPattern] = None

    class Ticker(BaseModel):
        # Ticker 정보
        symbol: str
        name: Optional[str] = None
        price: Optional[float] = None
        open_price: Optional[float] = None
        high_price: Optional[float] = None
        low_price: Optional[float] = None
        close_price: Optional[float] = None
        volume: Optional[int] = None
        ticker_date: Optional[date] = None
        created_at: Optional[datetime] = None
        updated_at: Optional[datetime] = None

    class Result(BaseModel):
        """
        Result schema for the signal with ticker.
        Contains the signal and ticker information.
        """

        action: Literal["up", "down", "unchanged", "unknown"]
        is_correct: bool = False
        price_diff: float

    signal: Signal
    ticker: Optional[Ticker]
    result: Optional[Result]

    model_config = {"from_attributes": True}


class GetSignalByOnlyAIRequest(BaseModel):
    """
    Request schema for getting signals by AI model.
    """

    ai_model: Literal["GOOGLE", "PERPLEXITY", "ALL"] = "GOOGLE"
    tickers: List[str] | None = None  # Optional ticker filter
    date: Optional[datetime] | None = (
        datetime.today()
    )  # Optional start date for filtering


class GetSignalByOnlyAIPromptSchema(BaseModel):
    """
    Prompt schema for getting signals by AI model.
    """

    class Tickers(BaseModel):
        """
        Tickers schema for the AI model.
        Contains a list of tickers to filter the signals.
        """

        ticker: str = ""
        result_description: str = ""
        action: Literal["buy", "sell", "hold"] = "buy"

    ai_model: Literal["GOOGLE", "PERPLEXITY"] = "GOOGLE"
    buy_tickers: List[Tickers] = []
    sell_tickers: List[Tickers] = []


class SignalValueObject(BaseModel):
    """시그널 값 객체(Value Object) 스키마 - Signals 모델과 동기화"""

    id: Optional[int] = None
    ticker: str
    strategy: Optional[str] = None
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    close_price: Optional[float] = None
    action: Literal["buy", "sell", "hold"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    probability: Optional[str] = None
    result_description: Optional[str] = None
    report_summary: Optional[str] = None
    ai_model: Optional[str] = "OPENAI_O4MINI"
    senario: Optional[str] = None
    good_things: Optional[str] = None
    bad_things: Optional[str] = None
    chart_pattern: Optional[ChartPattern] = None  # 차트 패턴 정보

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Signals 모델 객체를 SignalValueObject로 변환"""
        return cls.model_validate(obj)

    @classmethod
    def to_orm(cls, value_object) -> Signals:
        """SignalValueObject를 Signals 모델 객체로 변환"""
        data = value_object.model_dump(exclude={"id"})
        return Signals(**data)


class GetSignalByDateResponse(BaseModel):
    """
    Response schema for getting signals by date.
    Contains a list of signals for the specified date.
    """

    signals: List[SignalJoinTickerResponse]
