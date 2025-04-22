from decimal import Decimal
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Literal, Optional, Dict, Union

from myapi.domain.trading.trading_schema import TechnicalIndicators
from myapi.utils.futures_technical import TradingSignalResult


class TradingSignal(BaseModel):
    signal: Optional[str] = None  # "long", "short", 또는 None
    confidence: float = 0.0  # 0~1 사이의 신뢰도 점수
    contributing_factors: List[str] = []  # 신호에 기여한 요인 리스트
    explanation: Optional[str] = None  # 신호에 대한 설명

    class Config:
        arbitrary_types_allowed = True


class FuturesVO(BaseModel):
    id: Union[int, None] = None
    symbol: str
    price: Union[float, int]
    quantity: Union[float, int]
    side: str
    timestamp: Union[str, datetime]
    position_type: str
    take_profit: Union[float, int, None] = None  # <--- None 허용
    stop_loss: Union[float, int, None] = None  # <--- None 허용
    status: str
    order_id: str
    parent_order_id: str
    client_order_id: Optional[str]

    class Config:
        from_attributes = True


class FuturesBase(BaseModel):
    symbol: str
    price: float
    quantity: float
    side: str
    order_id: str
    client_order_id: Optional[str]
    parent_order_id: str


class FuturesCreate(FuturesBase):
    pass


class FuturesResponse(FuturesBase):
    id: int
    timestamp: datetime
    position_type: Optional[str]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    status: Optional[str]

    class Config:
        from_attributes = True


class PivotPoints(BaseModel):
    pivot: float
    support1: float
    resistance1: float
    support2: float
    resistance2: float


class BollingerBands(BaseModel):
    middle_band: float
    upper_band: float
    lower_band: float

    @property
    def description(self):
        """
        Returns a description about Bollinger Bands.
        """
        return (
            f"Middle Band: {self.middle_band}, "
            f"Upper Band: {self.upper_band}, "
            f"Lower Band: {self.lower_band}"
        )


class MACDResult(BaseModel):
    macd: float
    signal: float
    histogram: float
    crossover: bool
    crossunder: bool


class Ticker(BaseModel):
    last: float
    bid: Optional[float]
    ask: Optional[float]
    high: Optional[float]
    low: Optional[float]
    open: Optional[float]
    close: Optional[float]

    @property
    def description(self):
        """
        Returns a description about ticker.
        """
        return f"Current Symbol Price: {self.close}"


class TechnicalAnalysis(BaseModel):
    support: Optional[float]
    resistance: Optional[float]
    pivot: Optional[float]
    support2: Optional[float]
    resistance2: Optional[float]
    bollinger_bands: BollingerBands
    fibonacci_levels: Dict[str, float]  # 동적 키로 인해 Dict 유지
    macd_divergence: Optional[bool]
    macd_crossover: Optional[bool]
    macd_crossunder: Optional[bool]
    rsi_divergence: Optional[bool]
    volume_trend: Optional[str]
    ha_analysis: Optional[Dict]
    logic_ema_stoch: Optional[str]
    logic_sma_ribon: Optional[str]
    signals: Optional[List[TradingSignal]]
    total_signal: TradingSignalResult
    hammer_explain: str

    @property
    def description(self):
        """
        Returns a description about all of the technical analysis.
        """

        fibonacci_levels = ", ".join(
            [f"{key}: {value}" for key, value in self.fibonacci_levels.items()]
        )

        ha_analysis = (
            ", ".join([f"{key}: {value}" for key, value in self.ha_analysis.items()])
            if self.ha_analysis
            else "No Heikin Ashi Analysis"
        )

        return (
            f"Support: {self.support}, Resistance: {self.resistance}, "
            f"Pivot: {self.pivot}, Second_Support: {self.support2}, Second_Resistance: {self.resistance2}"
            f"Bollinger Bands: {self.bollinger_bands.description}, "
            f"Fibonacci Levels: {fibonacci_levels}, "
            f"MACD Divergence: {self.macd_divergence}, "
            f"MACD Crossover: {self.macd_crossover}, "
            f"MACD Crossunder: {self.macd_crossunder}, "
            f"RSI Divergence: {self.rsi_divergence}, "
            f"Volume Trend: {self.volume_trend}, "
            f"HA Analysis: {ha_analysis}, "
            f"EMA200 Trend Rider: {self.logic_ema_stoch}, "
            f"TrendRibbon Scalper: {self.logic_sma_ribon}, "
            f"Total Signal: {self.total_signal.explanation}, "
            f"Detected Hammer Pattern: {self.hammer_explain}, "
        )


