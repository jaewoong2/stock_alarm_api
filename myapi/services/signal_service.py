from datetime import date, timedelta
import logging
from typing import List, Optional, Literal, Union, cast
from numpy import tri
import pandas as pd
from regex import T
import yfinance as yf
import pandas_ta as ta  # Ensure 'ta' is installed via pip install ta
import requests
import datetime as dt

from pandas_datareader import data as pdr  # pip install pandas_datareader

# from nltk.sentiment import SentimentIntensityAnalyzer

from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import (
    TechnicalSignal,
    Strategy,
    FundamentalData,
    NewsHeadline,
)

logger = logging.getLogger(__name__)


def flatten_price_columns(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    """
    * (Price, <ticker>, <field>) → <field>
    * (<ticker>, <field>)       → <field>
    * (<field>)                 → 그대로
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df  # 이미 평탄

    # 3-level: ['Price', 'AAPL', 'Close' …]
    if df.columns.nlevels == 3:
        df = df.droplevel(0, axis=1)  # 'Price' 날리고 2-level 로

    # 2-level: ['AAPL', 'Close' …]  또는 ['SPY', 'Adj Close']
    if df.columns.nlevels == 2:
        # 하나뿐인 Ticker는 자동 추출, 복수면 매개변수로 전달받은 ticker 로 선택
        level_vals = df.columns.get_level_values(0)
        unique_tickers = level_vals.unique()

        if len(unique_tickers) == 1 or ticker is None:
            df = df.droplevel(0, axis=1)  # 맨 위 티커 레벨 제거
        else:
            result = df.xs(ticker, level=0, axis=1)  # 원하는 티커만 선택
            # Convert to DataFrame if it's a Series
            if isinstance(result, pd.Series):
                df = pd.DataFrame(result)
            else:
                df = result

    df.columns.name = None  # 컬럼명 계층 이름 제거
    return df


class SignalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.DEFAULT_UNIVERSE: str = "SPY,QQQ,AAPL,MSFT,TSLA"
        self.START_DAYS_BACK: int = 365
        # self.sia = SentimentIntensityAnalyzer()

    def market_ok(self, index_ticker="SPY") -> bool:
        """시장 필터: 지수 종가가 50일 SMA 위면 True"""
        df = yf.download(index_ticker, period="6mo", auto_adjust=True, progress=False)

        if df is None:
            return False

        if df.empty:
            return False

        df["SMA50"] = ta.sma(df["Close"], length=50)
        return bool((df["Close"].iloc[-1] > df["SMA50"].iloc[-1])[index_ticker])

    def rs_ok(self, ticker: str, benchmark="SPY", lookback_weeks=13) -> bool:
        """종목 상대강도 필터: 최근 13주 수익률 랭크가 상위 30%면 True"""
        lookback_days = lookback_weeks * 5
        t_df = yf.download(
            ticker, period=f"{lookback_days+5}d", auto_adjust=True, progress=False
        )
        b_df = yf.download(
            benchmark, period=f"{lookback_days+5}d", auto_adjust=True, progress=False
        )

        if t_df is None or b_df is None:
            return False

        if t_df.empty or b_df.empty:
            return False

        rel = (t_df["Close"] / b_df["Close"]).dropna()
        rs_rank = rel.pct_change(lookback_days).rank(pct=True).iloc[-1]  # 0~1

        return bool(rs_rank > 0.70)

    def _vol_dry_bounce_v2(self, df):
        if len(df) < 60:
            return False, {}

        last = df.iloc[-1]
        # ① Dry-Up 구간 찾기 (최근 10 일)

        vdu_mask = (
            (df["VOL_Z"] <= -1)
            & (df["Close"] < df["SMA5"])
            & (df["Close"] > df["SMA20"])
        )

        if not vdu_mask.tail(10).any():
            return False, {}

        # ② 오늘 Break-out 조건
        trig = (
            (last["Close"] > last["SMA5"])
            and (0.98 <= last["Close"] / last["SMA20"] <= 1.03)
            # and (last["VOL_PCTL60"] >= 0.9)
        )

        return trig, {
            "z_vol": round(float(last["VOL_Z"]), 2) or None,
            "pctl_vol": round(float(last["VOL_PCTL60"]), 2) or None,
            "close_sma20": round(float(last["Close"] / last["SMA20"]), 3) or None,
        }

    def _latest_eps_surprise_pct(self, tk: yf.Ticker) -> float | None:
        """
        yfinance ≥0.2.31
        get_earnings_history() → [{'date': '2024-10-24', 'actual': 1.63,
                                'estimate': 1.46, 'surprise': 0.17,
                                'surprisePercent': 11.64}, ...]
        """
        try:
            hist = tk.get_earnings_history()
            if isinstance(hist, pd.DataFrame):
                if not hist.empty:
                    last = hist.iloc[0].to_dict()
                    est = last.get("epsEstimate")
                    act = last.get("epsActual")
                    if est and act:
                        return (act - est) / abs(est) * 100
            elif hist:  # If it's a dictionary or list
                last = hist[0]  # 가장 최근 분기
                est = last.get("epsEstimate")
                act = last.get("epsActual")
                if est and act:
                    return (act - est) / abs(est) * 100
        except Exception:
            pass
        return None

    def _revenue_yoy_growth(self, tk: yf.Ticker) -> float | None:
        """
        최근 분기 매출(0번) vs 1년 전 동분기(4번) YoY %
        """
        try:
            fin = tk.get_income_stmt(freq="quarterly")  # Could be DataFrame or dict

            # Handle DataFrame case (newer yfinance versions)
            if isinstance(fin, pd.DataFrame):
                if "TotalRevenue" in fin.index and fin.shape[1] >= 5:
                    try:
                        val_now = fin.iloc[fin.index.get_loc("TotalRevenue"), 0]
                        val_yearago = fin.iloc[fin.index.get_loc("TotalRevenue"), 4]

                        # Safe conversion to float, handling various data types
                        def safe_float_convert(val):
                            if hasattr(val, "iloc"):  # Handle Series
                                val = val.iloc[0]
                            if isinstance(val, complex):  # Handle complex numbers
                                val = val.real
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                logger.warning(
                                    f"Could not convert value to float: {val}"
                                )
                                return None

                        rev_now = safe_float_convert(val_now)
                        rev_yearago = safe_float_convert(val_yearago)

                        if (
                            rev_now is not None
                            and rev_yearago is not None
                            and rev_yearago != 0
                        ):
                            return (rev_now - rev_yearago) / abs(rev_yearago) * 100
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.warning(
                            f"Error converting revenue values to float: {str(e)}"
                        )

            # Handle dictionary case (older yfinance versions)
            elif isinstance(fin, dict) and "Total Revenue" in fin:
                revenues = fin["Total Revenue"]
                if isinstance(revenues, list) and len(revenues) >= 5:
                    rev_now = float(revenues[0])
                    rev_yearago = float(revenues[4])
                    if rev_yearago != 0:
                        return (rev_now - rev_yearago) / abs(rev_yearago) * 100
        except Exception as e:
            logger.warning(f"Error calculating revenue growth: {str(e)}")
            pass
        return None

    def _download_yf(self, ticker: str, start: date) -> pd.DataFrame:
        if start is None:
            start = date.today() - timedelta(days=days_back)

        df = (
            yf.Ticker(ticker)
            .history(
                start=start.isoformat(), end=date.today().isoformat(), auto_adjust=True
            )  # ← 여기서는 group_by 파라미터 없음
            .drop(columns=["Dividends", "Stock Splits"], errors="ignore")
        )
        df.index.name = "Date"
        return df

    def _download_stooq(self, ticker: str, start: date) -> pd.DataFrame:
        """
        Stooq는 무료·무제한. 미국 종목은 보통 `AAPL`, `MSFT` 그대로,
        ETF는 `SPY` → `SPY` or `SPY.US` 둘 다 동작하는 경우가 많다.
        """
        df = pdr.DataReader(ticker, "stooq", start, date.today())
        if df.empty:
            return pd.DataFrame()
        df = df.sort_index()  # Stooq는 최신 → 과거 순서
        df.index = df.index.tz_localize(None)
        return df.rename(
            columns={
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            }
        )

    def _safe(self, v: Union[float, str]) -> Optional[float]:
        """스칼라 대신 NaN 이면 None 리턴"""
        return None if pd.isna(v) else float(v)

    def fetch_ohlcv(
        self,
        ticker: str,
        start: Optional[date] = None,
        days_back: int = 365,
    ) -> pd.DataFrame:
        """
        1) Yahoo Finance → 2) Stooq 순서로 시도
        return: 일봉 OHLCV (Close 컬럼이 반드시 존재), 실패 시 빈 DataFrame
        """
        if start is None:
            start = date.today() - timedelta(days=days_back)

        df = self._download_yf(ticker, start)
        if not df.empty:
            df = flatten_price_columns(df, ticker)
            return df

        logger.warning(f"Failed to fetch data for ticker [Yahoo Finances]: {ticker}")

        # fallback
        df = self._download_stooq(ticker, start)

        if df.empty:
            logger.warning(f"Failed to fetch data for ticker: {ticker}")
            return pd.DataFrame()

        df = flatten_price_columns(df, ticker)
        return df

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # --- Stochastic ---
        df["SMA5"] = ta.sma(df.Close, 5)
        df["SMA20"] = ta.sma(df.Close, 20)
        df["VOL20"] = df.Volume.rolling(20).mean()
        df["VOL_Z"] = (df.Volume - df.VOL20) / df.Volume.rolling(20).std()
        df["VOL_PCTL60"] = df.Volume.rank(pct=True, method="max")

        # --- 이동평균 & RSI ---
        df["SMA10"] = ta.sma(df["Close"], length=10)
        df["SMA50"] = ta.sma(df["Close"], length=50)
        df["RSI14"] = ta.rsi(df["Close"], length=14)
        logger.info(f"이평선: {df["SMA10"]}, {df["SMA50"]}, {df["RSI14"]}")

        # --- 볼린저밴드 ---
        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None:
            logger.info(f"볼린저밴드: {bb}")
            df = pd.concat([df, bb], axis=1)

        # --- MACD ---
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd is not None:
            logger.info(f"macd: {macd}")
            df = pd.concat(
                [df, macd], axis=1
            )  # 컬럼: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

        # 계산 끝난 뒤 앞쪽 NaN 영역 한 번에 잘라내기
        df = df.dropna(how="all").reset_index(drop=False).set_index("Date")
        return df

    def evaluate_signals(
        self, df: pd.DataFrame, strategies: List[Strategy], ticker: str
    ) -> List[TechnicalSignal]:
        out: List[TechnicalSignal] = []
        cols = set(df.columns)

        # —––– 스칼라 값 안전 추출 —––––
        # Close
        close_last = df["Close"].iloc[-1]

        # SMAs
        sma10_last = df["SMA10"].iloc[-1] if "SMA10" in cols else None
        sma50_last = df["SMA50"].iloc[-1] if "SMA50" in cols else None

        # RSI
        rsi_last = df["RSI14"].iloc[-1] if "RSI14" in cols else None

        # Bollinger Lower
        bbl_last = df["BBL_20_2.0"].iloc[-1] if "BBL_20_2.0" in cols else None

        # MACD 히스토그램 (이전·최신)   'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9'
        macd_prev = df["MACDh_12_26_9"].iloc[-2] if "MACDh_12_26_9" in cols else None
        macd_last = df["MACDh_12_26_9"].iloc[-1] if "MACDh_12_26_9" in cols else None

        # —––– 전략별 조건 평가 —––––

        # 1) PULLBACK: SMA10, SMA50 모두 있어야
        if "PULLBACK" in strategies:
            if sma10_last is not None and sma50_last is not None:
                triggered = (close_last <= sma10_last * 1.005) and (
                    close_last >= sma50_last
                )
            else:
                triggered = False
            out.append(
                TechnicalSignal(
                    strategy="PULLBACK",
                    triggered=triggered,
                    details={
                        "close": close_last,
                        "sma10": sma10_last,
                        "sma50": sma50_last,
                    },
                )
            )

        # 2) OVERSOLD: RSI, BBL 모두 있어야
        if "OVERSOLD" in strategies:
            if rsi_last is not None and bbl_last is not None:
                triggered = (rsi_last < 30) and (close_last < bbl_last)
            else:
                triggered = False
            out.append(
                TechnicalSignal(
                    strategy="OVERSOLD",
                    triggered=triggered,
                    details={"RSI14": rsi_last, "BBL": bbl_last},
                )
            )

        # 3) MACD_LONG: MACD_HIST 이전·최신 모두 있어야
        if "MACD_LONG" in strategies:
            if macd_prev is not None and macd_last is not None:
                triggered = (macd_prev < 0) and (macd_last > 0)
            else:
                triggered = False
            out.append(
                TechnicalSignal(
                    strategy="MACD_LONG",
                    triggered=triggered,
                    details={"prev_macd_h": macd_prev, "macd_h": macd_last},
                )
            )

        if "VOL_DRY_BOUNCE" in strategies:
            trig, det = self._vol_dry_bounce_v2(df)
            out.append(
                TechnicalSignal(strategy="VOL_DRY_BOUNCE", triggered=trig, details=det)
            )

        return out

    def fetch_fundamentals(self, ticker: str) -> FundamentalData:
        """
        trailing PE, EPS 서프라이즈 %, 매출 YoY %
        비어 있으면 None 반환 → Pydantic 필드는 optional
        """
        tk = yf.Ticker(ticker)

        info = tk.info or tk.fast_info or {}  # fast_info 가 더 빠르고 안정적
        trailing_pe = info.get("peTrailing") or info.get("trailingPE")

        eps_surprise_pct = self._latest_eps_surprise_pct(tk)
        revenue_growth = self._revenue_yoy_growth(tk)

        return FundamentalData(
            trailing_pe=trailing_pe,
            eps_surprise_pct=eps_surprise_pct,
            revenue_growth=revenue_growth,
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
                sentiment=None,
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
        signals = self.evaluate_signals(df_with_indicators, strategies, ticker)

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
