import pandas as pd
import requests


class BackDataService:
    BASE_URL = "https://api.coinone.co.kr/public/v2"

    # 📌 코인원 API에서 1분봉 캔들 데이터 가져오기
    def get_coinone_candles(
        self, quote_currency="KRW", target_currency="BTC", interval="1m", size=200
    ):
        url = f"https://api.coinone.co.kr/public/v2/chart/{quote_currency}/{target_currency}"
        params = {"interval": interval, "size": size}
        response = requests.get(url, params=params)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return None

        data = response.json()

        # 응답 구조 확인
        if data.get("result") != "success":
            print(f"API Error: {data.get('error_code')}")
            return None

        # 데이터프레임 변환
        df = pd.DataFrame(data["chart"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # 컬럼 이름 변경 및 숫자로 변환
        df.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "target_volume": "volume",
            },
            inplace=True,
        )

        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df

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