class FutureInvestMentOrderParams(BaseModel):
    # if positionSide == LONG: has takeProfit
    # if positionSide == SHORT: has stopPrice
    positionSide: str
    takeProfit: Optional[float]
    stopPrice: Optional[float]


class FuturesActionType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    CLOSE_ORDER = "CLOSE_ORDER"


class FuturesOrderRequest(BaseModel):
    action: FuturesActionType
    symbol: str
    quantity: float
    price: float
    tp_price: float
    sl_price: float
    leverage: int


class FutureOpenAISuggestion(BaseModel):
    detaild_summary: str
    first_order: FuturesOrderRequest
    second_order: FuturesOrderRequest
    third_order: FuturesOrderRequest


class FuturesConfigRequest(BaseModel):
    # margin_type: str = "ISOLATED"
    symbol: str = "BTCUSDT"
    leverage: int = 2
    margin_type: str = "ISOLATED"


class TechnicalAnalysisRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    size: int = 500


class FuturesClosePositionRequest(BaseModel):
    symbol: str
    quantity: Optional[float] = None


class FuturesBalancePositionInfo(BaseModel):
    position: str  # "LONG" or "SHORT"
    position_amt: float
    entry_price: float
    leverage: Optional[int]
    unrealized_profit: float

    @property
    def description(self):
        return (
            f"[{self.position}]: {self.position_amt} Position Amount, "
            f"{self.entry_price} Entry Price, "
            f"{self.leverage} Leverage, "
            f"{self.unrealized_profit} Unrealized Profit"
        )


class FuturesBalance(BaseModel):
    symbol: str
    free: int | float | Decimal
    used: int | float | Decimal
    total: int | float | Decimal

    positions: Optional[FuturesBalancePositionInfo]

    @property
    def available(self):
        return float(self.free) - float(self.used)

    @property
    def description(self):
        if self.positions:
            if self.positions.position_amt > 0:
                return self.positions.description

        return f"[{self.symbol}]: {self.available} Available For Trading"


class FuturesBalances(BaseModel):
    balances: list[FuturesBalance]

    @property
    def description(self):
        return "\n".join([balance.description for balance in self.balances])


class ExecuteFuturesRequest(BaseModel):
    symbol: str = "BTCUSDT"
    limit: int = 500
    timeframe: str = "1h"
    image_timeframe: str = "1h"
    longterm_timeframe: str = "4h"
    additional_context: Optional[str] = ""


class ExecuteFutureOrderRequest(BaseModel):
    symbol: str
    suggestion: FuturesOrderRequest
    target_balance: Optional[FuturesBalance]


class PlaceFuturesOrder(BaseModel):
    id: str
    symbol: str
    origQty: float
    order_id: str
    clientOrderId: str
    side: str
    avgPrice: Optional[float]
    cumQuote: Optional[float]
    triggerPrice: Optional[float]
    stopPrice: Optional[float]


class PlaceFuturesOrderResponse(BaseModel):
    buy_order: Optional[PlaceFuturesOrder]
    sell_order: Optional[PlaceFuturesOrder]
    tp_order: PlaceFuturesOrder
    sl_order: PlaceFuturesOrder


class HeikinAshiAnalysis(BaseModel):
    total_candles: int
    num_bull: int
    num_bear: int
    num_doji: int
    consecutive_bull: int
    consecutive_bear: int
    avg_upper_tail: float
    avg_lower_tail: float
    interpretation: Optional[str] = None


