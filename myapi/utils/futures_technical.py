from dataclasses import dataclass
import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

from myapi.domain.futures.futures_schema import TradingSignal

logger = logging.getLogger(__name__)

# =========================
# 1) Dataclasses 정의
# =========================


@dataclass
class IndicatorResults:
    """calculate_all_indicators()가 반환하는 구조"""

    pivot_points: Dict[str, float]
    bollinger_bands: Dict[str, float]
    macd: Dict[str, float]  # {"macd": float, "signal": float, "histogram": float}
    macd_divergence: bool
    rsi: float
    rsi_divergence: bool
    fibonacci_levels: Dict[str, float]
    volume_analysis: str
    heikin_ashi: Dict[
        str, float
    ]  # {"ha_open": float, "ha_close": float, "ha_high": float, "ha_low": float}


@dataclass
class TradingSignalResult:
    """generate_trading_signal()가 반환하는 최종 거래 시그널"""

    signal: str  # "long", "short", "hold"
    confidence: float  # 0 ~ 100 (가중치를 합산한 신뢰도)
    explanation: str  # 결정 근거 요약


# =========================
# 2) 기본 지표 계산 함수들
# =========================


def calculate_all_indicators(df: pd.DataFrame, lookback: int = 5) -> IndicatorResults:
    """
    OHLCV 데이터를 받아서 주요 지표를 모두 계산 후, IndicatorResults 형태로 반환.
    df 컬럼: ['timestamp','open','high','low','close','volume']
    """
    if len(df) < lookback + 2:
        # 데이터가 매우 적으면 예외처리
        raise ValueError("Dataframe length is too short to calculate indicators.")

    # 1) Pivot Points
    pivot_points = _calculate_pivot_points(df)

    # 2) Bollinger Bands
    bb = _calculate_bollinger_bands(df, window=20, num_std=2)

    # 3) MACD + Divergence
    macd_res = _calculate_macd(df)
    macd_div = _detect_divergence_advanced(
        df, macd_res["macd_series"], lookback=lookback
    )

    # 4) RSI + Divergence
    rsi_series = _calculate_rsi(df, period=14)
    rsi_latest = rsi_series.iloc[-1] if not rsi_series.empty else np.nan
    rsi_div = _detect_divergence_advanced(df, rsi_series, lookback=lookback)

    # 5) Fibonacci
    fibo = _calculate_fibonacci(df)

    # 6) Volume Analysis
    volume_stat = _analyze_volume(df, lookback=lookback)

    # 7) Heikin Ashi
    ha_df = _calculate_heikin_ashi(df)
    ha_latest = {
        "ha_open": ha_df["HA_Open"].iloc[-1],
        "ha_close": ha_df["HA_Close"].iloc[-1],
        "ha_high": ha_df["HA_High"].iloc[-1],
        "ha_low": ha_df["HA_Low"].iloc[-1],
    }

    return IndicatorResults(
        pivot_points=pivot_points,
        bollinger_bands=bb,
        macd={
            "macd": macd_res["last_macd"],
            "signal": macd_res["last_signal"],
            "histogram": macd_res["histogram"],
        },
        macd_divergence=macd_div,
        rsi=rsi_latest,
        rsi_divergence=rsi_div,
        fibonacci_levels=fibo,
        volume_analysis=volume_stat,
        heikin_ashi=ha_latest,
    )


def _calculate_pivot_points(df: pd.DataFrame) -> Dict[str, float]:
    last_candle = df.iloc[-1]
    pivot = (last_candle["high"] + last_candle["low"] + last_candle["close"]) / 3
    support1 = 2 * pivot - last_candle["high"]
    resistance1 = 2 * pivot - last_candle["low"]
    support2 = pivot - (last_candle["high"] - last_candle["low"])
    resistance2 = pivot + (last_candle["high"] - last_candle["low"])
    return {
        "pivot": pivot,
        "support1": support1,
        "resistance1": resistance1,
        "support2": support2,
        "resistance2": resistance2,
    }


def _calculate_bollinger_bands(
    df: pd.DataFrame, window: int = 20, num_std: int = 2
) -> Dict[str, float]:
    rolling_mean = df["close"].rolling(window=window).mean()
    rolling_std = df["close"].rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return {
        "middle": rolling_mean.iloc[-1],
        "upper": upper_band.iloc[-1],
        "lower": lower_band.iloc[-1],
    }


def _calculate_macd(df: pd.DataFrame) -> Dict[str, Any]:
    exp12 = df["close"].ewm(span=12, adjust=False).mean()
    exp26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal

    result = {
        "macd_series": macd,
        "signal_series": signal,
        "hist_series": histogram,
        "last_macd": macd.iloc[-1],
        "last_signal": signal.iloc[-1],
        "histogram": histogram.iloc[-1],
    }
    return result


