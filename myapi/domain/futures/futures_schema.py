from decimal import Decimal
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Union

from myapi.domain.ai.ai_schema import ActionType


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
        return (
            "Current Market Data"
            f"Last: {self.last}, "
            f"High: {self.high}, "
            f"Low: {self.low}, "
            f"Open: {self.open}, "
            f"Close: {self.close}"
        )


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
            f"HA Analysis: {ha_analysis}"
        )


class FutureInvestMentOrderParams(BaseModel):
    # if positionSide == LONG: has takeProfit
    # if positionSide == SHORT: has stopPrice
    positionSide: str
    takeProfit: Optional[float]
    stopPrice: Optional[float]


class FuturesOrderRequest(BaseModel):
    symbol: str
    quantity: float
    price: float
    tp_price: float
    sl_price: float
    leverage: int


class FuturesActionType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    CLOSE_ORDER = "CLOSE_ORDER"


class FutureOpenAISuggestion(BaseModel):
    action: FuturesActionType
    reasoning: str
    order: FuturesOrderRequest
    detaild_summary: str


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
