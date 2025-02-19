import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import uuid

import requests

from myapi.domain.trading.coinone_schema import OrderRequest
from myapi.utils.config import Settings, row_to_dict


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

    # Public API Methods
    def get_candlestick(
        self,
        quote_currency: str,
        target_currency: str,
        interval: str = "5m",
        limit: int = 72,
    ) -> Dict[str, Any]:
        url = (
            f"{self.base_url}/public/v2/candlestick/{quote_currency}/{target_currency}"
        )
        params = {"interval": interval, "limit": limit}
        response = self.session.get(url, params=params)
        return response.json()

    def get_ticker_all(self, quote_currency: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/ticker_all/{quote_currency}"
        response = self.session.get(url)
        return response.json()

    def get_orderbook(
        self, quote_currency: str, target_currency: str
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/orderbook/{quote_currency}/{target_currency}"
        response = self.session.get(url)
        return response.json()

    def get_trades(
        self, quote_currency: str, target_currency: str, size: int = 200
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/trades/{quote_currency}/{target_currency}"
        params = {"size": size}
        response = self.session.get(url, params=params)
        return response.json()

    def get_markets(self, quote_currency: str, target_currency: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/markets/{quote_currency}/{target_currency}"
        response = self.session.get(url)
        return response.json()

    # Private API Methods
    def _get_nonce(self) -> str:
        return str(int(time.time() * 1000))

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

        response = self.session.post(url, headers=headers)

        return response.json()

    def get_balances(self) -> Dict[str, Any]:
        return self._private_post("/v2.1/account/balance", {})

    def get_balance(self, currency: List[str]) -> Dict[str, Any]:
        return self._private_post("/v2.1/account/balance", {"currencies": currency})

    def place_order(self, payload: OrderRequest) -> Dict[str, Any]:
        data = row_to_dict(payload)

        return self._private_post("/v2.1/order", data)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return self._private_post("/v2.1/orders/cancel", {"order_id": order_id})

    def cancel_all_orders(self, target_currency: str) -> Dict[str, Any]:
        return self._private_post(
            "/v2.1/orders/cancel-all", {"target_currency": target_currency}
        )

    def get_fees_all(self) -> Dict[str, Any]:
        return self._private_post("/v2.1/fees/all", {})

    def get_fee(self, target_currency: str) -> Dict[str, Any]:
        return self._private_post("/v2.1/fees/", {"target_currency": target_currency})