# SimplifiedFundingRate 클래스 정의
class SimplifiedFundingRate(BaseModel):
    symbol: str
    funding_rate: float
    timestamp: int
    datetime: str | datetime
    mark_price: float
    next_funding_time: str

    # 펀딩 비율을 기반으로 롱 포지션 과다 여부 판단
    @property
    def is_long_overcrowded(self) -> bool:
        """펀딩 비율이 0.01(1%) 이상이면 롱 포지션이 과다하다고 판단"""
        return self.funding_rate > 0.01

    # 펀딩 비율을 기반으로 숏 포지션 과다 여부 판단
    @property
    def is_short_overcrowded(self) -> bool:
        """펀딩 비율이 -0.01(-1%) 이하이면 숏 포지션이 과다하다고 판단"""
        return self.funding_rate < -0.01

    # 거래 신호 생성
    @property
    def trade_signal(self) -> str:
        """롱/숏 과다 여부에 따라 매수/매도 신호 생성"""
        if self.is_long_overcrowded:
            return "SHORT"  # 롱 과다 -> 반전 매도 신호
        elif self.is_short_overcrowded:
            return "LONG"  # 숏 과다 -> 반전 매수 신호
        return "HOLD"  # 중립

    @property
    def description(self):
        """
        Returns a description about the funding rate.
        """
        return (
            f"Funding Rate: {self.funding_rate},\n"
            f"Mark Price: {self.mark_price},\n "
            f"Trade Signal: {self.trade_signal},\n"
            f"Overcrowded Long: {self.is_long_overcrowded},\n"
            f"Overcrowded Short: {self.is_short_overcrowded},\n"
        )

    class Config:
        from_attributes = True


class MeanTechnicalIndicators(BaseModel):
    MA_short_9: float
    MA_long_21: float
    MA_long_120: float
    RSI_14: float
    MACD: float
    MACD_Signal: float
    BB_Upper: float
    BB_Lower: float
    ADX: float
    ATR_14: float
    Latest_Close: float
    Latest_Open: float
    volatility: float
    high: float
    close_mean: float
    rsi_slope: float
    ma9_slope: float
    plus_di_avg: float
    minus_di_avg: float
    volume_avg: float

    @property
    def description(self) -> str:
        return f"""
        Total Mean Technical Indicators:
            MA_short_9: {self.MA_short_9}
            MA_long_21: {self.MA_long_21}
            MA_long_120: {self.MA_long_120}
            RSI_14: {self.RSI_14}
            MACD: {self.MACD}
            MACD_Signal: {self.MACD_Signal}
            BB_Upper: {self.BB_Upper}
            BB_Lower: {self.BB_Lower}
            ADX: {self.ADX}
            ATR_14: {self.ATR_14}
            Latest_Close: {self.Latest_Close}
            Latest_Open: {self.Latest_Open}
            volatility: {self.volatility}
            high: {self.high}
            close_mean: {self.close_mean}
            rsi_slope: {self.rsi_slope}
            ma9_slope: {self.ma9_slope}
            plus_di_avg: {self.plus_di_avg}
            minus_di_avg: {self.minus_di_avg}
            volume_avg: {self.volume_avg}
        """

    @property
    def inetrpretation(self):
        # 4) 값에 따라 동적으로 해석해 주는 로직
        interpretation_data = {}

        # (1) RSI: 과매수/과매도 구간 판별
        if self.RSI_14 > 70:
            rsi_comment = "과매수 구간(RSI > 70) - 매수세가 강하거나 과열일 수 있음"
        elif self.RSI_14 < 30:
            rsi_comment = "과매도 구간(RSI < 30) - 매도세가 강거나 저평가일 수 있음"
        else:
            rsi_comment = "중립 구간(30 ≤ RSI ≤ 70)"
        interpretation_data["RSI_14"] = f"RSI 평균: {self.RSI_14}, 해석: {rsi_comment}"

        # (2) +DI vs -DI
        if self.plus_di_avg > self.minus_di_avg:
            dmi_comment = (
                f"상승 추세 우위(+DI {self.plus_di_avg} > -DI {self.minus_di_avg}). "
                "가격 상승 모멘텀이 우세할 수 있음."
            )
        elif self.plus_di_avg < self.minus_di_avg:
            dmi_comment = (
                f"하락 추세 우위(+DI {self.plus_di_avg} < -DI {self.minus_di_avg}). "
                "가격 하락 모멘텀이 우세할 수 있음."
            )
        else:
            dmi_comment = (
                f"균형 상태(+DI {self.plus_di_avg} ≈ -DI {self.minus_di_avg}). "
                "뚜렷한 추세 우위 없음."
            )
        interpretation_data["DMI"] = dmi_comment

        # (3) MACD와 시그널
        if self.MACD > 0:
            if self.MACD > self.MACD_Signal:
                macd_comment = "양(+) MACD가 시그널 상회 -> 상승 추세가 강할 가능성"
            else:
                macd_comment = "양(+) MACD가 시그널 하회 -> 단기 조정/둔화 가능성"
        else:
            if self.MACD < self.MACD_Signal:
                macd_comment = "음(-) MACD가 시그널 아래 -> 하락 추세 강화 가능성"
            else:
                macd_comment = (
                    "음(-) MACD가 시그널 위 -> 하락 추세 둔화/반등 시도 가능성"
                )
        interpretation_data["MACD"] = (
            f"MACD 평균: {self.MACD}, MACD 시그널 평균: {self.MACD_Signal}, 해석: {macd_comment}"
        )

        # (4) ADX 해석 (추세 강도 확인)
        if self.ADX < 20:
            adx_comment = "약한 추세(ADX < 20). 뚜렷한 방향성 부족."
        elif self.ADX < 40:
            adx_comment = "보통 수준 추세(20 ≤ ADX < 40)."
        else:
            adx_comment = "강한 추세(ADX ≥ 40). 추세 방향성을 적극 고려."
        interpretation_data["ADX"] = f"ADX 평균: {self.ADX}, 해석: {adx_comment}"

        # (5) ATR(14) 해석 (단순 변동성 체크)
        if self.ATR_14 > 2.0:
            atr_comment = "고변동성 구간(ATR > 2.0)으로 변동폭이 큼."
        else:
            atr_comment = "보통/저변동성 구간(ATR ≤ 2.0)."
        interpretation_data["ATR_14"] = f"ATR 평균: {self.ATR_14}, 해석: {atr_comment}"

        # Combine all interpretation data into a single string
        interpretations = "\n".join(
            f"{key}: {value}" for key, value in interpretation_data.items()
        )

        return interpretations


