import base64
import datetime
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional
import uuid

import requests

from myapi.domain.trading.coinone_schema import (
    ActiveOrdersResponse,
    CancelOrderResponse,
    CoinoneBalanceResponse,
    CompleteOrderResponse,
    OrderBookResponse,
    OrderRequest,
)
from myapi.utils.config import Settings


class CoinoneService:
    def __init__(
        self,
        settings: Settings,
        base_url: str = "https://api.coinone.co.kr",
    ):
        self.api_key = settings.COIN_ACCESS_TOKEN
        self.secret_key = settings.COIN_SECRET_KEY
        self.base_url = base_url
        self.session = requests.Session()

    def get_completed_order(
        self,
        size: int,
        target_currency: str,
        minutes: int = 30,
        quote_currency: str = "KRW",
    ):
        now = datetime.datetime.now(datetime.timezone.utc)
        to_ts = int(now.timestamp() * 1000)
        from_ts = int((now - datetime.timedelta(minutes=minutes)).timestamp() * 1000)
        data = {
            "size": size,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "target_currency": target_currency,
            "quote_currency": quote_currency,
        }
        result = self._private_post("/v2.1/order/completed_orders", data)
        return CompleteOrderResponse(**result)

    # Public API Methods
    def get_candlestick(
        self,
        quote_currency: str,
        target_currency: str,
        interval: str = "15m",
        size: int = 200,
    ) -> Dict[str, Any]:
        url = f"https://api.coinone.co.kr/public/v2/chart/{quote_currency}/{target_currency}"
        params = {"interval": interval, "size": size}

        """
        with
        Resources are automatically released when the with block exits
        Cleanup happens even if an exception occurs
        Prevents memory leaks and resource exhaustion
        More robust error handling
        """
        with self.session.get(url, params=params) as response:
            response.raise_for_status()
            return response.json()

    def get_ticker_all(self, quote_currency: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/ticker_all/{quote_currency}"

        with self.session.get(url) as response:
            response.raise_for_status()
            return response.json()

    def get_orderbook(self, quote_currency: str, target_currency: str, size: int = 10):
        url = f"{self.base_url}/public/v2/orderbook/{quote_currency}/{target_currency}?size={size}"

        with self.session.get(url) as response:
            response.raise_for_status()
            data = response.json()
            return OrderBookResponse(**data)

    def get_trades(
        self, quote_currency: str, target_currency: str, size: int = 200
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/trades/{quote_currency}/{target_currency}"
        params = {"size": size}

        with self.session.get(url, params=params) as response:
            return response.json()

    def get_ticker(self, ticker: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/ticker_new/KRW/{ticker}?additional_data=false"
        with self.session.get(url) as response:
            response.raise_for_status()
            return response.json()

    def get_markets(self, quote_currency: str, target_currency: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/markets/{quote_currency}/{target_currency}"
        with self.session.get(url) as response:
            return response.json()

    def _get_signature(self, encoded_payload: bytes) -> str:
        """
        인코딩된 페이로드로 HMAC-SHA512 서명을 생성합니다.
        """
        signature = hmac.new(
            self.secret_key.encode("utf-8"), encoded_payload, hashlib.sha512
        )
        return signature.hexdigest()

    def _create_headers(self, encoded_payload: bytes) -> dict:
        """
        API 호출에 필요한 헤더를 생성합니다.
        """
        return {
            "Content-type": "application/json",
            "X-COINONE-PAYLOAD": encoded_payload,
            "X-COINONE-SIGNATURE": self._get_signature(encoded_payload),
        }

    def _sign_request(self, payload: dict):
        """
        페이로드에 nonce를 추가하고 base64로 인코딩합니다.
        """
        payload["nonce"] = str(uuid.uuid4())
        dumped_json = json.dumps(payload)
        return base64.b64encode(dumped_json.encode("utf-8"))

    def _private_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        data["access_token"] = self.api_key

        encoded_payload = self._sign_request(payload=data)
        headers = self._create_headers(encoded_payload)

        with self.session.post(url, headers=headers) as response:
            return response.json()

    def get_balances(self) -> Dict[str, Any]:
        return self._private_post("/v2.1/account/balance", {})

    def get_balance(self, currency: List[str]):
        balance = self._private_post("/v2.1/account/balance", {"currencies": currency})

        if balance.get("result") == "error":
            return CoinoneBalanceResponse(
                balances=[], error_code="No balance found", result="error"
            )

        if not balance.get("balances"):
            return CoinoneBalanceResponse(
                balances=[], error_code="No balance found", result="error"
            )

        return CoinoneBalanceResponse(**balance)

    def place_order(self, payload: OrderRequest):
        return self._private_post("/v2.1/order", payload.model_dump())

    def cancel_order(self, order_id: str, target_currency: str):
        result = self._private_post(
            "/v2.1/order/cancel",
            {
                "order_id": order_id,
                "quote_currency": "KRW",
                "target_currency": target_currency,
            },
        )

        return CancelOrderResponse(**result)

    def cancel_all_orders(self, target_currency: str) -> Dict[str, Any]:
        return self._private_post(
            "/v2.1/orders/cancel-all", {"target_currency": target_currency}
        )

    def get_fees_all(self) -> Dict[str, Any]:
        return self._private_post("/v2.1/fees/all", {})

    def get_fee(self, target_currency: str) -> Dict[str, Any]:
        return self._private_post("/v2.1/fees/", {"target_currency": target_currency})

    def get_active_orders(self, target_currency: str):
        orders = self._private_post(
            "/v2.1/order/active_orders",
            {"target_currency": target_currency, "quote_currency": "KRW"},
        )

        if orders.get("result") == "error":
            return ActiveOrdersResponse(
                error_code="No active orders found", result="error", active_orders=[]
            )

        if not orders.get("active_orders"):
            return ActiveOrdersResponse(
                error_code="No active orders found", result="error", active_orders=[]
            )

        return ActiveOrdersResponse(**orders)
