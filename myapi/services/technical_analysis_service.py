from datetime import date, timedelta
from typing import List, Optional, Union
import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf

from myapi.domain.signal.signal_schema import TechnicalSignal, Strategy, FundamentalData

logger = logging.getLogger(__name__)


def safe_float(val):
    """안전한 float 변환"""
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
    """MultiIndex 컬럼을 평탄화"""
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    if df.columns.nlevels == 3:
        df = df.droplevel(0, axis=1)

    if df.columns.nlevels == 2:
        level_vals = df.columns.get_level_values(0)
        unique_tickers = level_vals.unique()

        if len(unique_tickers) == 1 or ticker is None:
            df = df.droplevel(0, axis=1)
        else:
            result = df.xs(ticker, level=0, axis=1)
            if isinstance(result, pd.Series):
                df = pd.DataFrame(result)
            else:
                df = result

    df.columns.name = None
    return df


class TechnicalAnalysisService:
    """기술적 분석 전용 서비스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def fetch_ohlcv(
        self,
        ticker: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        days_back: int = 365,
    ) -> pd.DataFrame:
        """OHLCV 데이터 조회"""
        try:
            if start is not None and end is not None:
                df = yf.download(
                    ticker,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    auto_adjust=True,
                    progress=False,
                )
            else:
                if start is None:
                    start = date.today() - timedelta(days=days_back)
                df = yf.download(
                    ticker,
                    start=start.isoformat(),
                    end=date.today().isoformat(),
                    auto_adjust=True,
                    progress=False,
                )

            if df is None:
                self.logger.warning(f"No data found for ticker: {ticker}")
                return pd.DataFrame()

            if df.empty:
                self.logger.warning(f"No data found for ticker: {ticker}")
                return pd.DataFrame()

            df = df.drop(columns=["Dividends", "Stock Splits"], errors="ignore")
            df.index.name = "Date"
            return flatten_price_columns(df, ticker)

        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    def add_indicators(
        self, df: pd.DataFrame, spy_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """기술적 지표 추가"""
        if df.empty:
            return df

        df = df.copy()

        # 기본 이동평균
        df["SMA5"] = ta.sma(df["Close"], 5)
        df["SMA10"] = ta.sma(df["Close"], 10)
        df["SMA20"] = ta.sma(df["Close"], 20)
        df["SMA50"] = ta.sma(df["Close"], 50)
        df["SMA200"] = ta.sma(df["Close"], 200)
        df["SMA150"] = ta.sma(df["Close"], 150)

        # 거래량 지표
        df["VOL20"] = df["Volume"].rolling(20).mean()
        df["VOL_Z"] = (df["Volume"] - df["VOL20"]) / df["Volume"].rolling(20).std()
        df["VOL_PCTL60"] = df["Volume"].rank(pct=True, method="max")
        df["VolumeSpike"] = df["Volume"] > df["VOL20"] * 2
        df["VolumeSpikeStrength"] = df["Volume"] / df["VOL20"]

        # 오실레이터
        df["RSI14"] = ta.rsi(df["Close"], length=14)
        df["RSI5"] = ta.rsi(df["Close"], length=5)
        df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        # 볼린저 밴드
        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None:
            df = pd.concat([df, bb], axis=1)

        # MACD
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)

        # Stochastic
        stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=14, d=3, smooth_k=3)
        if stoch is not None:
            df = pd.concat([df, stoch], axis=1)

        # ADX
        adx = ta.adx(df["High"], df["Low"], df["Close"], length=14)
        if adx is not None:
            df = pd.concat([df, adx], axis=1)

        # SuperTrend
        supertrend = ta.supertrend(
            df["High"], df["Low"], df["Close"], length=10, multiplier=3
        )
        if supertrend is not None:
            df = pd.concat([df, supertrend], axis=1)

        # Donchian Channel
        donch = ta.donchian(df["High"], df["Low"], length=20)
        if donch is not None:
            df = pd.concat([df, donch], axis=1)

        # 추가 지표들
        df["VWAP"] = ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"])
        df["ROC1"] = ta.roc(df["Close"], length=1)
        df["ROC3"] = ta.roc(df["Close"], length=3)
        df["ROC5"] = ta.roc(df["Close"], length=5)
        df["SMA50_SLOPE"] = df["SMA50"].diff()
        df["BB_WIDTH"] = (df["BBU_20_2.0"] - df["BBL_20_2.0"]) / df["Close"]
        df["ATR_PCT"] = (df["ATR14"] / df["Close"]) * 100
        df["GAP_PCT"] = df["Open"] / df["Close"].shift(1) - 1
        df["ATR_RATIO"] = df["ATR14"] / df["ATR14"].rolling(20).mean()

        # 캔들 패턴
        df["BULL_ENGULF"] = (
            (df["Close"].shift(1) < df["Open"].shift(1))
            & (df["Open"] < df["Close"].shift(1))
            & (df["Close"] > df["Open"].shift(1))
        )

        # VCP 지표
        long_win, short_win = 20, 5
        df["RANGE_LONG"] = (
            df["High"].rolling(long_win).max() - df["Low"].rolling(long_win).min()
        ) / df["Low"].rolling(long_win).min()
        df["RANGE_SHORT"] = (
            df["High"].rolling(short_win).max() - df["Low"].rolling(short_win).min()
        ) / df["Low"].rolling(short_win).min()
        df["VCP_VOL_REL"] = df["Volume"] / df["Volume"].rolling(long_win).mean()

        # 상대강도 계산
        if spy_df is not None:
            df = self._add_relative_strength(df, spy_df)

        return df.dropna(how="all").reset_index(drop=False).set_index("Date")

    def _add_relative_strength(
        self, df: pd.DataFrame, spy_df: pd.DataFrame
    ) -> pd.DataFrame:
        """상대강도 지표 추가"""
        try:
            spy_close = spy_df["Close"].reindex(df.index).ffill()

            for period, col in [(20, "RS_SHORT"), (60, "RS_MID")]:
                ticker_ret = df["Close"].pct_change(period)
                spy_ret = spy_close.pct_change(period)
                df[col] = (ticker_ret - spy_ret) * 100
        except Exception as e:
            self.logger.warning(f"Failed to compute RS data: {e}")

        return df

    def evaluate_signals(
        self, df: pd.DataFrame, strategies: List[Strategy]
    ) -> List[TechnicalSignal]:
        """기술적 신호 평가"""
        if df.empty:
            return []

        signals = []
        cols = set(df.columns)

        # 최신 데이터 추출
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else None

        for strategy in strategies:
            signal = self._evaluate_strategy(strategy, df, last_row, prev_row, cols)
            if signal:
                signals.append(signal)

        return signals

    def _evaluate_strategy(
        self, strategy: Strategy, df: pd.DataFrame, last_row, prev_row, cols
    ) -> TechnicalSignal:
        """개별 전략 평가"""

        if strategy == "PULLBACK":
            triggered = (
                "SMA10" in cols
                and "SMA50" in cols
                and last_row["Close"] <= last_row["SMA10"] * 1.03
                and last_row["Close"] >= last_row["SMA50"] * 0.98
            )
            return TechnicalSignal(
                strategy=strategy,
                triggered=triggered,
                details={
                    "close": last_row["Close"],
                    "sma10": last_row.get("SMA10"),
                    "sma50": last_row.get("SMA50"),
                },
            )

        elif strategy == "OVERSOLD":
            triggered = (
                "RSI14" in cols
                and "BBL_20_2.0" in cols
                and "STOCHk_14_3_3" in cols
                and last_row["RSI14"] < 40
                and last_row["Close"] <= last_row["BBL_20_2.0"] * 1.02
                and last_row["STOCHk_14_3_3"] < 30
            )
            return TechnicalSignal(
                strategy=strategy,
                triggered=triggered,
                details={
                    "rsi": last_row.get("RSI14"),
                    "bbl": last_row.get("BBL_20_2.0"),
                    "stoch_k": last_row.get("STOCHk_14_3_3"),
                },
            )

        elif strategy == "VOLUME_SPIKE":
            vol_ratio = last_row["Volume"] / last_row["VOL20"] if "VOL20" in cols else 0
            price_change = df["Close"].pct_change().iloc[-1] if len(df) > 1 else 0
            triggered = (
                "VolumeSpike" in cols
                and last_row["VolumeSpike"]
                and last_row.get("RSI14", 50) < 50
                and price_change > 0.01
            )
            return TechnicalSignal(
                strategy=strategy,
                triggered=triggered,
                details={
                    "volume": last_row["Volume"],
                    "vol20": last_row.get("VOL20"),
                    "vol_ratio": vol_ratio,
                    "price_change_pct": price_change * 100,
                },
            )

        # 다른 전략들도 비슷하게 구현...

        return TechnicalSignal(strategy=strategy, triggered=False, details={})

    def fetch_fundamentals(self, ticker: str) -> FundamentalData:
        """펀더멘털 데이터 조회"""
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or tk.fast_info or {}

            return FundamentalData(
                trailing_pe=info.get("peTrailing") or info.get("trailingPE"),
                eps_surprise_pct=self._get_eps_surprise(tk),
                revenue_growth=self._get_revenue_growth(tk),
                roe=self._calculate_roe(tk),
                debt_to_equity=self._calculate_debt_to_equity(tk),
                fcf_yield=self._calculate_fcf_yield(tk),
            )
        except Exception as e:
            self.logger.error(f"Error fetching fundamentals for {ticker}: {e}")
            return FundamentalData()

    def _get_eps_surprise(self, tk: yf.Ticker) -> float | None:
        """EPS 서프라이즈 계산"""
        try:
            hist = tk.get_earnings_history()
            if isinstance(hist, pd.DataFrame) and not hist.empty:
                last = hist.iloc[0].to_dict()
                est = last.get("epsEstimate")
                act = last.get("epsActual")
                if est and act:
                    return (act - est) / abs(est) * 100
            elif hist is not None and isinstance(hist, list) and len(hist) > 0:
                last = hist[0]
                est = last.get("epsEstimate")
                act = last.get("epsActual")
                if est and act:
                    return (act - est) / abs(est) * 100
        except Exception:
            pass
        return None

    def _get_revenue_growth(self, tk: yf.Ticker) -> float | None:
        """매출 성장률 계산"""
        try:
            fin = tk.get_income_stmt(freq="quarterly")
            if (
                isinstance(fin, pd.DataFrame)
                and "TotalRevenue" in fin.index
                and fin.shape[1] >= 5
            ):
                rev_now = safe_float(fin.iloc[fin.index.get_loc("TotalRevenue"), 0])
                rev_yearago = safe_float(fin.iloc[fin.index.get_loc("TotalRevenue"), 4])

                if rev_now is not None and rev_yearago is not None and rev_yearago != 0:
                    return (rev_now - rev_yearago) / abs(rev_yearago) * 100
        except Exception as e:
            self.logger.warning(f"Error calculating revenue growth: {e}")
        return None

    def _calculate_roe(self, tk: yf.Ticker) -> float | None:
        """ROE 계산"""
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

                net_income_val = safe_float(net_income)
                equity_val = safe_float(equity)

                if (
                    net_income_val is not None
                    and equity_val is not None
                    and equity_val != 0
                ):
                    return net_income_val / equity_val * 100
        except Exception as e:
            self.logger.warning(f"Error calculating ROE: {e}")
        return None

    def _calculate_debt_to_equity(self, tk: yf.Ticker) -> float | None:
        """부채비율 계산"""
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

                debt_val = safe_float(total_debt)
                equity_val = safe_float(equity)

                if debt_val is not None and equity_val is not None and equity_val != 0:
                    return debt_val / equity_val
        except Exception as e:
            self.logger.warning(f"Error calculating debt-to-equity: {e}")
        return None

    def _calculate_fcf_yield(self, tk: yf.Ticker) -> float | None:
        """FCF 수익률 계산"""
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
                    fcf_val = safe_float(fcf)
                    if fcf_val is not None:
                        return fcf_val / market_cap * 100
        except Exception as e:
            self.logger.warning(f"Error calculating FCF yield: {e}")
        return None
