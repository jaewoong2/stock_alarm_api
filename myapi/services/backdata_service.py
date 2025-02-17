import requests


class BackDataService:
    BASE_URL = "https://api.coinone.co.kr/public/v2"

    def get_market_data(self, symbol: str = "BTC"):
        url = f"{self.BASE_URL}/ticker_new/KRW/{symbol}?additional_data=false"
        response = requests.get(url).json()

        ticker = response["tickers"][0]

        if "errorCode" in response and response["errorCode"] != "0":
            raise ValueError(f"코인원 API 오류: {response['errorCode']}")

        return {
            "symbol": symbol,
            "price": float(ticker["last"]),
            "high": float(ticker["high"]),
            "low": float(ticker["low"]),
            "volume": float(ticker["target_volume"]),
        }
