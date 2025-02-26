# 헬퍼 함수 정의
def calculate_moving_average(df: pd.DataFrame, period: int) -> pd.Series:
    return df["Close"].rolling(window=period).mean()


def calculate_rsi(df: pd.DataFrame, period: int) -> pd.Series:
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def calculate_bollinger_bands(df: pd.DataFrame, period: int, std_dev: float) -> tuple:
    ma = df["Close"].rolling(window=period).mean()
    std = df["Close"].rolling(window=period).std()
    upper_band = ma + (std * std_dev)
    lower_band = ma - (std * std_dev)
    return ma, upper_band, lower_band


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_volatility_from_df(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return df["Close"].pct_change().rolling(window=period).std() * (252**0.5)


# 원래 함수
def get_technical_indicators(df: pd.DataFrame) -> dict:
    if len(df) < 21:
        return {}

    df["MA_9"] = calculate_moving_average(df, 9)
    df["MA_21"] = calculate_moving_average(df, 21)
    df["RSI_14"] = calculate_rsi(df, 14)
    macd_line, signal_line = calculate_macd(df)
    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line
    ma_bb, upper_band, lower_band = calculate_bollinger_bands(df, 20, 2)
    df["BB_MA_20"] = ma_bb
    df["BB_Upper"] = upper_band
    df["BB_Lower"] = lower_band
    df["ATR_14"] = calculate_atr(df)
    df["volatility"] = calculate_volatility_from_df(df)

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
        "Latest_Close": round(latest["Close"], 2),
        "volatility": round(latest["volatility"], 2),
    }
