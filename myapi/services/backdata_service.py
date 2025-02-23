import pandas as pd
import requests

from myapi.domain.backdata.backdata_schema import (
    Article,
    ArticleResponseType,
    ErrorResponse,
    SentimentResponse,
    SentimentResponseType,
)
from myapi.utils.config import Settings


# 38af960b93d04842847b618aa17796ee
class BackDataService:
    def __init__(self, settings: Settings):
        self.NEWS_API_KEY = settings.NEWS_API_KEY

    BASE_URL = "https://api.coinone.co.kr/public/v2"

    # Function to fetch Bitcoin news from NewsAPI

    def get_btc_news(self) -> ArticleResponseType:
        NEWS_API_URL = "https://newsapi.org/v2/everything"

        params = {
            "q": "bitcoin OR btc",  # Search query for Bitcoin-related news
            "apiKey": self.NEWS_API_KEY,
            "language": "en",  # English news only (optional)
            "sortBy": "publishedAt",  # Sort by latest
            "pageSize": 3,  # Limit to 10 articles
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
