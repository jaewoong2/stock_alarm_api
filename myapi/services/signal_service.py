from datetime import date, timedelta, timezone
import datetime
from email.utils import parsedate_to_datetime
import html
from io import BytesIO
import logging
import re
from tracemalloc import start
from typing import List, Literal, Optional, Sequence, Union
import aiohttp
import cloudscraper
import pandas as pd
import pdfplumber
import yfinance as yf
import numpy as np
if not hasattr(np, "NaN"):
    np.NaN = np.nan
import pandas_ta as ta
import requests
import datetime as dt

from pandas_datareader import data as pdr

from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import (
    Article,
    GetSignalByOnlyAIRequest,
    SignalPromptData,
    TechnicalSignal,
    Strategy,
    FundamentalData,
    NewsHeadline,
    WebSearchTickerResult,
)
from myapi.domain.news.news_schema import (
    WebSearchMarketItem,
)
from myapi.domain.news.news_models import WebSearchResult

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
    def __init__(
        self,
        settings: Settings,
        signals_repository: SignalsRepository,
        web_search_repository: WebSearchResultRepository,
    ):
        self.settings = settings
        self.DEFAULT_UNIVERSE: str = "SPY,QQQ,AAPL,MSFT,TSLA"
        self.START_DAYS_BACK: int = 365
        self.signals_repository = signals_repository
        self.web_search_repository = web_search_repository
        # self.sia = SentimentIntensityAnalyzer()

    def save_web_search_results(
        self,
        result_type: str,
        results: Sequence[WebSearchMarketItem | WebSearchTickerResult],
        ticker: str | None = None,
    ) -> None:
        db_items = [
            WebSearchResult(
                result_type=result_type,
                ticker=ticker,
                date_yyyymmdd=item.issued_YYYYMMDD,
                headline=getattr(item, "headline", None),
                summary=getattr(item, "summary", None),
                detail_description=getattr(item, "full_description", None),
                recommendation=getattr(item, "recommendation", None),
            )
            for item in results
        ]
        if db_items:
            self.web_search_repository.bulk_create(db_items)

    def market_ok(self, index_ticker="SPY") -> bool:
        """시장 필터: 지수 종가가 20일 SMA 위면 True"""
        df = yf.download(index_ticker, period="6mo", auto_adjust=True, progress=False)

        if df is None:
            return False

        if df.empty:
            return False

        df["SMA20"] = ta.sma(df["Close"], length=20)
        return bool((df["Close"].iloc[-1] > df["SMA20"].iloc[-1])[index_ticker])

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

    def _download_yfinance(
        self, ticker: str, start: datetime.datetime, end: datetime.datetime
    ) -> pd.DataFrame:
        """
        yfinance를 사용하여 주식 데이터를 다운로드합니다.
        :param ticker: 종목 티커 (예: 'AAPL')
        :param start: 시작 날짜 (datetime.date)
        :param end: 종료 날짜 (datetime.date)
        :return: OHLCV 데이터프레임
        """
        df = (
            yf.Ticker(ticker)
            .history(
                start=datetime.datetime.strftime(start, "%Y-%m-%d"),
                end=datetime.datetime.strftime(end, "%Y-%m-%d"),
                auto_adjust=True,
            )  # ← 여기서는 group_by 파라미터 없음
            .drop(columns=["Dividends", "Stock Splits"], errors="ignore")
        )
        df.index.name = "Date"
        return df

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

    def add_computed_rs_data(
        self, df: pd.DataFrame, spy_df: pd.DataFrame | None = None
    ):
        """
        종목의 상대강도(RS) 데이터 계산
        :param df: 종목 OHLCV 데이터프레임
        :param spy_df: SPY ETF 데이터프레임 (없으면 자동으로 다운로드)
        :return: RS 데이터가 추가된 데이터프레임
        """
        try:
            # If spy_df is not provided, download it
            if spy_df is None:
                start_date = df.index.min()
                end_date = df.index.max() + timedelta(days=1)
                spy_df = yf.download(
                    "SPY",
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    auto_adjust=True,
                    progress=False,
                )

            if spy_df is None or spy_df.empty:
                return df

            # Reindex SPY close prices to match df's index
            spy_close = spy_df["Close"].reindex(df.index).ffill()

            for period, col in [(20, "RS_SHORT"), (60, "RS_MID")]:
                ticker_ret = df["Close"].pct_change(period)
                spy_ret = spy_close.pct_change(period)
                df[col] = (ticker_ret - spy_ret) * 100
        except Exception as e:
            logger.warning(f"Failed to compute RS data for: {e}")

        return df

    def fetch_ohlcv(
        self,
        ticker: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        days_back: int = 365,
    ) -> pd.DataFrame:
        """
        1) Yahoo Finance → 2) Stooq 순서로 시도
        return: 일봉 OHLCV (Close 컬럼이 반드시 존재), 실패 시 빈 DataFrame
        """
        if start is not None and end is not None:
            # Convert date objects to datetime objects
            start_dt = datetime.datetime.combine(start, datetime.datetime.min.time())
            end_dt = datetime.datetime.combine(end, datetime.datetime.min.time())
            df = self._download_yfinance(ticker=ticker, start=start_dt, end=end_dt)

            if not df.empty:
                df = flatten_price_columns(df, ticker)
                return df

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

    def add_indicators(self, df: pd.DataFrame, spy_df: pd.DataFrame) -> pd.DataFrame:
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
        df["VolumeSpike"] = df["Volume"] > df["VOL20"] * 2
        df["VolumeSpikeStrength"] = df["Volume"] / df["VOL20"]  # 급등 강도

        df["RSI14"] = ta.rsi(df["Close"], length=14)
        df["EMA12"] = ta.ema(df["Close"], length=12)
        df["EMA26"] = ta.ema(df["Close"], length=26)
        stoch_rsi = ta.stochrsi(df["Close"], length=14)
        if stoch_rsi is not None:
            df = pd.concat([df, stoch_rsi], axis=1)
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
        # df["VWAP"] = ta.vwap(df.High, df.Low, df.Close, df.Volume)
        df["ROC5"] = ta.roc(df.Close, length=5)

        # ────────── 신규 ‘추세’ 지표 ──────────
        # ① ADX(+DI/-DI) – 추세 강도
        df = pd.concat(
            [df, ta.adx(df.High, df.Low, df.Close, length=14)], axis=1
        )  # ADX_14, DMP_14, DMN_14

        # ② SuperTrend (ATR 기반 추세 필터) – ta 패키지에 존재
        df = pd.concat(
            [df, ta.supertrend(df.High, df.Low, df.Close, length=10, multiplier=3)],
            axis=1,
        )
        # 컬럼: SUPERT_10_3.0, SUPERTd_10_3.0 (direction)

        # ③ Donchian Channel(20) – 추세 돌파용
        donch = ta.donchian(
            df.High, df.Low, length=20
        )  # DONCHU_20, DONCHL_20, DONCHM_20
        df = pd.concat([df, donch], axis=1)

        # ④ 이동평균 기울기(∇) – SMA50 기울기
        df["SMA50_SLOPE"] = df["SMA50"].diff()

        df["VWAP"] = ta.vwap(
            df["High"], df["Low"], df["Close"], df["Volume"]
        )  # 장중 기준선
        df["RSI5"] = ta.rsi(df["Close"], length=5)  # 단기 RSI
        # 볼린저 밴드 폭 (%)
        df["BB_WIDTH"] = (df["BBU_20_2.0"] - df["BBL_20_2.0"]) / df["Close"]

        df["AVG_VOL20"] = df["Volume"].rolling(20).mean()
        df["LIQUIDITY_FILTER"] = df["AVG_VOL20"] > 500000  # 최소 거래량 기준

        df["ATR_PCT"] = (df["ATR14"] / df["Close"]) * 100  # 변동성 비율

        df["GAP_PCT"] = df["Open"] / df["Close"].shift(1) - 1

        # True-Range Ratio: 오늘 변동성 / 20일 평균 변동성
        avg_atr20 = df["ATR14"].rolling(20).mean()
        df["ATR_RATIO"] = df["ATR14"] / avg_atr20

        # 초단기 모멘텀
        df["ROC1"] = ta.roc(df["Close"], length=1)
        df["ROC3"] = ta.roc(df["Close"], length=3)

        # ─── 캔들 패턴 예: 상승장악(Engulfing) ────────────
        df["BULL_ENGULF"] = (
            (df["Close"].shift(1) < df["Open"].shift(1))  # 전일 음봉
            & (df["Open"] < df["Close"].shift(1))  # 오늘 시가 < 전일 종가
            & (df["Close"] > df["Open"].shift(1))  # 오늘 종가 > 전일 시가
        )

        # (신규) 장기 추세용 SMA150 ─ VCP 필터에서 사용
        df["SMA150"] = ta.sma(df["Close"], length=150)

        # (신규) VCP 보조지표 -------------------------------
        long_win, short_win = 20, 5  # ‘긴 변동성’/‘짧은 변동성’ 구간
        # ­♠ ① 구간별 변동폭(%)
        df["RANGE_LONG"] = (
            df["High"].rolling(long_win).max() - df["Low"].rolling(long_win).min()
        ) / df["Low"].rolling(long_win).min()
        df["RANGE_SHORT"] = (
            df["High"].rolling(short_win).max() - df["Low"].rolling(short_win).min()
        ) / df["Low"].rolling(short_win).min()
        # ­♠ ② 거래량 드라이-업 지표(당일-vs-20일 평균 비율)
        df["VCP_VOL_REL"] = df["Volume"] / df["Volume"].rolling(long_win).mean()

        df = df.dropna(how="all").reset_index(drop=False).set_index("Date")
        df = self.add_computed_rs_data(df, spy_df)

        return df

    def evaluate_signals(
        self, df: pd.DataFrame, strategies: List[Strategy]
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
        ema12_last = df["EMA12"].iloc[-1] if "EMA12" in cols else None
        ema26_last = df["EMA26"].iloc[-1] if "EMA26" in cols else None
        stoch_k = (
            df["STOCHk_14_3_3"].iloc[-1] if "STOCHk_14_3_3" in cols else None
        )  # 추가
        stochrsi_k = (
            df["STOCHRSIk_14_14_3_3"].iloc[-1]
            if "STOCHRSIk_14_14_3_3" in cols
            else None
        )
        high_52w = (
            df["High"].rolling(252).max().iloc[-1] if len(df) >= 252 else None
        )  # 추가

        close_prev = df["Close"].iloc[-2] if len(df) > 1 else None
        rsi_last = df["RSI_14"].iloc[-1] if "RSI_14" in df.columns else None
        rs_short_last = df["RS_SHORT"].iloc[-1] if "RS_SHORT" in cols else None
        rs_mid_last = df["RS_MID"].iloc[-1] if "RS_MID" in cols else None

        # 최신 값 준비
        gap_pct = df["GAP_PCT"].iloc[-1]
        roc1, roc3 = df["ROC1"].iloc[-1], df["ROC3"].iloc[-1]
        atr_ratio = df["ATR_RATIO"].iloc[-1]
        vol_ratio20 = df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1]
        bb_width = df["BB_WIDTH"].iloc[-1]

        # 전일(shift 1) high·volume·close
        prev_high = df["High"].iloc[-2]
        prev_close = df["Close"].iloc[-2]

        # 3) VOLUME_EXPANSION
        if "VOLUME_EXPANSION" in strategies:
            triggered = (vol_ratio20 >= 1.5) and (roc1 >= 0.02)
            out.append(
                TechnicalSignal(
                    strategy="VOLUME_EXPANSION",
                    triggered=triggered,
                    details={
                        "vol_ratio20": round(vol_ratio20, 2),
                        "roc1": round(roc1 * 100, 2),
                    },
                )
            )

        # 4) QUIET_PULLBACK
        if "QUIET_PULLBACK" in strategies:
            triggered = (abs(prev_close / sma10_last - 1) <= 0.01) and (atr_ratio < 0.7)
            out.append(
                TechnicalSignal(
                    strategy="QUIET_PULLBACK",
                    triggered=triggered,
                    details={
                        "prev_close": prev_close,
                        "sma10": sma10_last,
                        "atr_ratio": round(atr_ratio, 2),
                    },
                )
            )

        # 5) VOLATILITY_COMPRESSION
        if "VOLATILITY_COMPRESSION" in strategies:
            # 6개월(≈126거래일) 최저 BB 폭인지 확인
            min_bw_6m = df["BB_WIDTH"].rolling(126).min().iloc[-1]
            triggered = bb_width <= min_bw_6m * 1.05  # 여유 5 %
            out.append(
                TechnicalSignal(
                    strategy="VOLATILITY_COMPRESSION",
                    triggered=triggered,
                    details={
                        "bb_width": round(bb_width, 4),
                        "min_bw_6m": round(min_bw_6m, 4),
                    },
                )
            )

        if "RS_SHORT" in strategies:
            triggered = rs_short_last is not None and rs_short_last > 0
            out.append(
                TechnicalSignal(
                    strategy="RS_SHORT",
                    triggered=triggered,
                    details={"rs_short": rs_short_last},
                )
            )

        if "RS_MID" in strategies:
            triggered = rs_mid_last is not None and rs_mid_last > 0
            out.append(
                TechnicalSignal(
                    strategy="RS_MID",
                    triggered=triggered,
                    details={"rs_mid": rs_mid_last},
                )
            )

        if "VOLUME_SPIKE" in strategies and df["VolumeSpike"].iloc[-1]:
            price_change = df["Close"].pct_change().iloc[-1] if len(df) > 1 else 0
            triggered = (
                rsi_last is not None and rsi_last < 50 and price_change > 0.01
            )  # 상승 + 과매수 아님
            out.append(
                TechnicalSignal(
                    strategy="VOLUME_SPIKE",
                    triggered=triggered,
                    details={
                        "volume": df["Volume"].iloc[-1],
                        "vol20": df["VOL20"].iloc[-1],
                        "rsi": rsi_last,
                        "price_change_pct": price_change * 100,
                    },
                )
            )

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
                and stochrsi_k is not None
                and rsi_last < 40
                and close_last <= bbl_last * 1.02
                and stoch_k < 30
                and stochrsi_k < 20
            )
            out.append(
                TechnicalSignal(
                    strategy="OVERSOLD",
                    triggered=triggered,
                    details={
                        "rsi": rsi_last,
                        "bbl": bbl_last,
                        "stoch_k": stoch_k,
                        "stochrsi_k": stochrsi_k,
                    },
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
                and ema12_last is not None
                and ema26_last is not None
                and macd_prev < 0.2
                and macd_last > -0.05
                and macd_line > signal_line
                and ema12_last > ema26_last
            )
            out.append(
                TechnicalSignal(
                    strategy="MACD_LONG",
                    triggered=triggered,
                    details={
                        "prev_macd_h": macd_prev,
                        "macd_h": macd_last,
                        "ema12": ema12_last,
                        "ema26": ema26_last,
                    },
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

        if "TREND_UP" in strategies:
            adx_last = df["ADX_14"].iloc[-1]
            dip_last = df["DMP_14"].iloc[-1]  # +DI
            dim_last = df["DMN_14"].iloc[-1]  # -DI
            st_dir = df["SUPERTd_10_3.0"].iloc[-1]  # 1이면 상승, -1이면 하락
            slope_50 = df["SMA50_SLOPE"].iloc[-1]

            if sma50_last is None or sma200_last is None:
                return out

            triggered = bool(
                adx_last > 25  # 추세 강함
                and dip_last > dim_last  # 매수우위
                and st_dir == 1  # SuperTrend 상승
                and close_last > sma50_last > sma200_last  # 가격 구조
                and slope_50 > 0  # SMA50 우상향
            )
            out.append(
                TechnicalSignal(
                    strategy="TREND_UP",
                    triggered=triggered,
                    details={
                        "adx": adx_last,
                        "+di": dip_last,
                        "-di": dim_last,
                        "supertrend_dir": st_dir,
                        "sma50_slope": slope_50,
                    },
                )
            )

        if "TREND_DOWN" in strategies:
            adx_last = df["ADX_14"].iloc[-1]
            dip_last = df["DMP_14"].iloc[-1]
            dim_last = df["DMN_14"].iloc[-1]
            st_dir = df["SUPERTd_10_3.0"].iloc[-1]
            slope_50 = df["SMA50_SLOPE"].iloc[-1]

            if sma50_last is None or sma200_last is None:
                return out

            triggered = bool(
                adx_last > 25
                and dim_last > dip_last  # 매도우위
                and st_dir == -1  # SuperTrend 하락
                and close_last < sma50_last < sma200_last
                and slope_50 < 0
            )

            out.append(
                TechnicalSignal(
                    strategy="TREND_DOWN",
                    triggered=triggered,
                    details={
                        "adx": adx_last,
                        "+di": dip_last,
                        "-di": dim_last,
                        "supertrend_dir": st_dir,
                        "sma50_slope": slope_50,
                    },
                )
            )

        if "DONCHIAN_BREAKOUT" in strategies:
            donch_high_prev = df["DCU_20_20"].iloc[-2]
            donch_high_now = df["DCU_20_20"].iloc[-1]

            triggered = bool(
                close_last > donch_high_prev  # 20일 고가 돌파
                and adx_last > 20  # 추세 강화
                and vol_z is not None
                and vol_z > 0  # 거래량 ↑  (기존 계산값 활용)
            )
            out.append(
                TechnicalSignal(
                    strategy="DONCHIAN_BREAKOUT",
                    triggered=triggered,
                    details={
                        "close": close_last,
                        "prev_donch_high": donch_high_prev,
                        "adx": adx_last,
                        "vol_z": vol_z,
                    },
                )
            )

        sma150_last = df["SMA150"].iloc[-1] if "SMA150" in cols else None

        if "VCP_DAILY" in strategies:
            # 트렌드 필터: SMA50 > SMA150 > SMA200
            trend_ok = (
                sma50_last is not None
                and sma150_last is not None
                and sma200_last is not None
                and sma50_last > sma150_last > sma200_last
            )

            # 변동성 수축(‘널널’ 버전): 최근 5일 폭이 최근 20일 폭의 75% 미만
            range_long = df["RANGE_LONG"].iloc[-1] if "RANGE_LONG" in cols else None
            range_short = df["RANGE_SHORT"].iloc[-1] if "RANGE_SHORT" in cols else None
            contraction = (
                range_long is not None
                and range_short is not None
                and range_short < range_long * 0.75
            )

            # 거래량 드라이-업(‘널널’): 오늘 볼륨이 20일 평균의 0.8 미만
            vol_rel = df["VCP_VOL_REL"].iloc[-1] if "VCP_VOL_REL" in cols else None
            vol_dry = vol_rel is not None and vol_rel < 1.0

            # 피벗: 전일 포함 10일 최고가 돌파(살짝 여유 0.5% 버퍼)
            pivot_high = df["High"].rolling(10).max().iloc[-2]
            price_break = df["Close"].iloc[-1] > pivot_high * 1.005

            triggered = bool(trend_ok and contraction and vol_dry)

            out.append(
                TechnicalSignal(
                    strategy="VCP_DAILY",
                    triggered=triggered,
                    details={
                        "range_long_pct": (
                            round(range_long * 100, 2) if range_long else None
                        ),
                        "range_short_pct": (
                            round(range_short * 100, 2) if range_short else None
                        ),
                        "vol_rel20": round(vol_rel, 2) if vol_rel else None,
                        "pivot_high": pivot_high,
                    },
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

    def report_summary_prompt(self, ticker: str, report_text: str):
        system_prompt = f"""
            You are a financial analyst Summarize a {ticker} technical report
            
            The summary must include:
                1) Price Action (1~3 sentences)
                2) Volume (1~3 sentences)
                3) Trend & Pattern (1~3 sentences)
                4) Technical Signals (1~3 sentences)
                5) Support & Resistance (1~3 sentences)
                6) Expected Volatility & Risk (1~3 sentences)
                7) Overall Assessment. (1~3 sentences)
        """

        prompt = f"""
        Please summarize the following original report.
        
        # Report
        {report_text}
        """

        return system_prompt, prompt

    def generate_prompt(
        self,
        data: SignalPromptData,
        report_summary: str | None = "",
        today: str = dt.date.today().strftime("%Y-%m-%d"),
    ) -> str:
        """
        Generate a prompt for the AI model based on the report and description.
        """

        prompt = f"""
        You are deep knowledge of day-swing trader specialising (like a professional trader)
        Ensure recommendations are **realistic** and aligned with short-term trading (1-2 days).
        
        **Date:** {today}
        
        ### Step-by-Step Instructions
        1. THINK: Extract all bullish/bearish signals from the last row of the CSV And Signals. 
        2. REFLECT: Stress-test those signals against the prior all rows and list any conflicts.  
        
        ## Instructions
            ### Analyze Each Stock/ETF:
            - Evaluate the triggered strategies and their technical details
            - Consider fundamental data for stock quality.
            - **Think Relative Strength (RS) against S&P 500**
            - **Analyze And Explain Chart Patterns By Using OHLCV DataFrame CSV**
                - confidence_level: 0.0 ~ 1.0 (0.0 = no pattern, 1.0 = strong pattern) 
            
            ### Provide Recommendations:
            - For each stock/ETF, recommend one of: BUY, SELL, or HOLD.
                For BUY/SELL: [Think First "WHY"]
                - Entry Price: Suggested price to enter today (required)
                - Close Price: Suggested price to close the position today (required)
                - Stop-Loss Price: Suggested Price to exit to limit losses (required)
                - Take-Profit Price: Suggested Price to exit for profit (required)
                
                For HOLD: Explain why no action is recommended (e.g., unclear trend, high risk).

            ### Reasoning:
            - Explain your recommendation step-by-step.
            - Re-Test The signals By Using Input Datas

            ### Constraints:
            - Entry, stop-loss, and take-profit prices must be realistic.
            - Consider short-term trading horizon (1-2 days).
            - Input Data Importance: Stock's OHLCV DataFrame *** > News Headlines **  > Fundamental Data, Report Summary *

        
        ### Input Data
        Below is a JSON array of stocks/ETFs with their previous day's data. Each item includes:
        - `ticker`: Stock/ETF ticker symbol.
        - `last_price`: Closing price from the previous day.
        - `price_change_pct`: Percentage price change from the day before.
        - `triggered_strategies`: List of triggered strategies (e.g., VOLUME_EXPANSION, PULLBACK).
        - `technical_details`: Detailed metrics for each triggered strategy (e.g., RSI, SMA values).
        - `fundamentals`: Fundamental metrics (trailing_pe, eps_surprise_pct, revenue_growth, roe, debt_to_equity, fcf_yield).
        - `news`: Recent news (7 Days Ago ~ Today) headlines
        - `report_summary`: Summary of the technical report.
        - `spy_description`: S&P 500 status (e.g., bullish, bearish, neutral).
        - `additional_info`: Any additional information or context.
        - `Stock's OHLCV DataFrame`: Stock's OHLCV DataFrame.

        
        ```json
        - ticker: {data.ticker}
        - last_price: {data.last_price}
        - price_change_pct: {data.price_change_pct}
        - triggered_strategies: {data.triggered_strategies}
        - technical_details: {data.technical_details}
        - fundamentals: {data.fundamentals}
        - report_summary: {report_summary}
        - S&P 500 Status: {data.spy_description}
        - additional_info: {data.additional_info}
        - Stock's OHLCV DataFrame (Analyze Step By Step): {data.dataframe}
        ```
        """

        return prompt

    def extract_text_only(self, pdf_bytes: bytes) -> str:
        """PDF bytes에서 이미지·벡터 그림을 제외한 순수 텍스트만 추출"""
        full_text: list[str] = []

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()  # 이미지·도형 제외, 글자 서치
                if text:
                    full_text.append(text)

        return "\n\n".join(full_text)

    def fetch_pdf_stock_investment(self, ticker: str) -> bytes:
        """
        Fetch a PDF report for the given stock ticker.
        Returns binary PDF data as bytes.
        """
        url = f"https://stockinvest.us/pdf/technical-analysis/{ticker}"
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
        )
        # 페이지 먼저 열기
        scraper.get(f"https://stockinvest.us/stock/{ticker}", timeout=20)
        r = scraper.get(
            url=url,
            timeout=20,
            headers={
                "Accept": "application/pdf",
                "Referer": f"https://stockinvest.us/stock/{ticker}",
            },
            stream=True,  # chunk 전송 → text 속성 미생성
        )

        r.raise_for_status()
        if not r.headers.get("Content-Type", "").startswith("application/pdf"):
            print("Not a PDF, got:", r.headers.get("Content-Type"))
            return b"None"

        # ★ content를 직접 bytes로 읽기
        raw_pdf = r.content  # 여기서는 decode 없음
        return raw_pdf

    async def _fetch_page(self, start: int = 1) -> list[dict]:
        NAVER_BASE = "https://openapi.naver.com/v1/search/news.json"
        QUERIES = ["nasdaq", "s&p500"]

        items = []

        for query in QUERIES:
            params = {"query": query, "display": 100, "start": start, "sort": "date"}
            async with aiohttp.ClientSession(
                headers={
                    "X-Naver-Client-Id": self.settings.NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": self.settings.NAVER_CLIENT_SECRET,
                }
            ) as session:
                async with session.get(NAVER_BASE, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    items.extend(data["items"])

        if not items:
            return []

        items.sort(key=lambda x: x["pubDate"], reverse=True)
        items = items[:100]

        if len(items) < 100:
            return items
        # 100개 이상인 경우, 최근 100개만 반환
        items = items[:100]
        return items

    async def get_today_items(self) -> List[Article]:
        items, start = [], 1

        items = await self._fetch_page(start)

        three_days_ago = datetime.datetime.now(
            timezone.utc
        ).astimezone().date() - timedelta(days=3)
        today = datetime.datetime.now(timezone.utc).astimezone().date()

        return [
            Article(
                id=it["link"],
                title=html.unescape(re.sub(r"<\/?b>", "", it["title"])),
                summary=html.unescape(re.sub(r"<\/?b>", "", it["description"])),
                url=it["originallink"] or it["link"],
                published=parsedate_to_datetime(it["pubDate"]),
                category="naver",
            )
            for it in items
            if (
                parsedate_to_datetime(it["pubDate"]).date() >= three_days_ago
                and parsedate_to_datetime(it["pubDate"]).date() <= today
            )
        ]

    def generate_web_search_prompt(
        self,
        ticker: str,
        date: datetime.date | str,
    ) -> str:
        ticker = ticker.upper()
        """
        Generate a prompt for web search based on the stock ticker and report summary.
        """
        prompt = f"""
        today is {date} and you are an AI assistant for stock analysis.
        You are a sell-side equity-research assistant with real-time web and market-data access.
        Act like a professional analyst who can quickly gather and analyze information about a stock.
        Find the latest news, press releases, SEC filings, analyst reports, and market chatter for the stock ticker {ticker}.
        
        ╭─ TASK
        │ 1. Search the open web and wire services for:
        │    • Company-specific news, press releases, SEC filings (8-K·6-K) published in the last 7 days.  
        │    • Sell-side research notes, rating / price-target changes, or model updates in the last 7 days.  
        │    • Market chatter: unusual options activity, block trades, rumors in the last 3 days.  
        │ 2. **Classify each item as a short-term catalyst**  
        │    “+” (Bullish), “−” (Bearish), or “0” (Neutral/mixed).  
        │ 3. Pull the latest 30 trading-days of price & volume for TICKER[{ticker}]  
        │    • Close, % chg 3d & 14d & 30d, intraday high-low, vs S&P 500 (RS) and vs sector ETF.  
        │    • Label the short-term price state: **Uptrend / Downtrend / Range-bound**.  
        ╰─ END TASK

        ╭─ SEARCH PROTOCOL (follow exactly)
        │ • Run four separate queries (recency filter --recency=7 unless noted):
        │   ① "Ticker[{ticker}] press release OR corporate site OR 8-K OR 6-K past 7 days"
        │   ② "Ticker[{ticker}] stock news catalyst past 7 days"
        │   ③ "Ticker[{ticker}] analyst report OR price target OR upgrade OR downgrade past 7 days"
        │   ④ "Ticker[{ticker}] unusual options activity OR block trade past 3 days"  --recency=3
        │ • Domains hint (optional): https://www.tradingview.com/symbols/NASDAQ-{ticker}/news/, https://stockscan.io/stocks/{ticker}/news, bloomberg.com, reuters.com
        │ • Fetch max 10 unique docs total. Skip duplicates.
        ╰─ END PROTOCOL
        """
        return prompt

    def generate_us_market_prompt(self, date: str) -> str:
        """Generate a prompt to summarize U.S. market catalysts."""
        prompt = f"""
        today is {date} and you are an AI assistant for U.S. market analysis.
        driving the U.S. stock market. Focus on actionable catalysts investors care about.

        ╭─ TASK
        │ 1. Search the open web for the most important U.S. market catalysts.
        │    • Economic releases (CPI, jobs, FOMC, etc.) around the given date.
        │    • Headlines impacting overall market sentiment.
        │    • Movements in major indexes (S&P 500, NASDAQ, Dow) and notable sectors.
        │ 2. Provide 3-5 concise bullet points summarizing the findings.
        │    • Include closing levels or percentage moves for the major indices if available.
        ╰─ END TASK

        ╭─ SEARCH PROTOCOL
        │ • Use Google Search with recency around {date} to gather information.
        │ • Return "NO DATA" if nothing relevant is found.
        ╰─ END PROTOCOL
        """
        return prompt

    def get_web_search_summary(
        self,
        date: datetime.date,
        type: Literal["ticker", "market"],
        ticker: Optional[str] = "",
    ):
        """
        Generate a summary of web search results for the given stock ticker and date.
        """
        # start_date = date - 1day, end_date = date
        start_date = (date - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (date + dt.timedelta(days=2)).strftime("%Y-%m-%d")

        results = self.web_search_repository.get_search_results(
            result_type=type,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )

        return results

    def get_ticker_news_by_recommendation(
        self, recommendation: str, limit: int, date: Optional[datetime.date] = None
    ) -> list[dict]:
        ticker_counts = self.web_search_repository.get_ticker_counts_by_recommendation(
            recommendation=recommendation,
            limit=limit,
            date=date,
        )
        result = []
        for ticker, _ in ticker_counts:
            items = self.web_search_repository.get_search_results(
                result_type="ticker",
                ticker=ticker,
            )

            result.append(
                {
                    "ticker": ticker,
                    "news": [
                        {
                            "date": it.date_yyyymmdd,
                            "headline": it.headline,
                            "summary": it.summary,
                            "detail_description": it.detail_description,
                            "recommendation": it.recommendation,
                        }
                        for it in items
                    ],
                }
            )
        return result
