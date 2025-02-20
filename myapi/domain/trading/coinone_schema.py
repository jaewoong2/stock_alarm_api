import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


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


# 1. 주문 요청에 대한 Pydantic 모델 정의
class OrderRequest(BaseModel):
    side: str = Field(..., description="매수/매도 분류 (BUY: 매수, SELL: 매도)")
    quote_currency: str = Field(..., description="마켓 기준 통화 (예: KRW)")
    target_currency: str = Field(..., description="주문하려는 종목의 심볼 (예: BTC)")
    type: str = Field(
        ...,
        description="주문 유형 (LIMIT, MARKET, STOP_LIMIT)",
    )
    # 옵션 필드 (필요 주문 유형에 따라 선택)
    price: Optional[str] = Field(
        None, description="주문 가격 (지정가, 예약가에서 필수)"
    )
    qty: Optional[str] = Field(
        None, description="주문 수량 (지정가, 예약가, 시장가 매도에서 필수)"
    )
    amount: Optional[str] = Field(None, description="주문 총액 (시장가 매수에서 필수)")
    post_only: Optional[bool] = Field(
        None, description="Post Only 주문 여부 (지정가에서 필수)"
    )
    limit_price: Optional[str] = Field(
        None, description="체결 가격의 최대/최소 한도 (시장가 주문 시)"
    )
    trigger_price: Optional[str] = Field(
        None, description="예약가 주문이 실행되는 가격 (감시가, 예약가에서 필수)"
    )

    @model_validator(mode="after")
    def check_required_fields(self) -> "OrderRequest":
        order_type = self.type
        side = self.side

        if order_type in ["LIMIT", "STOP_LIMIT"]:
            if self.price is None:
                raise ValueError("지정가/예약가 주문 시 'price' 값이 필요합니다.")
            if order_type == "STOP_LIMIT" and self.trigger_price is None:
                raise ValueError("예약가 주문 시 'trigger_price' 값이 필요합니다.")
            if self.qty is None:
                raise ValueError("지정가/예약가 주문 시 'qty' 값이 필요합니다.")
        if order_type == "MARKET":
            if side == "BUY" and self.amount is None:
                raise ValueError("시장가 매수 주문 시 'amount' 값이 필요합니다.")
            if side == "SELL" and self.qty is None:
                raise ValueError("시장가 매도 주문 시 'qty' 값이 필요합니다.")
        return self
