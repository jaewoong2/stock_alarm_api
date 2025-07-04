import io
import matplotlib
from matplotlib import pyplot as plt
import pandas as pd
import numpy as np


matplotlib.use(
    "Agg", force=True
)  # GUI 백엔드 대신 Agg 사용 (반드시 import plt 전에 호출)
import mplfinance as mpf


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

    # 단순 합계를 사용한 +DI, -DI (Wilder의 smoothing과는 다릅니다)
    df["+di"] = 100 * (df["+dm"].rolling(window=period).sum() / df["atr"])
    df["-di"] = 100 * (df["-dm"].rolling(window=period).sum() / df["atr"])

    # DX와 ADX 계산
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].rolling(window=period).mean()
    return df


def plot_with_indicators(df: pd.DataFrame, length: int):

    if not isinstance(df.index, pd.DatetimeIndex):
        if pd.api.types.is_numeric_dtype(df.index):
            df.index = pd.to_datetime(df.index, unit="ms")
        else:
            raise ValueError(
                "DataFrame index must be a DatetimeIndex or numeric timestamp"
            )

    # 커스텀 스타일 설정
    custom_style = mpf.make_mpf_style(
        base_mpf_style="yahoo",
        rc={
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "lines.linewidth": 1.5,
        },
        marketcolors=mpf.make_marketcolors(
            up="green", down="red", wick="black", volume="gray", edge="black", alpha=0.8
        ),
        mavcolors=["blue", "orange", "green"],  # 이동평균선 색상 지정
    )

    # 추가 플롯 설정 (범례와 함께)
    add_plots = [
        mpf.make_addplot(
            df["MA_9"], panel=0, width=1.2, linestyle="solid", color="blue", label="MA9"
        ),
        mpf.make_addplot(
            df["MA_21"],
            panel=0,
            width=1.2,
            linestyle="solid",
            color="orange",
            label="MA21",
        ),
        mpf.make_addplot(
            df["MA_120"],
            panel=0,
            width=1.2,
            linestyle="solid",
            color="green",
            label="MA120",
        ),
        mpf.make_addplot(
            df["BB_Upper"],
            panel=0,
            width=0.8,
            linestyle="dashdot",
            color="purple",
            label="BB Upper",
        ),
        mpf.make_addplot(
            df["BB_Lower"],
            panel=0,
            width=0.8,
            linestyle="dashdot",
            color="purple",
            label="BB Lower",
        ),
        mpf.make_addplot(
            df["RSI_14"],
            panel=1,
            color="lime",
            width=1.2,
            ylabel="RSI(14)",
            label="RSI",
        ),
        mpf.make_addplot(
            df["MACD"], panel=2, color="fuchsia", width=1.2, ylabel="MACD", label="MACD"
        ),
        mpf.make_addplot(
            df["MACD_Signal"], panel=2, color="blue", width=1.2, label="MACD Signal"
        ),
    ]

    if "adx" in df.columns:
        add_plots.append(
            mpf.make_addplot(
                df["adx"], panel=3, color="orange", width=1.2, ylabel="ADX", label="ADX"
            )
        )

    # 차트 그리기 옵션
    mpf_kwargs = {
        "type": "candle",
        "volume": True,
        "addplot": add_plots,
        "figratio": (20, 12),  # 더 큰 비율로 설정
        "figscale": 1.5,  # 크기 확장
        "title": f"Candlestick Chart with Indicators (BB_{length})",
        "tight_layout": True,
        "style": custom_style,
        "panel_ratios": (3, 1, 1, 1),
        "show_nontrading": False,  # 비거래 시간 제외
        "datetime_format": "%Y-%m-%d %H:%M:%S",  # 상세한 시간 형식
        "xrotation": 45,  # X축 레이블 회전
        "scale_padding": {
            "left": 0.5,
            "right": 0.5,
            "top": 0.5,
            "bottom": 0.5,
        },  # 여백 조정
    }

    fig = mpf.plot(df, **mpf_kwargs, returnfig=True)
    # 범례 추가
    max_price = df["high"].max()
    min_price = df["low"].min()
    ax = fig[0].get_axes()[0]
    ax.annotate(
        f"Max: {max_price:.2f}",
        xy=(0.05, 0.95),
        xycoords="axes fraction",
        fontsize=10,
        color="black",
    )
    ax.annotate(
        f"Min: {min_price:.2f}",
        xy=(0.05, 0.90),
        xycoords="axes fraction",
        fontsize=10,
        color="black",
    )

    start_time = df.index[0].strftime("%Y-%m-%d %H:%M:%S")
    end_time = df.index[-1].strftime("%Y-%m-%d %H:%M:%S")
    ax.annotate(
        f"Start: {start_time}",
        xy=(0.05, 0.85),
        xycoords="axes fraction",
        fontsize=10,
        color="black",
    )
    ax.annotate(
        f"End: {end_time}",
        xy=(0.05, 0.80),
        xycoords="axes fraction",
        fontsize=10,
        color="black",
    )
    handles, labels = ax.get_legend_handles_labels()
    fig[0].legend(handles, labels, loc="upper left", fontsize=10)

    buffer = io.BytesIO()
    fig[0].savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig[0])
    buffer.seek(0)
    return buffer
