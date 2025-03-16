from typing import List, Optional
from pandas import DataFrame
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum

from myapi.domain.backdata.backdata_schema import (
    ArticleResponseType,
    SentimentResponseType,
)
from myapi.domain.trading.coinone_schema import (
    ActiveOrdersResponse,
    Balance,
    CoinoneBalanceResponse,
    GetTradingInformationResponseModel,
    OrderBookResponse,
)

Base = declarative_base()


class TechnicalIndicators(BaseModel):
    MA_short_9: float
    MA_long_21: float
    MA_long_120: float
    RSI_14: float
    MACD: float
    MACD_Signal: float
    BB_MA: float
    BB_Upper: float
    BB_Lower: float
    ADX: float
    ATR_14: float
    Latest_Close: float
    Latest_Open: float
    volatility: float
    high: float

    @property
    def description(self) -> str:
        return f"""
            MA_short_9: {self.MA_short_9}
            MA_long_21: {self.MA_long_21}
            MA_long_120: {self.MA_long_120}
            RSI_14: {self.RSI_14}
            MACD: {self.MACD}
            MACD_Signal: {self.MACD_Signal}
            BB_MA: {self.BB_MA}
            BB_Upper: {self.BB_Upper}
            BB_Lower: {self.BB_Lower}
            ADX: {self.ADX}
            ATR_14: {self.ATR_14}
            Latest_Close: {self.Latest_Close}
            Latest_Open: {self.Latest_Open}
            volatility: {self.volatility}
            high: {self.high}
        """


class ActionEnum(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ExecutionStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True)
    # 결정/실행 시각
    timestamp = Column(DateTime, nullable=False)
    # 종목 (예: BTC, ETH 등)
    symbol = Column(String(10), nullable=False)
    # BUY, SELL, HOLD 중 하나
    action = Column(Enum(ActionEnum), nullable=False)
    # 매수/매도 수량
    amount = Column(Float, nullable=False)

    action_string = Column(Text, nullable=False)
    # 모델이 준 설명 또는 요약본
    reason = Column(Text, nullable=True)
    # 거래 내역에 대한 요약
    summary = Column(Text, nullable=True)
    # 입력된 데이터 (시세, 전략, 뉴스 등 중요한 데이터)
    openai_prompt = Column(Text, nullable=True)
    # 체결된 KRW 가격 (매매 완료 후)
    execution_krw = Column(Float, nullable=True)
    # 체결된 Crypto 가격 (매매 완료 후)
    execution_crypto = Column(Float, nullable=True)
    # 체결 성공/실패 여부
    status = Column(Enum(ExecutionStatus), nullable=False)

    # 입력된 데이터 (시세, 전략, 뉴스 등 중요한 데이터)
    action_string = Column(Text, nullable=True)


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

    class Config:
        arbitrary_types_allowed = True


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
