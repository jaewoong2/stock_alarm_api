import ccxt
import pandas as pd
import requests
import logging

from myapi.domain.backdata.backdata_schema import (
    Article,
    ArticleResponseType,
    SentimentResponse,
    SentimentResponseType,
)
from myapi.repositories.trading_repository import TradingRepository
from myapi.utils.config import Settings

# 거래소 주소 목록 (예시, 실제 데이터로 대체 필요)
EXCHANGE_ADDRESSES = {
    "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g",  # Binance 예시 주소
    "3EyjEjqUzLfGx2b9LTDQAlbLHTCjXjQ87v",  # Coinbase 예시 주소
}


class BackDataService:
    BASE_URL = "https://api.coinone.co.kr/public/v2"

    def __init__(self, settings: Settings, trading_repository: TradingRepository):
        self.NEWS_API_KEY = settings.NEWS_API_KEY
        self.trading_repository = trading_repository

    def get_ohlcv_data(
        self,
        symbol: str = "BTC/KRW",
        timeframe: str = "1d",
        limit: int = 300,
    ):
        """
        Binance 거래소에서 OHLCV 데이터를 가져와서 Pandas DataFrame으로 반환하는 함수입니다.
        에러 발생 시 예외를 raise합니다.
        """
        try:
            exchange = ccxt.binance()
            ohlcv = exchange.fetch_ohlcv(
                symbol=symbol, timeframe=timeframe, limit=limit
            )
            # 컬럼 이름을 모두 소문자로 하여 일관성 유지
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except ccxt.BaseError as e:
            logging.exception("CCXT 에러 발생:")
            raise
        except Exception as e:
            logging.exception("예상치 못한 에러 발생 in get_ohlcv_data:")
            raise

    def get_btc_news(self, symbol: str = "Crypto") -> ArticleResponseType:
        """
        NewsAPI를 사용하여 Bitcoin 관련 뉴스를 가져옵니다.
        에러 발생 시 예외를 raise합니다.
        """
        NEWS_API_URL = "https://newsapi.org/v2/everything"
        yesterday_date = (pd.Timestamp.now() - pd.Timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        params = {
            "q": f"bitcoin OR btc OR {symbol}",
            "apiKey": self.NEWS_API_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "from": yesterday_date,
        }
        try:
            response = requests.get(NEWS_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                return [Article(**article) for article in articles]
            else:
                raise ValueError(
                    f"Failed to fetch news: {data.get('message', 'Unknown error')}"
                )
        except requests.exceptions.RequestException as e:
            logging.exception("Request exception in get_btc_news:")
            raise

    def get_sentiment_data(self) -> SentimentResponseType:
        """
        Alternative.me의 Crypto Fear & Greed Index API를 사용하여 시장 감성 데이터를 가져옵니다.
        에러 발생 시 예외를 raise합니다.
        """
        url = "https://api.alternative.me/fng/"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return SentimentResponse(**data)
        except requests.exceptions.RequestException as e:
            logging.exception("Request exception in get_sentiment_data:")
            raise
        except ValueError as e:
            logging.exception("JSON 파싱 에러 in get_sentiment_data:")
            raise

    def get_coinone_candles(
        self, quote_currency="KRW", target_currency="BTC", interval="1m", size=200
    ):
        """
        코인원 API에서 N분봉 캔들 데이터를 가져와 DataFrame으로 반환합니다.
        에러 발생 시 예외를 raise합니다.
        """
        url = f"https://api.coinone.co.kr/public/v2/chart/{quote_currency}/{target_currency}"
        params = {"interval": interval, "size": size}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("result") != "success":
                error_code = data.get("error_code", "Unknown error code")
                logging.error(f"Coinone API error: {error_code}")
                raise ValueError(f"Coinone API error: {error_code}")
            df = pd.DataFrame(data["chart"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
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
        except requests.exceptions.RequestException as e:
            logging.exception("Request exception in get_coinone_candles:")
            raise

    def get_market_data(self, symbol: str = "BTC"):
        """
        코인원 API에서 지정 심볼에 대한 마켓 데이터를 가져옵니다.
        에러 발생 시 예외를 raise합니다.
        """
        url = f"{self.BASE_URL}/ticker_new/KRW/{symbol}?additional_data=false"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if "errorCode" in data and data["errorCode"] != "0":
                raise ValueError(f"코인원 API 오류: {data['errorCode']}")
            tickers = data.get("tickers")
            if not tickers or len(tickers) == 0:
                raise ValueError("No tickers data found")
            ticker = tickers[0]
            return {
                "symbol": symbol,
                "price": float(ticker["last"]),
                "high": float(ticker["high"]),
                "low": float(ticker["low"]),
                "volume": float(ticker["target_volume"]),
            }
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logging.exception("Error fetching market data:")
            raise

    def check_buy_condition(self, target, ma, price, high):
        """
        매수 조건을 확인합니다.
        :param target: 목표 가격
        :param ma: 이동평균 값
        :param price: 현재 가격
        :param high: 오늘의 최고가
        :return: 매수 가능 여부 (bool)
        """
        return price >= target and high <= target * 1.02 and price >= ma

    def check_sell_condition(self, symbol: str, ma_days: int = 5):
        """
        매도 조건을 확인합니다.
        :param symbol: 코인 티커
        :param ma_days: 이동평균선 계산에 필요한 일수
        :return: 매도 가능 여부 (bool)
        에러 발생 시 예외를 raise합니다.
        """
        df = self.get_ohlcv_data(symbol, limit=ma_days + 1)
        if df is None or len(df) < ma_days:
            raise ValueError("Not enough OHLCV data to compute moving average")
        ma = df["close"].rolling(window=ma_days).mean().iloc[-1]
        price = df["close"].iloc[-1]
        return price < ma
