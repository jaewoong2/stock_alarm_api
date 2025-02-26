import yfinance as yf
import pandas as pd
import pandas_ta as ta
from fredapi import Fred
from datetime import date, datetime, timedelta
from twitter_scraper import get_tweets

from forex_python.converter import CurrencyRates
from newsapi import NewsApiClient

from myapi.utils.config import Settings


class StockService:
    def __init__(self, settings: Settings):
        # FRED API 설정
        self.fred = Fred(api_key=settings.FRED_API_KEY)
        self.currency_rates = CurrencyRates()
        self.newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)

    def get_historical_data(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """최근 N일치 주가 데이터를 가져오기"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        ticker_data = yf.Ticker(ticker)
        df = ticker_data.history(start=start_date, end=end_date)

        return df[["Open", "High", "Low", "Close", "Volume"]].reset_index()

    def get_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산"""
        df_ta = df.copy()
        df_ta["SMA_20"] = ta.sma(df["Close"], length=20)
        df_ta["RSI"] = ta.rsi(df["Close"], length=14)
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd is not None:
            df_ta["MACD"] = macd["MACD_12_26_9"]

        return df_ta[["Date", "Close", "SMA_20", "RSI", "MACD"]].dropna()

    def get_dxy(self):
        # 실제 DXY는 여러 환율의 가중 평균이지만, 예시로 USD/EUR 환율을 사용합니다.
        try:
            return self.currency_rates.get_rate("USD", "EUR")
        except Exception as e:
            print(f"Error fetching DXY data: {e}")
            return 103.45  # 에러 발생 시 기본값 반환

    def get_economic_data(self) -> dict:
        """FRED에서 경제 데이터 가져오기"""
        try:
            fed_rate = self.fred.get_series_latest_release("FEDFUNDS")
            cpi = self.fred.get_series_latest_release("CPIAUCSL")
            dxy = self.get_dxy()

            return {
                "Federal Funds Rate": float(fed_rate.iloc[-1]),
                "CPI": float(cpi.iloc[-1]),
                "DXY": dxy,
            }
        except Exception as e:
            print(f"Error fetching economic data: {e}")
            return {}

    def get_market_sentiment(self, symbol: str, query_date: date):
        """시장 심리 데이터 (VIX + X 감성 + 뉴스)"""
        # VIX 데이터 (실제)
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="1d")
        vix_value = vix_data["Close"].iloc[-1] if not vix_data.empty else 18.5

        next_day = query_date + timedelta(days=1)
        search_query = (
            f"${symbol} since:{query_date.isoformat()} until:{next_day.isoformat()}"
        )
        try:
            tweets = get_tweets(search_query, pages=10)
            return tweets

        except Exception as e:
            sentiment = {"positive": 50, "negative": 50}  # 오류 시 기본값

        # 뉴스 데이터 (실제)
        try:
            news = self.newsapi.get_everything(
                q=f"{symbol} OR Nasdaq",
                language="en",
                sort_by="publishedAt",
                page_size=5,
            )
            latest_news = (
                news["articles"][0]["title"] if news["articles"] else "No recent news"
            )
        except Exception as e:
            latest_news = f"News API 실패: {str(e)}"

        return {"VIX": float(vix_value), "X_Sentiment": sentiment, "News": latest_news}
