import ccxt
import pandas as pd
import requests

from myapi.domain.backdata.backdata_schema import (
    Article,
    ArticleResponseType,
    ErrorResponse,
    SentimentResponse,
    SentimentResponseType,
)
from myapi.repositories.trading_repository import TradingRepository
from myapi.utils.config import Settings

import pandas as pd

# 거래소 주소 목록 (예시, 실제 데이터로 대체 필요)
EXCHANGE_ADDRESSES = {
    "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g",  # Binance 예시 주소
    "3EyjEjqUzLfGx2b9LTDQAlbLHTCjXjQ87v",  # Coinbase 예시 주소
}


# 38af960b93d04842847b618aa17796ee
class BackDataService:
    def __init__(self, settings: Settings, trading_repository: TradingRepository):
        self.NEWS_API_KEY = settings.NEWS_API_KEY
        self.trading_repository = trading_repository

    BASE_URL = "https://api.coinone.co.kr/public/v2"

    # Function to fetch Bitcoin news from NewsAPI

    def get_ohlcv_data(
        self,
        symbol: str = "BTC/KRW",
        timeframe: str = "1d",
        limit: int = 300,
    ):
        """
        Binance 거래소에서 OHLCV 데이터를 가져와서 Pandas DataFrame으로 반환하는 함수입니다.

        [Parameters]
        symbol: str
            조회할 거래쌍(티커)입니다.
            예시: "BTC/USDT", "ETH/USDT", "BTC/KRW"
        limit: int
            데이터의 개수 입니다.
        timeframe: str
            데이터의 시간 간격입니다.
            예시: "1d" (일별 데이터), "1h" (시간별 데이터), "5m" (5분 단위 데이터)

        [Returns]
        df: pandas.DataFrame
            변환된 OHLCV 데이터로, 'Date' 열이 인덱스로 설정되어 있으며,
            'Open', 'High', 'Low', 'Close', 'Volume' 컬럼을 포함합니다.

        [Example]
        >>> # BTC/USDT 거래쌍의 2022년 1월 1일 이후 1시간 간격 데이터 조회
        >>> data = get_ohlcv_data("BTC/USDT", "2022-01-01T00:00:00Z", "1h")
        """
        exchange = ccxt.binance()

        ohlcv = exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        # 가져온 OHLCV 데이터를 Pandas DataFrame으로 변환
        # 각 컬럼은 "Timestamp", "Open", "High", "Low", "Close", "Volume" 순으로 배열됨
        df = pd.DataFrame(
            ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
        )

        # 'Timestamp' 컬럼을 datetime 형식으로 변환하여 'Date' 컬럼에 저장 (밀리초 단위임)
        df["Date"] = pd.to_datetime(df["Timestamp"], unit="ms")

        # 'Date' 컬럼을 DataFrame의 인덱스로 설정하여 시간 순으로 정렬된 데이터를 생성
        df.set_index("Date", inplace=True)

        # 불필요한 'Timestamp' 컬럼 삭제
        del df["Timestamp"]

        # 최종적으로 변환된 DataFrame 반환
        return df

    def get_btc_news(self, symbol: str = "Crypto") -> ArticleResponseType:
        NEWS_API_URL = "https://newsapi.org/v2/everything"

        yesterday = pd.Timestamp.now() - pd.Timedelta(days=1)
        yesterday_date = yesterday.strftime("%Y-%m-%d")

        params = {
            "q": f"bitcoin OR btc OR {symbol}",  # Search query for Bitcoin-related news
            "apiKey": self.NEWS_API_KEY,
            "language": "en",  # English news only (optional)
            "sortBy": "publishedAt",  # Sort by latest
            "pageSize": 10,  # Limit to 10 articles
            "from": yesterday_date,
        }

        try:
            response = requests.get(NEWS_API_URL, params=params)
            response.raise_for_status()  # Raise an error for bad status codes
            data = response.json()

            # Extract articles from the response
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                # Convert raw articles to Pydantic Article models
                return [Article(**article) for article in articles]
            else:
                return ErrorResponse(
                    error="Failed to fetch news",
                    message=data.get("message", "Unknown error"),
                )
        except requests.exceptions.RequestException as e:
            return ErrorResponse(error="Request failed", message=str(e))

    def get_sentiment_data(self) -> SentimentResponseType:
        """
        Alternative.me의 Crypto Fear & Greed Index API를 사용하여 시장 감성 데이터를 가져옵니다.
        무료로 제공되며, 자세한 내용은 https://alternative.me/crypto/fear-and-greed-index/ 참고.
        """
        url = "https://api.alternative.me/fng/"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Convert raw JSON to Pydantic model
            return SentimentResponse(**data)
        except requests.exceptions.RequestException as e:
            return ErrorResponse(error="Request failed", message=str(e))
        except ValueError as e:
            return ErrorResponse(error="Invalid JSON response", message=str(e))

    # 📌 코인원 API에서 N분봉 캔들 데이터 가져오기
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

    def check_buy_condition(self, target, ma, price, high):
        """
        매수 조건을 확인합니다.
        :param coin: 코인 티커
        :param target: 목표 가격
        :param ma: 이동평균 값
        :param price: 현재 가격
        :param high: 오늘의 최고가
        :return: 매수 가능 여부 (bool)
        """
        if price >= target and high <= target * 1.02 and price >= ma:
            return True
        return False

    def check_sell_condition(self, symbol: str, ma_days: int = 5):
        """
        매도 조건을 확인합니다.
        :param symbol: 코인 티커
        :param ma_days: 이동평균선 일수
        :return: 매도 가능 여부 (bool)
        """
        df = self.get_ohlcv_data(symbol, limit=ma_days + 1)

        if df is None or len(df) < ma_days:
            return False

        ma = df["close"].rolling(window=ma_days).mean().iloc[-1]
        price = df["close"].iloc[-1]

        # 현재 가격이 이동평균선 아래로 떨어지면 매도
        if price < ma:
            return True

        return False
