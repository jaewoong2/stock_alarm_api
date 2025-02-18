import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class CoinoneOrderResponse(BaseModel):
    """
    /v2.1/order 엔드포인트 응답 모델
    """

    result: str
    error_code: str
    order_id: Optional[str] = None  # 오류 발생 시 order_id가 없을 수도 있음


class Balance(BaseModel):
    """
    /v2.1/account/balance 응답 내 개별 잔고 항목 모델
    """

    available: str
    limit: str
    average_price: str
    currency: str


class CoinoneBalanceResponse(BaseModel):
    """
    /v2.1/account/balance 엔드포인트 응답 모델
    """

    result: str
    error_code: str
    balances: List[Balance]


class PlaceOrderResponse(BaseModel):
    """
    place_order method 응답 모델
    """

    result: str
    error_code: str
    krw_balance: str
    btc_balance: str

    class Config:
        extra = "allow"


class GetTradingInformationResponseModel(BaseModel):
    """
    get_trading_information method 응답 모델
    """

    id: int
    timestamp: datetime.datetime
    symbol: str
    action: str
    amount: float
    reason: str
    summary: str
    openai_prompt: str
    execution_krw: float
    execution_crypto: float
    status: str

    @field_validator("amount", "execution_krw", "execution_crypto", mode="before")
    @classmethod
    def convert_to_float(cls, value):
        try:
            if value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid float value: {value}")


# -----------------------
# Pydantic Response Models
# -----------------------


class Candlestick(BaseModel):
    open: str
    close: str
    high: str
    low: str
    volume: str
    timestamp: int


class CandlestickResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    candles: List[Dict[str, Any]] = Field(..., description="List of candlestick data")


class TickerResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    tickers: Dict[str, Any]


class OrderBookEntry(BaseModel):
    price: str
    qty: str


class OrderBookResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]


class TradesResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    quote_currency: str
    target_currency: str
    transactions: List[Dict[str, Any]]


class MarketResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    markets: List[Dict[str, Any]]


class BalanceResponse(BaseModel):
    result: str
    error_code: str
    server_time: int
    balances: Dict[str, Any]
