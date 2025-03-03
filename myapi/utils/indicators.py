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


def calculate_volatility_from_df(candles_df: pd.DataFrame) -> float:
    """
    candles_df의 'close' 가격을 이용하여 로그 수익률 기반 변동성을 계산합니다.
    """
    candles_df = candles_df.copy()
    candles_df["close"] = candles_df["close"].astype(float)
    # 로그 수익률 계산 (첫 행은 NaN)
    log_close = pd.Series(np.log(candles_df["close"].astype(float)))
    candles_df["log_return"] = log_close.diff()
    # 표본 표준편차에 기간 스케일 적용 (예시: N = 데이터 길이 - 1)
    volatility = candles_df["log_return"].std() * np.sqrt(len(candles_df) - 1)
    return volatility


def compute_atr(df: pd.DataFrame, period=14):
    """
    ATR (Average True Range)를 계산합니다.
    TR은 (고가-저가), |고가-이전종가|, |저가-이전종가| 중 최대값입니다.
    """
    df["previous_close"] = df["close"].shift(1)
    df["high_low"] = df["high"] - df["low"]
    df["high_pc"] = abs(df["high"] - df["previous_close"])
    df["low_pc"] = abs(df["low"] - df["previous_close"])
    df["tr"] = df[["high_low", "high_pc", "low_pc"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=period).mean()  # 단순 이동평균 방식
    return df


def compute_adx(df, period=14):
    """
    ADX (Average Directional Index)를 계산합니다.
    +DM, -DM을 구하고, 이를 ATR로 나눈 후 +DI, -DI, DX, 그리고 ADX를 계산합니다.
    """
    df["previous_high"] = df["high"].shift(1)
    df["previous_low"] = df["low"].shift(1)
    df["up_move"] = df["high"] - df["previous_high"]
    df["down_move"] = df["previous_low"] - df["low"]

    # +DM와 -DM 계산
    df["+dm"] = np.where(
        (df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0
    )
    df["-dm"] = np.where(
        (df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0
    )

    # ATR은 이미 계산된 값을 사용합니다.
    df = compute_atr(df, period)

    # 단순 합계를 사용한 +DI, -DI (Wilder의 smoothing 방식은 좀 더 복잡합니다)
    df["+di"] = 100 * (df["+dm"].rolling(window=period).sum() / df["atr"])
    df["-di"] = 100 * (df["-dm"].rolling(window=period).sum() / df["atr"])

    # DX와 ADX 계산
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].rolling(window=period).mean()
    return df


def get_technical_indicators(df: pd.DataFrame | None, length: int) -> dict:
    """
    df: 캔들 DataFrame (최소 21개 이상의 row 필요)
    """
    if df is None or len(df) < 120:
        raise ValueError("DataFrame must have at least 21 rows. OR Dataframe is None")

    # 이동평균
    df["MA_9"] = calculate_moving_average(df, 9)
    df["MA_21"] = calculate_moving_average(df, 21)
    df["MA_120"] = calculate_moving_average(df, 120)

    # RSI
    df["RSI_14"] = calculate_rsi(df, 14)

    # MACD
    macd_line, signal_line = calculate_macd(df)
    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line

    # 볼린저 밴드
    ma_bb, upper_band, lower_band = calculate_bollinger_bands(df, length, 2)
    df["BB_MA_20"] = ma_bb
    df["BB_Upper"] = upper_band
    df["BB_Lower"] = lower_band

    # ATR
    df["ATR_14"] = calculate_atr(df)

    df["volatility"] = calculate_volatility_from_df(df)

    df = compute_adx(df)

    latest = df.iloc[0]

    return {
        "MA_short_9": round(latest["MA_9"], 2),
        "MA_long_21": round(latest["MA_21"], 2),
        "MA_long_120": round(latest["MA_120"], 2),
        "RSI_14": round(latest["RSI_14"], 2),
        "MACD": round(latest["MACD"], 2),
        "MACD_Signal": round(latest["MACD_Signal"], 2),
        "BB_MA_20": round(latest["BB_MA_20"], 2),
        "BB_Upper": round(latest["BB_Upper"], 2),
        "BB_Lower": round(latest["BB_Lower"], 2),
        "ADX": round(latest["adx"], 2),
        "ATR_14": round(latest["ATR_14"], 2),
        "Latest_Close": round(latest["close"], 2),
        "Current": round(latest["open"], 2),
        "volatility": round(latest["volatility"], 2),
        "high": round(latest["high"], 2),
    }
