from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class FuturesTradeException(Exception):
    """선물 거래 관련 기본 예외 클래스"""

    def __init__(
        self,
        message: str,
        error_code: str = "FUTURES_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 변환"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class OrderCreationException(FuturesTradeException):
    """주문 생성 실패 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        symbol: str = "",
        order_details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = {
            "symbol": symbol,
            "order_details": order_details or {},
            "original_error": str(original_error) if original_error else None,
        }
        super().__init__(
            message=message, error_code="ORDER_CREATION_FAILED", details=details
        )
        self.symbol = symbol
        self.order_details = order_details
        self.original_error = original_error


class OrderCancellationException(FuturesTradeException):
    """주문 취소 실패 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        order_id: str = "",
        symbol: str = "",
        original_error: Optional[Exception] = None,
    ):
        details = {
            "order_id": order_id,
            "symbol": symbol,
            "original_error": str(original_error) if original_error else None,
        }
        super().__init__(
            message=message, error_code="ORDER_CANCELLATION_FAILED", details=details
        )
        self.order_id = order_id
        self.symbol = symbol
        self.original_error = original_error


class PositionCloseException(FuturesTradeException):
    """포지션 종료 실패 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        symbol: str = "",
        position_type: str = "",
        position_size: Optional[float] = None,
        original_error: Optional[Exception] = None,
    ):
        details = {
            "symbol": symbol,
            "position_type": position_type,
            "position_size": position_size,
            "original_error": str(original_error) if original_error else None,
        }
        super().__init__(
            message=message, error_code="POSITION_CLOSE_FAILED", details=details
        )
        self.symbol = symbol
        self.position_type = position_type
        self.position_size = position_size
        self.original_error = original_error


class InvalidSuggestionException(FuturesTradeException):
    """제안 데이터가 유효하지 않을 때 발생하는 예외"""

    def __init__(self, message: str, suggestion_data: Optional[Dict[str, Any]] = None):
        details = {"suggestion_data": suggestion_data or {}}
        super().__init__(
            message=message, error_code="INVALID_SUGGESTION", details=details
        )
        self.suggestion_data = suggestion_data


class ExchangeConnectionException(FuturesTradeException):
    """거래소 연결 오류 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        exchange: str = "binance",
        endpoint: str = "",
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        details = {
            "exchange": exchange,
            "endpoint": endpoint,
            "request_data": request_data or {},
            "response_data": response_data or {},
            "original_error": str(original_error) if original_error else None,
        }
        super().__init__(
            message=message, error_code="EXCHANGE_CONNECTION_ERROR", details=details
        )
        self.exchange = exchange
        self.endpoint = endpoint
        self.request_data = request_data
        self.response_data = response_data
        self.original_error = original_error


class InsufficientBalanceException(FuturesTradeException):
    """잔액 부족 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        required_amount: float = 0.0,
        available_amount: float = 0.0,
        currency: str = "USDC",
    ):
        details = {
            "required_amount": required_amount,
            "available_amount": available_amount,
            "currency": currency,
            "deficit": required_amount - available_amount,
        }
        super().__init__(
            message=message, error_code="INSUFFICIENT_BALANCE", details=details
        )
        self.required_amount = required_amount
        self.available_amount = available_amount
        self.currency = currency


class LeverageConfigurationException(FuturesTradeException):
    """레버리지 설정 오류 시 발생하는 예외"""

    def __init__(
        self,
        message: str,
        symbol: str = "",
        requested_leverage: int = 0,
        max_allowed_leverage: int = 0,
        original_error: Optional[Exception] = None,
    ):
        details = {
            "symbol": symbol,
            "requested_leverage": requested_leverage,
            "max_allowed_leverage": max_allowed_leverage,
            "original_error": str(original_error) if original_error else None,
        }
        super().__init__(
            message=message, error_code="LEVERAGE_CONFIGURATION_ERROR", details=details
        )
        self.symbol = symbol
        self.requested_leverage = requested_leverage
        self.max_allowed_leverage = max_allowed_leverage
        self.original_error = original_error


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(FuturesTradeException)
    async def futures_trade_exception_handler(
        request: Request, exc: FuturesTradeException
    ):
        return JSONResponse(
            status_code=400,
            content={"message": str(exc), "type": exc.__class__.__name__},
        )

    @app.exception_handler(ExchangeConnectionException)
    async def exchange_connection_exception_handler(
        request: Request, exc: ExchangeConnectionException
    ):
        return JSONResponse(
            status_code=503,  # Service Unavailable
            content={"message": str(exc), "type": "ExchangeConnectionError"},
        )

    @app.exception_handler(OrderCreationException)
    async def order_creation_exception_handler(
        request: Request, exc: OrderCreationException
    ):
        return JSONResponse(
            status_code=400,
            content={"message": str(exc), "type": "OrderCreationError"},
        )
