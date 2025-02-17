import pandas as pd
import requests


class BackDataService:
    BASE_URL = "https://api.coinone.co.kr/public/v2"

    # 📌 코인원 API에서 1m, 5m, 15m, 1h 데이터 수집
    def get_coinone_candles(self, market="btc", interval="minute1", count=200):
        url = f"{self.BASE_URL}/candles/{interval}/{market}"
        params = {"count": count}
        response = requests.get(url, params=params)
        data = response.json()

        # 데이터프레임으로 변환
        df = pd.DataFrame(data["candles"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("timestamp", inplace=True)
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

        # 📌 이동평균선(MA) 계산

    def _calculate_moving_average(self, df, short_window=9, long_window=21):
        df[f"MA{short_window}"] = df["close"].rolling(window=short_window).mean()
        df[f"MA{long_window}"] = df["close"].rolling(window=long_window).mean()
        return df

    # 📌 RSI 계산
    def _calculate_rsi(self, df, window=14):
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / (loss + 1e-10)  # 0으로 나누는 오류 방지
        df["RSI"] = 100 - (100 / (1 + rs))
        return df

    # 📌 MACD 계산
    def _calculate_macd(self, df):
        short_ema = df["close"].ewm(span=12, adjust=False).mean()
        long_ema = df["close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = short_ema - long_ema
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        return df
