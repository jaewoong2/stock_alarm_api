from typing import List, Optional
from pandas import DataFrame
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

from myapi.domain.backdata.backdata_schema import (
    ArticleResponseType,
    SentimentResponseType,
)
from myapi.domain.trading.coinone_schema import (
    ActiveOrdersResponse,
    CoinoneBalanceResponse,
    GetTradingInformationResponseModel,
    OrderBookResponse,
)
from myapi.domain.trading.trading_model import ActionEnum


class TechnicalIndicators(BaseModel):
    MA_short_9: Optional[float]
    MA_long_21: Optional[float]
    MA_long_120: Optional[float]
    RSI_14: Optional[float]
    MACD: Optional[float]
    MACD_Signal: Optional[float]
    BB_Upper: Optional[float]
    BB_Lower: Optional[float]
    ADX: Optional[float]
    ATR_14: Optional[float]
    Latest_Close: Optional[float]
    Latest_Open: Optional[float]
    volatility: Optional[float]
    high: Optional[float]

    model_config = ConfigDict(extra="allow")  # 🚀 추가 필드 허용

    @property
    def description(self) -> str:
        return f"""
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
        """


# "When price level could go up or down"을 위한 하위 구조
class PriceDirection(BaseModel):
    condition: str = Field(
        ..., description="가격이 오르거나 내릴 조건"
    )  # 가격이 오르거나 내릴 조건
    price_level: float = Field(..., description="예상 가격 레벨")  # 예상 가격 레벨
    timeframe: str = Field(
        ..., description="예상 시간 범위 (예: 'within 1-2 hours')"
    )  # 예상 시간 범위 (예: "within 1-2 hours")


class TechnicalAnalysisResponse(BaseModel):
    price_movement: str = Field(
        ..., description="Predict of price movement"
    )  # Description of price movement within the next 1-2 hours
    stop_loss: float = Field(
        ..., description="Stop-loss price level"
    )  # Stop-loss price level
    stop_loss_reason: Optional[str] = Field(
        None, description="Reason for stop-loss (optional)"
    )  # Reason for stop-loss (optional)
    buy_line: float = Field(
        ..., description="Buy entry price level"
    )  # Buy entry price level
    buy_line_reason: Optional[str] = Field(
        None, description="Reason for buy entry (optional)"
    )  # Reason for buy entry (optional)
    take_profit: float = Field(
        ..., description="Take-profit price level"
    )  # Take-profit price level
    take_profit_reason: Optional[str] = Field(
        None, description="Reason for take-profit (optional)"
    )  # Reason for take-profit (optional)
    price_up: PriceDirection = Field(
        ..., description="Scenario when the price moves up"
    )  # Scenario when the price moves up
    price_down: PriceDirection = Field(
        ..., description="Scenario when the price moves down"
    )  # Scenario when the price moves down
    disclaimer: Optional[str] = Field(
        None, description="Additional cautionary notes (optional)"
    )  # Additional cautionary notes (optional)
    users_action: str = Field(
        ..., description="Immediate action the user should take"
    )  # Immediate action the user should take


# {"action": action, "z_score": latest_z, "hedge_ratio": hedge_ratio}
class ArbitrageSignal(BaseModel):
    action: str
    z_score: float
    hedge_ratio: float

    @property
    def description(self) -> str:
        return f"[ArbitrageSignal With Bitcoin - {self.action}]: Z-Score: {self.z_score}, Hedge Ratio: {self.hedge_ratio}"


class BackdataInformations(BaseModel):
    trading_info: GetTradingInformationResponseModel
    market_data: dict
    candles_info: DataFrame
    orderbook: OrderBookResponse
    balances: CoinoneBalanceResponse
    news: ArticleResponseType
    sentiment: SentimentResponseType
    active_orders: ActiveOrdersResponse
    current_time: str
    technical_indicators: TechnicalIndicators
    plot_image_path: Optional[str]
    arbitrage_signal: ArbitrageSignal

    class Config:
        arbitrary_types_allowed = True


# FastAPI Pydantic 스키마
class TransactionBase(BaseModel):
    id: Optional[str]
    currency: str
    qty: Optional[float] = None
    avarage_price: Optional[float] = None
    total_price: float
    fee: Optional[float] = None
    timestamp: datetime
    action: ActionEnum = ActionEnum.HOLD
    trade_id: str = ""
    order_id: str = ""


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: int

    class Config:
        from_attributes = True  # Pydantic V2에서는 orm_mode 대신 from_attributes 사용
