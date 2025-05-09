from datetime import date, timedelta
import logging
from typing import List, Optional, Literal, Union, cast
import pandas as pd
import yfinance as yf
import pandas_ta as ta  # Ensure 'ta' is installed via pip install ta
import requests
import datetime as dt

from pandas_datareader import data as pdr  # pip install pandas_datareader

# from nltk.sentiment import SentimentIntensityAnalyzer

from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import (
    SignalPromptData,
    TechnicalSignal,
    Strategy,
    FundamentalData,
    NewsHeadline,
    TickerReport,
)

logger = logging.getLogger(__name__)


def safe_float(val):
    if val is None:
        return None
    if isinstance(val, pd.Series):
        if len(val) > 0:
            val = val.iloc[0]
        else:
            return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


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
        vdu_mask = (
            (df["VOL_Z"] <= -1)
            & (df["Close"] < df["SMA5"])
            & (df["Close"] > df["SMA20"])
        )
        if not vdu_mask.tail(10).any():
            return False, {}
        trig = (
            (last["Close"] >= last["SMA5"])
            and (0.95 <= last["Close"] / last["SMA20"] <= 1.05)
            # 변경: 거래량 퍼센타일 조건 제거로 신호 완화
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

        # 추가: ROE 계산

    def _calculate_roe(self, tk: yf.Ticker) -> float | None:
        try:
            fin = tk.get_income_stmt(freq="yearly")
            balance = tk.get_balance_sheet(freq="yearly")
            if isinstance(fin, pd.DataFrame) and isinstance(balance, pd.DataFrame):
                net_income = (
                    fin.loc["NetIncome"].iloc[0] if "NetIncome" in fin.index else None
                )
                equity = (
                    balance.loc["StockholdersEquity"].iloc[0]
                    if "StockholdersEquity" in balance.index
                    else None
                )

                # Extract scalar values from Series objects if needed

                net_income_val = safe_float(net_income)
                equity_val = safe_float(equity)

                if (
                    net_income_val is not None
                    and equity_val is not None
                    and equity_val != 0
                ):
                    return net_income_val / equity_val * 100
        except Exception as e:
            logger.warning(f"Error calculating ROE: {str(e)}")
        return None

    # 추가: Debt-to-Equity Ratio 계산
    def _calculate_debt_to_equity(self, tk: yf.Ticker) -> float | None:
        try:
            balance = tk.get_balance_sheet(freq="yearly")
            if isinstance(balance, pd.DataFrame):
                total_debt = (
                    balance.loc["TotalDebt"].iloc[0]
                    if "TotalDebt" in balance.index
                    else None
                )
                equity = (
                    balance.loc["StockholdersEquity"].iloc[0]
                    if "StockholdersEquity" in balance.index
                    else None
                )

                # Extract scalar values from Series objects if needed

                total_debt_val = safe_float(total_debt)
                equity_val = safe_float(equity)

                if (
                    total_debt_val is not None
                    and equity_val is not None
                    and equity_val != 0
                ):
                    return total_debt_val / equity_val
        except Exception as e:
            logger.warning(f"Error calculating Debt-to-Equity: {str(e)}")
        return None

        # 추가: Free Cash Flow Yield 계산

    def _calculate_fcf_yield(self, tk: yf.Ticker) -> float | None:
        try:
            cashflow = tk.get_cash_flow(freq="yearly")
            info = tk.info or tk.fast_info or {}
            market_cap = info.get("marketCap")
            if isinstance(cashflow, pd.DataFrame) and market_cap:
                fcf = (
                    cashflow.loc["FreeCashFlow"].iloc[0]
                    if "FreeCashFlow" in cashflow.index
                    else None
                )
                if fcf is not None and market_cap != 0:
                    fcf = safe_float(fcf)
                    if fcf is not None:
                        return fcf / market_cap * 100
                    return None
        except Exception as e:
            logger.warning(f"Error calculating FCF Yield: {str(e)}")
        return None

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
        # 기존 지표
        df["SMA5"] = ta.sma(df.Close, 5)
        df["SMA10"] = ta.sma(df["Close"], length=10)
        df["SMA20"] = ta.sma(df.Close, 20)
        df["SMA50"] = ta.sma(df["Close"], length=50)
        df["SMA200"] = ta.sma(df["Close"], length=200)  # 추가: 장기 추세

        df["VOL20"] = df.Volume.rolling(20).mean()
        df["VOL_Z"] = (df.Volume - df.VOL20) / df.Volume.rolling(20).std()
        df["VOL_PCTL60"] = df.Volume.rank(pct=True, method="max")

        df["RSI14"] = ta.rsi(df["Close"], length=14)
        df["ATR14"] = ta.atr(
            df["High"], df["Low"], df["Close"], length=14
        )  # 추가: 변동성

        stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=14, d=3, smooth_k=3)

        if stoch is not None:
            df = pd.concat([df, stoch], axis=1)  # 추가: Stochastic Oscillator

        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None:
            df = pd.concat([df, bb], axis=1)

        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)

        # 추가: VWAP와 ROC
        df["VWAP"] = ta.vwap(df.High, df.Low, df.Close, df.Volume)
        df["ROC5"] = ta.roc(df.Close, length=5)

        df = df.dropna(how="all").reset_index(drop=False).set_index("Date")

        return df

    def evaluate_signals(
        self, df: pd.DataFrame, strategies: List[Strategy], ticker: str
    ) -> List[TechnicalSignal]:
        out: List[TechnicalSignal] = []
        cols = set(df.columns)
        close_last = df["Close"].iloc[-1]
        sma5_last = df["SMA5"].iloc[-1] if "SMA5" in cols else None
        sma10_last = df["SMA10"].iloc[-1] if "SMA10" in cols else None
        sma20_last = df["SMA20"].iloc[-1] if "SMA20" in cols else None
        sma50_last = df["SMA50"].iloc[-1] if "SMA50" in cols else None
        sma200_last = df["SMA200"].iloc[-1] if "SMA200" in cols else None
        rsi_last = df["RSI14"].iloc[-1] if "RSI14" in cols else None
        bbl_last = df["BBL_20_2.0"].iloc[-1] if "BBL_20_2.0" in cols else None
        macd_prev = df["MACDh_12_26_9"].iloc[-2] if "MACDh_12_26_9" in cols else None
        macd_last = df["MACDh_12_26_9"].iloc[-1] if "MACDh_12_26_9" in cols else None
        stoch_k = (
            df["STOCHk_14_3_3"].iloc[-1] if "STOCHk_14_3_3" in cols else None
        )  # 추가
        high_52w = (
            df["High"].rolling(252).max().iloc[-1] if len(df) >= 252 else None
        )  # 추가
        vwap_last = df["VWAP"].iloc[-1] if "VWAP" in cols else None
        roc5_last = df["ROC5"].iloc[-1] if "ROC5" in cols else None
        close_prev = df["Close"].iloc[-2] if len(df) > 1 else None

        # 변경: PULLBACK 조건 완화 (1% 이내)
        if "PULLBACK" in strategies:
            triggered = (
                sma10_last is not None
                and sma50_last is not None
                and close_last <= sma10_last * 1.03
                and close_last >= sma50_last * 0.98
            )
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

        # OVERSOLD (완화된 조건 + Stochastic 확인)
        if "OVERSOLD" in strategies:
            triggered = (
                rsi_last is not None
                and bbl_last is not None
                and stoch_k is not None
                and rsi_last < 40
                and close_last <= bbl_last * 1.02
                and stoch_k < 30
            )
            out.append(
                TechnicalSignal(
                    strategy="OVERSOLD",
                    triggered=triggered,
                    details={"rsi": rsi_last, "bbl": bbl_last, "stoch_k": stoch_k},
                )
            )

        # MACD_LONG (완화된 조건 + MACD 선 확인)
        if "MACD_LONG" in strategies:
            macd_line = df["MACD_12_26_9"].iloc[-1] if "MACD_12_26_9" in cols else None
            signal_line = (
                df["MACDs_12_26_9"].iloc[-1] if "MACDs_12_26_9" in cols else None
            )
            triggered = (
                macd_prev is not None
                and macd_last is not None
                and macd_line is not None
                and signal_line is not None
                and macd_prev < 0.2
                and macd_last > -0.05
                and macd_line > signal_line
            )
            out.append(
                TechnicalSignal(
                    strategy="MACD_LONG",
                    triggered=triggered,
                    details={"prev_macd_h": macd_prev, "macd_h": macd_last},
                )
            )

        # VOL_DRY_BOUNCE
        if "VOL_DRY_BOUNCE" in strategies:
            trig, det = self._vol_dry_bounce_v2(df)
            out.append(
                TechnicalSignal(strategy="VOL_DRY_BOUNCE", triggered=trig, details=det)
            )

        # GOLDEN_CROSS (완화된 조건 + 거래량 확인)
        if "GOLDEN_CROSS" in strategies:
            vol_z = df["VOL_Z"].iloc[-1] if "VOL_Z" in cols else None
            triggered = (
                sma50_last is not None
                and sma200_last is not None
                and vol_z is not None
                and sma50_last > sma200_last * 0.99
                and vol_z > 0.5
            )
            out.append(
                TechnicalSignal(
                    strategy="GOLDEN_CROSS",
                    triggered=triggered,
                    details={
                        "sma50": sma50_last,
                        "sma200": sma200_last,
                        "vol_z": vol_z,
                    },
                )
            )

        # MEAN_REVERSION (완화된 조건)
        if "MEAN_REVERSION" in strategies:
            triggered = (
                sma20_last is not None
                and close_prev is not None
                and close_last > sma20_last * 0.90
                and close_last < sma20_last * 1.10
                and close_prev < sma20_last * 0.95
            )
            out.append(
                TechnicalSignal(
                    strategy="MEAN_REVERSION",
                    triggered=triggered,
                    details={"close": close_last, "sma20": sma20_last},
                )
            )

        # BREAKOUT (완화된 조건 + RSI 확인)
        if "BREAKOUT" in strategies:
            triggered = (
                high_52w is not None
                and rsi_last is not None
                and close_last > high_52w * 0.98
                and rsi_last < 70
            )
            out.append(
                TechnicalSignal(
                    strategy="BREAKOUT",
                    triggered=triggered,
                    details={
                        "close": close_last,
                        "high_52w": high_52w,
                        "rsi": rsi_last,
                    },
                )
            )

        # GAP_UP (신규 전략)
        if "GAP_UP" in strategies:
            triggered = (
                close_prev is not None
                and vol_z is not None
                and close_last > close_prev * 1.02
                and vol_z > 0.5
            )
            out.append(
                TechnicalSignal(
                    strategy="GAP_UP",
                    triggered=triggered,
                    details={
                        "close": close_last,
                        "close_prev": close_prev,
                        "vol_z": vol_z,
                    },
                )
            )

        # # VWAP_BOUNCE (신규 전략) => 폐기 (너무 많이 잡음)
        # if "VWAP_BOUNCE" in strategies:
        #     triggered = (
        #         vwap_last is not None
        #         and rsi_last is not None
        #         and close_last >= vwap_last * 0.98
        #         and close_last <= vwap_last * 1.02
        #         and rsi_last >= 40
        #     )
        #     out.append(
        #         TechnicalSignal(
        #             strategy="VWAP_BOUNCE",
        #             triggered=triggered,
        #             details={"close": close_last, "vwap": vwap_last, "rsi": rsi_last},
        #         )
        #     )

        # 단기간 급격한 가격/거래량 변화 포착
        if "MOMENTUM_SURGE" in strategies:
            if "Volume" in df.columns and len(df) >= 5:
                # 최근 가격 변화율
                price_chg_pct = (df["Close"].iloc[-1] / df["Close"].iloc[-5] - 1) * 100

                # 최근 거래량 증가율
                vol_chg_pct = (
                    df["Volume"].iloc[-1] / df["Volume"].iloc[-5:].mean() - 1
                ) * 100

                # 가격 3% 이상 상승 + 거래량 50% 이상 증가
                triggered = bool((abs(price_chg_pct) > 3) and (vol_chg_pct > 50))

                details = {
                    "price_change_pct": round(price_chg_pct, 2),
                    "volume_change_pct": round(vol_chg_pct, 2),
                }

            else:
                triggered = False
                details = {}

            out.append(
                TechnicalSignal(
                    strategy="MOMENTUM_SURGE", triggered=triggered, details=details
                )
            )

        return out

    def fetch_fundamentals(self, ticker: str) -> FundamentalData:
        tk = yf.Ticker(ticker)
        info = tk.info or tk.fast_info or {}
        trailing_pe = info.get("peTrailing") or info.get("trailingPE")
        eps_surprise_pct = self._latest_eps_surprise_pct(tk)
        revenue_growth = self._revenue_yoy_growth(tk)
        roe = self._calculate_roe(tk)  # 추가
        debt_to_equity = self._calculate_debt_to_equity(tk)  # 추가
        fcf_yield = self._calculate_fcf_yield(tk)  # 추가
        return FundamentalData(
            trailing_pe=trailing_pe,
            eps_surprise_pct=eps_surprise_pct,
            revenue_growth=revenue_growth,
            roe=roe,
            debt_to_equity=debt_to_equity,
            fcf_yield=fcf_yield,
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
        self, ticker: str, days_back: int = 5, max_items: int = 5
    ) -> List[NewsHeadline]:
        """Fetch recent news headlines for the given ticker."""
        try:
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
        except ImportError:
            logger.warning("News API not available.")
            return []

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

    def generate_prompt(self, data: SignalPromptData):
        """
        Generate a prompt for the AI model based on the report and description.
        """

        prompt = f"""
        You are an expert stock trader with deep knowledge of technical and fundamental analysis. Your task is to analyze a list of stocks/ETFs based on their previous day's data and provide trading recommendations for today (May 5, 2025). For each stock/ETF with triggered technical signals, recommend whether to BUY, SELL, or HOLD, and provide specific entry price, stop-loss price, and take-profit price. Base your recommendations on the provided technical signals, fundamental data, and news headlines, considering market conditions and volatility. Ensure recommendations are realistic and aligned with short-term trading (1-3 days).

        ### Input Data
        Below is a JSON array of stocks/ETFs with their previous day's data (May 4, 2025). Each item includes:
        - `ticker`: Stock/ETF ticker symbol.
        - `last_price`: Closing price from the previous day.
        - `price_change_pct`: Percentage price change from the day before.
        - `triggered_strategies`: List of technical strategies triggered, with descriptions:
            - PULLBACK: Price has dipped close to the 10-day SMA while remaining above the 50-day SMA—aiming to “buy the dip” within an ongoing uptrend.
            - OVERSOLD: RSI(14) falls below 40, the price trades near the lower Bollinger Band (BBL_20_2.0), and Stochastic %K is under 30, signaling potential oversold conditions.
            - MACD_LONG: The MACD histogram (MACDh) moves from deep negative territory (e.g. below –0.20) to above –0.05, and the MACD line crosses above its signal line, indicating a bullish shift.
            - VOL_DRY_BOUNCE: After a period of unusually low volume (“dry-up”), volume begins to recover and the price bounces—capturing a rebound from a low-volume pullback.
            - GOLDEN_CROSS: The 50-day SMA crosses above (or nearly crosses) the 200-day SMA, accompanied by a volume Z-score (VOL_Z) above 0.5, suggesting a strong bullish reversal.
            - MEAN_REVERSION: Price deviates significantly below the 20-day SMA (previous close < 95% of SMA20) then reverts back within ±10% of the SMA20—trading on the expectation of average-reversion.
            - BREAKOUT: The current price exceeds 98% of its 52-week high while RSI remains below 70, identifying a near-high breakout with room for further upside.
            - GAP_UP: The price opens significantly higher than the previous close (e.g. > 2%) with a volume Z-score above 0.5, indicating a strong bullish gap.
            - MOMENTUM_SURGE: The price has surged more than 3% over the last 5 days with a volume increase of over 50%, indicating a strong momentum shift.
        - `technical_details`: Detailed metrics for each triggered strategy (e.g., RSI, SMA values).
        - `fundamentals`: Fundamental metrics (trailing_pe, eps_surprise_pct, revenue_growth, roe, debt_to_equity, fcf_yield).
            - `trailing_pe`: Trailing Price-to-Earnings ratio.
            - `eps_surprise_pct`: Earnings per share surprise percentage.
            - `revenue_growth`: Year-over-year revenue growth percentage.
            - `roe`: Return on equity percentage.
            - `debt_to_equity`: Debt-to-equity ratio.
            - `fcf_yield`: Free cash flow yield percentage.
        - `news`: Recent news headlines (sentiment analysis currently unavailable).

        ```json
            - ticker: {data.ticker}
            - last_price: {data.last_price}
            - price_change_pct: {data.price_change_pct}
            - triggered_strategies: {data.triggered_strategies}
            - technical_details: {data.technical_details}
            - fundamentals: {data.fundamentals}
            - news: {data.news}
            - dataframe: {data.dataframe}
            - additional_info: {data.additional_info}
        ```

        ## Instructions

            ### Analyze Each Stock/ETF:
            - Evaluate the triggered strategies and their technical details (e.g., RSI, MACD).
            - Consider fundamental data (e.g., high ROE, low debt-to-equity) for stock quality.
            - Factor in news headlines for sentiment or catalysts (e.g., earnings beats).
            - Assess price_change_pct for momentum or reversal potential.

            ### Provide Recommendations:
            - For each stock/ETF, recommend one of: BUY, SELL, or HOLD.
                For BUY/SELL:
                - Entry Price: Suggested price to enter today (e.g., near last_price or a breakout level).
                - Stop-Loss Price: Price to exit to limit losses (e.g., 2-5% below entry, based on ATR or support levels).
                - Take-Profit Price: Price to exit for profit (e.g., 5-10% above entry, based on resistance or strategy).
                
                For HOLD: Explain why no action is recommended (e.g., unclear trend, high risk).

            ### Reasoning:
            - Explain your recommendation step-by-step, referencing specific technical/fundamental data and news.


            ### Constraints:
            - Entry, stop-loss, and take-profit prices must be realistic (within 10% of last_price unless justified).
            - Consider short-term trading horizon (1-3 days).
            - Avoid recommending stocks with no triggered strategies.
            - If fundamentals are unavailable (e.g., ETFs), focus on technicals and news.

            ### Output Format
            Return a JSON array of recommendations, one per stock/ETF. Each recommendation should include:
            - ticker: Stock/ETF ticker.
            - recommendation: "BUY", "SELL", or "HOLD".
            - entry_price: Suggested entry price (null for HOLD).
            - stop_loss_price: Suggested stop-loss price (null for HOLD).
            - take_profit_price: Suggested take-profit price (null for HOLD).
            - reasoning: Step-by-step explanation of the recommendation.
        """

        return prompt
