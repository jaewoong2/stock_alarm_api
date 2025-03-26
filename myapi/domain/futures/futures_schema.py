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

    class Config:
        from_attributes = True


class FuturesBase(BaseModel):
    symbol: str
    price: float
    quantity: float
    side: str
    order_id: str
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
        return f"[{self.symbol}]: {self.available} Available"


class FuturesBalances(BaseModel):
    balances: list[FuturesBalance]


class ExecuteFuturesRequest(BaseModel):
    symbol: str = "BTCUSDT"
    limit: int = 500
    timeframe: str = "1h"


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