def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """단순 RSI 계산 (벡터화)"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)


def _detect_divergence_advanced(
    df: pd.DataFrame, indicator: pd.Series, lookback: int = 5
) -> bool:
    recent_prices = df["close"].iloc[-lookback:]
    recent_indicator = indicator.iloc[-lookback:]
    price_high = recent_prices.max()
    price_low = recent_prices.min()
    indicator_high = recent_indicator.max()
    indicator_low = recent_indicator.min()

    current_price = df["close"].iloc[-1]
    current_indicator = indicator.iloc[-1]

    divergence = (
        current_price >= price_high and current_indicator < indicator_high
    ) or (current_price <= price_low and current_indicator > indicator_low)
    return divergence


def _calculate_fibonacci(df: pd.DataFrame) -> Dict[str, float]:
    high = df["high"].max()
    low = df["low"].min()
    diff = high - low
    fib_levels = {
        "0.0%": high,
        "23.6%": high - (diff * 0.236),
        "38.2%": high - (diff * 0.382),
        "50.0%": high - (diff * 0.5),
        "61.8%": high - (diff * 0.618),
        "100.0%": low,
    }
    return fib_levels


def _analyze_volume(df: pd.DataFrame, lookback: int = 5) -> str:
    """매우 단순화된 거래량 추세."""
    recent_vol = df["volume"].iloc[-lookback:]
    vol_diff_mean = recent_vol.diff().mean()
    price_diff_mean = df["close"].iloc[-lookback:].diff().mean()
    if vol_diff_mean > 0 and price_diff_mean > 0:
        return "strong"
    elif vol_diff_mean < 0 and price_diff_mean > 0:
        return "weak"
    else:
        return "neutral"


def _calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha_df = df.copy()
    ha_df["HA_Close"] = (
        ha_df["open"] + ha_df["high"] + ha_df["low"] + ha_df["close"]
    ) / 4
    ha_df["HA_Open"] = 0.0
    ha_df.loc[ha_df.index[0], "HA_Open"] = (
        pd.to_numeric(ha_df.loc[ha_df.index[0], "open"], errors="coerce")
        + pd.to_numeric(ha_df.loc[ha_df.index[0], "close"], errors="coerce")
    ) / 2

    for i in range(1, len(ha_df)):
        ha_df.loc[ha_df.index[i], "HA_Open"] = (
            pd.to_numeric(ha_df.loc[ha_df.index[i - 1], "HA_Open"], errors="coerce")
            + pd.to_numeric(ha_df.loc[ha_df.index[i - 1], "HA_Close"], errors="coerce")
        ) / 2.0

    ha_df["HA_High"] = ha_df[["high", "HA_Open", "HA_Close"]].max(axis=1)
    ha_df["HA_Low"] = ha_df[["low", "HA_Open", "HA_Close"]].min(axis=1)
    return ha_df


# =========================
# 2.3. 거래 로직 관련 지표 계산 (SKIP 부분 추가)
# =========================


def _calculate_indicators_ema_stoch(df: pd.DataFrame) -> pd.DataFrame:
    """
    EMA200, Stochastic RSI를 계산하여 df에 컬럼 추가 후 반환.
    - df.columns: ['open','high','low','close','volume']
    """
    result = df.copy()

    # 1) EMA200 계산
    result["EMA200"] = result["close"].ewm(span=200, min_periods=200).mean()

    # 2) Stochastic RSI 계산
    length = 14
    smoothK = 3
    smoothD = 3

    delta = result["close"].diff()
    ups = delta.clip(lower=0).rolling(length).mean()
    downs = (-delta.clip(upper=0)).rolling(length).mean()
    rs = ups / (downs + 1e-8)
    rsi = 100 - 100 / (1 + rs)

    rsi_min = rsi.rolling(length).min()
    rsi_max = rsi.rolling(length).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-8) * 100
    result["%K"] = stoch.rolling(smoothK).mean()
    result["%D"] = result["%K"].rolling(smoothD).mean()

    return result


def _calculate_indicators_sma_ribon(df: pd.DataFrame) -> pd.DataFrame:
    """
    SMA(5,8,13), Bollinger Band(20,2.5), Stochastic (14-3-3) 같은
    'SMA 리본 + 볼린저 + 스토캐스틱' 로직을 하나로 계산해 df에 추가 후 반환.
    """
    result = df.copy()

    # SMA 계산
    result["sma5"] = result["close"].rolling(window=5).mean()
    result["sma8"] = result["close"].rolling(window=8).mean()
    result["sma13"] = result["close"].rolling(window=13).mean()

    # 볼린저 밴드 계산 (20바, 2.5 표준편차)
    window = 20
    std_dev = 2.5
    result["bb_middle"] = result["close"].rolling(window=window).mean()
    result["bb_std"] = result["close"].rolling(window=window).std()
    result["bb_upper"] = result["bb_middle"] + (result["bb_std"] * std_dev)
    result["bb_lower"] = result["bb_middle"] - (result["bb_std"] * std_dev)

    # 스토캐스틱 (14-3-3)
    window_stoch = 14
    result["lowest_low"] = result["low"].rolling(window=window_stoch).min()
    result["highest_high"] = result["high"].rolling(window=window_stoch).max()
    result["stoch_k"] = (
        (
            100
            * (result["close"] - result["lowest_low"])
            / (result["highest_high"] - result["lowest_low"] + 1e-8)
        )
        .rolling(3)
        .mean()
    )  # %K -> 3번 평활
    result["stoch_d"] = result["stoch_k"].rolling(3).mean()  # %D -> %K의 3번 평활

    return result


# =========================
# 3) 최종 시그널 생성 함수
# =========================


def generate_trading_signal(
    df: pd.DataFrame, indicators: IndicatorResults
) -> TradingSignalResult:
    """
    기술 지표 + 보조 계산 결과를 종합하여 long/short/hold 결정을 내리는 로직.
    df: OHLCV (예: 5분봉)
    indicators: calculate_all_indicators() 호출 결과
    """
    # (1) EMA/Stoch 계산
    df_ema_stoch = _calculate_indicators_ema_stoch(df)
    last = df_ema_stoch.iloc[-1]

    explanations = []
    confidence = 0.0
    final_signal = "hold"

    # ---- EMA200 기반 추세판단 ----
    if last["close"] > last["EMA200"]:
        explanations.append("Price above EMA200 => bullish bias (+20)")
        confidence += 20
    else:
        explanations.append("Price below EMA200 => bearish bias (-20)")
        confidence -= 20

    # ---- Stochastic 골든/데드 크로스 ----
    golden_cross = (
        df_ema_stoch["%K"].iloc[-2] < df_ema_stoch["%D"].iloc[-2]
        and df_ema_stoch["%K"].iloc[-1] > df_ema_stoch["%D"].iloc[-1]
    )
    dead_cross = (
        df_ema_stoch["%K"].iloc[-2] > df_ema_stoch["%D"].iloc[-2]
        and df_ema_stoch["%K"].iloc[-1] < df_ema_stoch["%D"].iloc[-1]
    )
    if golden_cross:
        explanations.append("Stoch RSI Golden Cross => bullish momentum (+15)")
        confidence += 15
    elif dead_cross:
        explanations.append("Stoch RSI Dead Cross => bearish momentum (-15)")
        confidence -= 15

    # (2) SMA/Bollinger
    df_sma = _calculate_indicators_sma_ribon(df)
    last_sma = df_sma.iloc[-1]
    # 예시: SMA5 > SMA8 > SMA13 이면 bullish, 그 반대면 bearish, etc.
    if last_sma["sma5"] > last_sma["sma8"] > last_sma["sma13"]:
        explanations.append("SMA Ribbon is bullish aligned (+10)")
        confidence += 10
    elif last_sma["sma5"] < last_sma["sma8"] < last_sma["sma13"]:
        explanations.append("SMA Ribbon is bearish aligned (-10)")
        confidence -= 10

    # 볼린저 밴드 예시: close가 upper band보다 높으면 과매수, lower band보다 낮으면 과매도
    if last_sma["close"] > last_sma["bb_upper"]:
        explanations.append("Close above BB upper => potential overbought (-5)")
        confidence -= 5
    elif last_sma["close"] < last_sma["bb_lower"]:
        explanations.append("Close below BB lower => potential oversold (+5)")
        confidence += 5

    # (3) MACD/RSI 발산, 헤이킨 아시
    if indicators.macd_divergence:
        explanations.append("MACD Divergence => caution, possible reversal (-10)")
        confidence -= 10
    if indicators.rsi_divergence:
        explanations.append("RSI Divergence => caution, possible reversal (-10)")
        confidence -= 10

    # 헤이킨 아시
    ha_open = indicators.heikin_ashi["ha_open"]
    ha_close = indicators.heikin_ashi["ha_close"]
    if ha_close > ha_open:
        explanations.append("Heikin Ashi bullish candle => short-term bullish (+10)")
        confidence += 10
    else:
        explanations.append("Heikin Ashi bearish candle => short-term bearish (-10)")
        confidence -= 10

    # (4) 최종 결정
    # 임계값 예시: +20 이상 => long, -20 이하 => short, 그외 hold
    if confidence >= 20:
        final_signal = "long"
    elif confidence <= -20:
        final_signal = "short"
    else:
        final_signal = "hold"

    explanation_text = "\n".join(explanations)
    # confidence를 0~100 사이로 제한
    final_confidence = max(min(confidence, 100), 0)

    return TradingSignalResult(
        signal=final_signal, confidence=final_confidence, explanation=explanation_text
    )
