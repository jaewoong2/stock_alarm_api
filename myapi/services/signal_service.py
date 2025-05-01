from datetime import date, timedelta
from typing import List, Optional, Literal, Union, cast
import pandas as pd
import yfinance as yf
import pandas_ta as ta  # Ensure 'ta' is installed via pip install ta
import requests
import datetime as dt

# from nltk.sentiment import SentimentIntensityAnalyzer

from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import (
    TechnicalSignal,
    Strategy,
    FundamentalData,
    NewsHeadline,
)


class SignalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.DEFAULT_UNIVERSE: str = "SPY,QQQ,AAPL,MSFT,TSLA"
        self.START_DAYS_BACK: int = 365
        # self.sia = SentimentIntensityAnalyzer()

    def fetch_ohlcv(self, ticker: str, start: Optional[date] = None):
        """Download adjusted daily OHLCV data for the given ticker."""
        if start is None:
            start = date.today() - timedelta(days=self.START_DAYS_BACK)
        df = yf.download(
            ticker,
            start=start.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        return df

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append technical indicators to the DataFrame using pandas-ta direct calls."""
        df = df.copy()

        # 1. Simple Moving Averages
        df["SMA_10"] = ta.sma(df["Close"], length=10)
        df["SMA_50"] = ta.sma(df["Close"], length=50)

        # 2. Relative Strength Index
        df["RSI_14"] = ta.rsi(df["Close"], length=14)

        # 3. Bollinger Bands (lower, middle, upper)
        bb = ta.bbands(df["Close"], length=20, std=2)
        # bb is a DataFrame with columns ["BBL_20_2.0","BBM_20_2.0","BBU_20_2.0", …]
        if bb is None or bb.empty:
            # raise ValueError("Bollinger Bands calculation failed.")
            return df

        df["BBL_20_2.0"] = bb["BBL_20_2.0"]
        df["BBM_20_2.0"] = bb["BBM_20_2.0"]
        df["BBU_20_2.0"] = bb["BBU_20_2.0"]

        # 4. MACD (line, histogram, signal)
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)

        if macd is None or macd.empty:
            return df
        # ['MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9']
        df["MACD_12_26_9"] = macd["MACD_12_26_9"]
        df["MACD_HIST"] = macd["MACDh_12_26_9"]
        df["MACD_SIGNAL"] = macd["MACDs_12_26_9"]

        return df

    def evaluate_signals(
        self, df: pd.DataFrame, strategies: List[Strategy]
    ) -> List[TechnicalSignal]:
        """Return triggered technical signals for the last candle."""
        last, prev = df.iloc[-1], df.iloc[-2]
        out: List[TechnicalSignal] = []

        if "PULLBACK" in strategies:
            cond = (
                last["Close"] <= last["SMA10"] * 1.005
                and last["Close"] >= last["SMA50"]
            )
            out.append(
                TechnicalSignal(
                    strategy="PULLBACK",
                    triggered=cond,
                    details={"close": last["Close"], "sma10": last["SMA10"]},
                )
            )

        if "OVERSOLD" in strategies:
            cond = last["RSI14"] < 30 and last["Close"] < last["BBL"]
            out.append(
                TechnicalSignal(
                    strategy="OVERSOLD",
                    triggered=cond,
                    details={"RSI14": last["RSI14"], "BBL": last["BBL"]},
                )
            )

        if "MACD_LONG" in strategies:
            cond = prev["MACD_H"] < 0 < last["MACD_H"]
            out.append(
                TechnicalSignal(
                    strategy="MACD_LONG",
                    triggered=cond,
                    details={"prev_macd_h": prev["MACD_H"], "macd_h": last["MACD_H"]},
                )
            )

        return out

    def fetch_fundamentals(self, ticker: str) -> FundamentalData:
        """Fetch fundamental data for the given ticker."""
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        trailing_pe = info.get("trailingPE")

        # EPS Surprise: 최근 분기 기준
        cal = None
        if hasattr(tk, "calendar"):
            cal = (
                pd.DataFrame(tk.calendar)
                if isinstance(tk.calendar, dict)
                else tk.calendar
            )
        if cal is not None and not cal.empty:
            est, act = cal.loc["Earnings Estimate"][0], cal.loc["EPS"][0]
            # Convert est to a scalar value if it's a Series
            est_val = est.iloc[0] if isinstance(est, pd.Series) else est
            act_val = act.iloc[0] if isinstance(act, pd.Series) else act
            surprise_pct = (
                (act_val - est_val) / abs(est_val) * 100
                if not pd.isna(est_val) and est_val != 0
                else None
            )
        else:
            surprise_pct = None

        # Revenue YoY
        fin = tk.quarterly_financials.T if hasattr(tk, "quarterly_financials") else None
        if fin is not None and len(fin) >= 5:
            rev_growth = (
                (fin["Total Revenue"].iloc[0] - fin["Total Revenue"].iloc[4])
                / fin["Total Revenue"].iloc[4]
                * 100
            )
        else:
            rev_growth = None

        return FundamentalData(
            trailing_pe=trailing_pe,
            eps_surprise_pct=surprise_pct,
            revenue_growth=rev_growth,
        )

    def _get_sentiment(self, text: str) -> Literal["positive", "neutral", "negative"]:
        """Analysis sentiment of the given text."""
        # score = self.sia.polarity_scores(text)["compound"]
        # if score > 0.05:
        #     return "positive"
        # if score < -0.05:
        #     return "negative"
        return "neutral"

    def fetch_news(
        self, ticker: str, days_back: int = 3, max_items: int = 5
    ) -> List[NewsHeadline]:
        """Fetch recent news headlines for the given ticker."""
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": ticker,
            "language": "en",
            "from": (dt.date.today() - dt.timedelta(days=days_back)).isoformat(),
            "sortBy": "relevancy",
            "pageSize": max_items,
            "apiKey": self.settings.NEWS_API_KEY,
        }

        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        articles = r.json().get("articles", [])

        return [
            NewsHeadline(
                title=a["title"],
                url=a["url"],
                sentiment="neutral",
                # sentiment=self._get_sentiment(a["title"]),
            )
            for a in articles
        ]

    def analyze_stock(self, ticker: str, strategies: List[Strategy]) -> dict:
        """Perform a complete analysis of the stock including price, technicals, fundamentals and news."""
        # 주가 데이터 및 기술적 지표 가져오기
        df = self.fetch_ohlcv(ticker)

        if df is None:
            raise ValueError(f"Failed to fetch data for ticker: {ticker}")

        # Handle case when df is empty
        if df.empty:
            return {
                "ticker": ticker,
                "last_price": None,
                "price_change_pct": None,
                "technical_signals": [],
                "fundamentals": self.fetch_fundamentals(ticker),
                "news": self.fetch_news(ticker),
                "last_updated": dt.datetime.now().isoformat(),
            }

        df_with_indicators = self.add_indicators(df)

        # 기술적 시그널 평가
        signals = self.evaluate_signals(df_with_indicators, strategies)

        # 기본적 지표 가져오기
        fundamentals = self.fetch_fundamentals(ticker)

        # 뉴스 가져오기
        news = self.fetch_news(ticker)

        # 최종 분석 결과 반환
        return {
            "ticker": ticker,
            "last_price": df.iloc[-1].Close,
            "price_change_pct": (
                ((df.iloc[-1].Close / df.iloc[-2].Close) - 1) * 100
                if len(df) > 1
                else None
            ),
            "technical_signals": signals,
            "fundamentals": fundamentals,
            "news": news,
            "last_updated": dt.datetime.now().isoformat(),
        }
