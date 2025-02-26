import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta


def get_technical_indicators(df: pd.DataFrame) -> dict:
    """
    df: 캔들 DataFrame (최소 21개 이상의 row 필요)
    yfinance 데이터프레임에 맞게 수정됨
    """
    if len(df) < 21:
        return {}

    # yfinance 데이터프레임은 'Close' 컬럼 사용
    df["MA_9"] = ta.sma(df["Close"], length=9)  # 단순 이동평균
    df["MA_21"] = ta.sma(df["Close"], length=21)
    df["RSI_14"] = ta.rsi(df["Close"], length=14)

    if ta.macd is None or ta.bbands is None or ta.atr is None:
        return {}

    df[["MACD", "MACD_Signal", "MACD_Hist"]] = ta.macd(
        df["Close"], fast=12, slow=26, signal=9
    )[["MACD_12_26_9", "MACDS_12_26_9", "MACDH_12_26_9"]]
    df[["BB_Lower", "BB_MA_20", "BB_Upper"]] = ta.bbands(df["Close"], length=20, std=2)[
        ["BBL_20_2.0", "BBM_20_2.0", "BBU_20_2.0"]
    ]
    df["ATR_14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    df["volatility"] = df["Close"].pct_change().rolling(window=20).std() * (
        252**0.5
    )  # 연간 변동성

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
        "Latest_Close": round(latest["Close"], 2),  # yfinance는 'close'가 아닌 'Close'
        "volatility": round(latest["volatility"], 2),
    }
