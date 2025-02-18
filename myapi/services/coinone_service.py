import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

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

    def get_markets(self, quote_currency: str) -> Dict[str, Any]:
        url = f"{self.base_url}/public/v2/markets/{quote_currency}"
        response = self.session.get(url)
        return response.json()

    # Private API Methods
    def _get_nonce(self) -> str:
        return str(int(time.time() * 1000))

    def _sign_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data["nonce"] = self._get_nonce()
        encoded = urlencode(data)
        signature = hmac.new(
            self.secret_key.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha512
        ).hexdigest()
        data["signature"] = signature
        return data

    def _private_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        data["access_token"] = self.api_key
        data = self._sign_request(data)
        response = self.session.post(url, data=data)
        return response.json()

    def get_balances(self) -> Dict[str, Any]:
        return self._private_post("/v2.1/balances/", {})

    def get_balance(self, currency: str) -> Dict[str, Any]:
        return self._private_post("/v2.1/balance/", {"currency": currency})

    def place_order(
        self, market: str, side: str, price: str, qty: str, ord_type: str = "limit"
    ) -> Dict[str, Any]:
        data = {
            "market": market,
            "side": side,
            "price": price,
            "qty": qty,
            "ord_type": ord_type,
        }
        return self._private_post("/v2.1/orders/", data)

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