# ...existing code...


class TechnicalIndicatorsResponse(BaseModel):
    analysis: TechnicalAnalysis
    technical_indicators: (
        TechnicalIndicators  # 이미 정의된 TechnicalIndicators 클래스 사용
    )
    mean_indicators: MeanTechnicalIndicators

    class Config:
        arbitrary_types_allowed = True


# ▶ **동적 타임프레임** 모델
class TFCfg(BaseModel):
    major: List[str] = ["4h", "1h"]  # 대세 판단용
    minor: List[str] = ["15m", "5m"]  # 단기 판단용
    # minor[0] = 더 큰 단기 TF, minor[1] = 가장 작은 단기 TF


class IndiCfg(BaseModel):
    ema_fast: int = 50
    ema_slow: int = 200
    ema_minor: int = 20
    rsi_len: int = 14
    atr_len: int = 14
    adx_len: int = 14
    bb_len: int = 20
    bb_std: float = 2.0
    don_len: int = 20
    lrs_len: int = 14


class RiskCfg(BaseModel):
    atr_sl_mult: float = 1.0
    atr_tp_mult: float = 1.8
    vol_filter: float = 1.2


class BotCfg(BaseModel):
    symbol: str = "BTC/USDT"
    indi: IndiCfg = IndiCfg()
    risk: RiskCfg = RiskCfg()
    llm_snapshot_small: int = 16  # 5m·15m 최근 봉 수
    llm_snapshot_big: int = 1  # 1h·4h 최근 봉 수


class QueueMessage(BaseModel):
    body: str = ""
    path: str = "futures/execute"
    method: Literal["POST", "GET"] = "GET"
    query_string_parameters: Dict[str, str] = {}

    @property
    def message(self):
        """
        Returns a description about the queue message.
        """
        return {
            "body": self.body,
            "resource": "/{proxy+}",
            "path": f"/{self.path}",
            "httpMethod": self.method,
            "isBase64Encoded": False,
            "pathParameters": {"proxy": self.path},
            "queryStringParameters": self.query_string_parameters,
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, sdch",
                "Accept-Language": "ko",
                "Accept-Charset": "utf-8",
            },
            "requestContext": {
                "path": f"/{self.path}",
                "resourcePath": "/{proxy+}",
                "httpMethod": self.method,
            },
        }


class ResumptionRequestData(BaseModel):
    symbol: str = "BTCUSDT"
    limit: int = 500
    timeframes: TFCfg = TFCfg()  # 요청마다 원하는 TF 전달
    snapshot_small: int = 30  # optional
    snapshot_big: int = 60  # optional
    use_llm: bool = True


class SignalResult(BaseModel):
    major_pass: bool
    ichimoku_pass: bool
    resumption_pass: bool
    macd_pass: bool
    rsi_pass: bool
    price_pass: bool
    volume_pass: bool

    final_side: Literal["LONG", "SHORT", "NONE"]
