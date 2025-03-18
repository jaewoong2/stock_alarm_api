import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TriggerResponse(BaseModel):
    status: str | None
    message: str

    indicators: Dict | None = None


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

    @property
    def description(self) -> str:
        return f"[currecny: {self.currency}] Available: {self.available} {self.currency} (Avg Price: {self.average_price})"


class CoinoneBalanceResponse(BaseModel):
    """
    /v2.1/account/balance 엔드포인트 응답 모델
    """

    result: str
    error_code: str
    balances: List[Balance]

    @property
    def description(self) -> str:
        return ", ".join([balance.description for balance in self.balances])


class PlaceOrderResponse(BaseModel):
    """
    place_order method 응답 모델
    """

    result: str
    error_code: str
    krw_balance: str
    crypto_balance: str

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
    reason: Optional[str]
    summary: str
    openai_prompt: str
    execution_krw: float
    execution_crypto: float
    status: str
    action_string: str

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

    @property
    def description(self) -> str:
        return f"Price: {self.price}, Qty: {self.qty}"


class OrderBookResponse(BaseModel):
    result: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]

    model_config = ConfigDict(extra="ignore")

    @property
    def description(self) -> str:
        bids = [bid.description for bid in self.bids]
        asks = [ask.description for ask in self.asks]

        return f"Bids: {bids}, Asks: {asks}"


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

    order_id: Optional[str] = Field(  # 취소 주문 시 필요한 필드
        None, description="취소할 주문 ID (취소 주문 시 필수)"
    )

    @model_validator(mode="after")
    def check_required_fields(self) -> "OrderRequest":
        order_type = self.type
        side = self.side

        if order_type in ["LIMIT", "STOP_LIMIT"]:
            if side not in ["BUY", "SELL"]:
                return self

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


class ActiveOrder(BaseModel):
    order_id: str
    type: str
    side: str
    quote_currency: str
    target_currency: str
    price: str
    original_qty: str
    remain_qty: str
    executed_qty: str
    canceled_qty: str
    fee: str
    fee_rate: str
    average_executed_price: str
    ordered_at: int
    is_triggered: Optional[bool] = None
    trigger_price: Optional[str] = None
    triggered_at: Optional[int] = None

    @property
    def description(self) -> str:
        return f"""
        Order ID: {self.order_id}
        Type: {self.type}
        Side: {self.side}
        Quote Currency: {self.quote_currency}
        Target Currency: {self.target_currency}
        Price: {self.price}
        Original Qty: {self.original_qty}
        Remain Qty: {self.remain_qty}
        Executed Qty: {self.executed_qty}
        Canceled Qty: {self.canceled_qty}
        Fee: {self.fee}
        Fee Rate: {self.fee_rate}
        Average Executed Price: {self.average_executed_price}
        Ordered At: {self.ordered_at}
        Is Triggered: {self.is_triggered}
        Trigger Price: {self.trigger_price}
        Triggered At: {self.triggered_at}
        """

    model_config = ConfigDict(extra="ignore")


class ActiveOrdersResponse(BaseModel):
    result: str
    error_code: str
    active_orders: List[ActiveOrder]

    model_config = ConfigDict(extra="ignore")


class CancelOrderResponse(BaseModel):
    result: str
    error_code: str
    order_id: str
    price: str
    qty: str
    remain_qty: str
    side: str
    original_qty: str
    traded_qty: str
    canceled_qty: str
    fee: str
    fee_rate: str
    avg_price: str
    canceled_at: int
    ordered_at: int

    model_config = ConfigDict(extra="ignore")


class CompletedOrder(BaseModel):
    trade_id: str = Field(
        ..., description="체결 ID (예: '0e2bb80f-1e4d-11e9-9ec7-00e04c3600d1')"
    )
    order_id: str = Field(
        ..., description="주문 식별 ID (예: '0e30219d-1e4d-11e9-9ec7-00e04c3600d7')"
    )
    quote_currency: str = Field(..., description="마켓 기준 통화 (예: 'KRW')")
    target_currency: str = Field(..., description="주문 체결된 종목 (예: 'BTC')")
    order_type: str = Field(
        ..., description='주문 방식 (Enum: "LIMIT", "MARKET", "STOP_LIMIT")'
    )
    is_ask: bool = Field(
        ..., description="체결된 주문의 매도 주문 여부 (true: 매도, false: 매수)"
    )
    is_maker: bool = Field(..., description="maker 주문 여부 (예: true)")
    price: str = Field(..., description="체결된 주문 금액 (숫자형 문자열)")
    qty: str = Field(..., description="체결된 주문 수량 (숫자형 문자열)")
    timestamp: int = Field(..., description="주문 체결 시점의 타임스탬프 (밀리초 단위)")
    fee_rate: str = Field(..., description="체결된 주문 수수료율 (숫자형 문자열)")
    fee: str = Field(..., description="체결된 주문의 수수료 (숫자형 문자열)")
    fee_currency: str = Field(..., description='수수료 지불 통화 (예: "KRW")')


class CompleteOrderResponse(BaseModel):
    result: str = Field(..., description='정상 반환 시 "success", 에러 발생 시 "error"')
    error_code: str = Field(
        ...,
        description="에러 발생 시 에러코드 반환, 성공인 경우 0 반환 (숫자형 문자열)",
    )
    completed_orders: List[CompletedOrder] = Field(
        ..., description="배열 형태의 체결 주문 목록"
    )

    class Config:
        from_attributes = True  # Pydantic V2에서 ORM 모델 변환을 위해 사용
