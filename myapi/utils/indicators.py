# app/utils/indicators.py
import pandas as pd
import numpy as np


def calculate_moving_average(df: pd.DataFrame, window: int) -> pd.Series:
    return df["close"].rolling(window=window).mean()


def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calculate_macd(df: pd.DataFrame, short_span=12, long_span=26, signal_span=9):
    ema_short = df["close"].ewm(span=short_span, adjust=False).mean()
    ema_long = df["close"].ewm(span=long_span, adjust=False).mean()
    macd_line = ema_short - ema_long
    signal_line = macd_line.ewm(span=signal_span, adjust=False).mean()
    return macd_line, signal_line


def calculate_bollinger_bands(df: pd.DataFrame, window=20, num_std=2):
    ma = df["close"].rolling(window=window).mean()
    std = df["close"].rolling(window=window).std()
    upper_band = ma + num_std * std
    lower_band = ma - num_std * std
    return ma, upper_band, lower_band


def calculate_atr(df: pd.DataFrame, window=14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=window, min_periods=window).mean()
    return atr


def get_technical_indicators(df: pd.DataFrame) -> dict:
    """
    df: 캔들 DataFrame (최소 21개 이상의 row 필요)
    """
    if len(df) < 21:
        return {}

    # 이동평균
    df["MA_9"] = calculate_moving_average(df, 9)
    df["MA_21"] = calculate_moving_average(df, 21)

    # RSI
    df["RSI_14"] = calculate_rsi(df, 14)

    # MACD
    macd_line, signal_line = calculate_macd(df)
    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line

    # 볼린저 밴드
    ma_bb, upper_band, lower_band = calculate_bollinger_bands(df, 20, 2)
    df["BB_MA_20"] = ma_bb
    df["BB_Upper"] = upper_band
    df["BB_Lower"] = lower_band

    # ATR
    df["ATR_14"] = calculate_atr(df)

    latest = df.iloc[-1]
    return {
        "MA_short_9": round(latest["MA_9"], 2),
        "MA_long_21": round(latest["MA_21"], 2),
        "RSI_14": round(latest["RSI_14"], 2),
        "MACD": round(latest["MACD"], 2),
        "MACD_Signal": round(latest["MACD_Signal"], 2),
        "BB_MA_20": round(latest["BB_MA_20"], 2),
        "BB_Upper": round(latest["BB_Upper"], 2),
        "BB_Lower": round(latest["BB_Lower"], 2),
        "ATR_14": round(latest["ATR_14"], 2),
        "Latest_Close": round(latest["close"], 2),
    }
