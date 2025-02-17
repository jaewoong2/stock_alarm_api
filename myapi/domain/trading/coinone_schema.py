import datetime
from typing import List, Optional
from pydantic import BaseModel


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
