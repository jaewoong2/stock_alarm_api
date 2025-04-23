"""
하위 TF 역방향 → 다시 대세 방향 복귀” 구조는 검증된 트렌드‑팔로 + 눌림 매수 기법으로
① 다중 TF 추세 강도(ADX) 필터, ② 복귀 신호의 다중 확인(MACD·BB·RSI), ③ ATR‑기반 동적 SL/TP
과도한 역추세 스캘핑을 억제하면서 추세 재개 구간만

"""

from typing import Dict, List, Literal
import pandas as pd
import pandas_ta as ta

from myapi.domain.futures.futures_schema import (
    IndiCfg,
    ResumptionConfiguration,
    RiskConfiguration,
    SignalResult,
    TimeFrameConfiguration,
)


def add_pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    전일(shift=1) 기준 Pivot Point 및 R1/S1~R3/S3 계산 후
    원본 DataFrame에 컬럼으로 추가합니다.
    """
    d = df.copy()

    # 전일 고·저·종가
    ph = d["high"].shift(1)
    pl = d["low"].shift(1)
    pc = d["close"].shift(1)

    # Pivot Point (PP)
    d["PP"] = (ph + pl + pc) / 3
    d["P"] = (ph + pl + pc) / 3

    # Resistance
    d["R1"] = 2 * d["PP"] - pl
    d["R2"] = d["PP"] + (ph - pl)
    d["R3"] = ph + 2 * (d["PP"] - pl)

    # Support
    d["S1"] = 2 * d["PP"] - ph
    d["S2"] = d["PP"] - (ph - pl)
    d["S3"] = pl - 2 * (ph - d["PP"])

    return d


def merge_daily_pivots_to_intraday(
    intra: pd.DataFrame, daily: pd.DataFrame
) -> pd.DataFrame:
    """
    intra: 분봉 DataFrame(index=datetime), daily: 일봉 DataFrame(index=datetime)
    일봉 Pivot 계산 후, intra에 merge & ffill
    """
    # 1) 일봉 Pivot 계산
    piv = add_pivot_points(daily)
    piv = piv[["PP", "R1", "R2", "R3", "S1", "S2", "S3"]].copy()

    # Convert index to datetime if it's not already
    if not isinstance(piv.index, pd.DatetimeIndex):
        piv.index = pd.to_datetime(piv.index)

    piv["date"] = piv.index.date

    # 2) 분봉에 date 컬럼 추가
    intra = intra.copy()
    # Convert index to datetime if it's not already
    if not isinstance(intra.index, pd.DatetimeIndex):
        intra.index = pd.to_datetime(intra.index)
    intra["date"] = intra.index.date

    # 3) merge & 전일 Pivot forward-fill
    merged = intra.merge(piv, on="date", how="left")
    merged.drop(columns="date", inplace=True)
    return merged.ffill()


def add_indis(df: pd.DataFrame, c: IndiCfg) -> pd.DataFrame:
    """OHLCV DataFrame에 권장 지표·衍생 컬럼을 추가해 반환."""
    d = df.copy()

    # === 기본 추세 ===
    d["ema_fast"] = ta.ema(d["close"], length=c.ema_fast)
    d["ema_slow"] = ta.ema(d["close"], length=c.ema_slow)
    d["ema_minor"] = ta.ema(d["close"], length=c.ema_minor)

    # === 모멘텀 ===
    d["rsi"] = ta.rsi(d["close"], length=c.rsi_len)

    # stoch 지표 - 동적 컬럼명 사용
    stoch = ta.stoch(d["high"], d["low"], d["close"], k=c.stoch_len)
    stoch_k_col = f"STOCHk_{c.stoch_len}_3_3"
    stoch_d_col = f"STOCHd_{c.stoch_len}_3_3"
    if (
        stoch is not None
        and stoch_k_col in stoch.columns
        and stoch_d_col in stoch.columns
    ):
        d = pd.concat(
            [
                d,
                stoch.rename(columns={stoch_k_col: "stoch_k", stoch_d_col: "stoch_d"}),
            ],
            axis=1,
        )

    # macd 지표 - 동적 컬럼명 사용
    macd = ta.macd(d["close"], fast=c.macd_fast, slow=c.macd_slow, signal=c.macd_signal)
    macd_col = f"MACD_{c.macd_fast}_{c.macd_slow}_{c.macd_signal}"
    macd_signal_col = f"MACDs_{c.macd_fast}_{c.macd_slow}_{c.macd_signal}"
    if (
        macd is not None
        and macd_col in macd.columns
        and macd_signal_col in macd.columns
    ):
        d = pd.concat(
            [
                d,
                macd.rename(columns={macd_col: "macd", macd_signal_col: "macd_signal"}),
            ],
            axis=1,
        )

    d["roc"] = ta.roc(d["close"], length=c.roc_len)

    # === 변동성 ===
    d["atr"] = ta.atr(d["high"], d["low"], d["close"], length=c.atr_len)
    d["atr_percent"] = (d["atr"] / d["close"]) * 100
    d["natr"] = ta.natr(d["high"], d["low"], d["close"], length=c.atr_len)

    # === 추세 강도 ===
    adx_result = ta.adx(d["high"], d["low"], d["close"], length=c.adx_len)
    adx_col = f"ADX_{c.adx_len}"
    if adx_result is not None and adx_col in adx_result.columns:
        d["adx"] = adx_result[adx_col]

    d["lrs"] = ta.linreg(d["ema_minor"], length=c.lrs_len)  # 회귀 기울기

    # === 볼린저밴드·돈채널 ===
    bb = ta.bbands(d["close"], length=c.bb_len, std=c.bb_std)
    don = ta.donchian(d["high"], d["low"], length=c.don_len)
    if don is not None:
        don = don.rename(
            columns=lambda x: x.replace("DCL", "DONCH_L").replace("DCU", "DONCH_U")
        )
        d = pd.concat([d, bb, don], axis=1)
    else:
        d = pd.concat([d, bb], axis=1)

    # === 가격·프라이스 액션 특성 ===
    d["hlc3"] = (d["high"] + d["low"] + d["close"]) / 3
    d["oc2"] = (d["open"] + d["close"]) / 2
    d["candle_body"] = (d["close"] - d["open"]).abs()
    d["upper_wick"] = d["high"] - d[["open", "close"]].max(axis=1)
    d["lower_wick"] = d[["open", "close"]].min(axis=1) - d["low"]

    # ===衍生 기울기·증감률 (直近 1봉 대비) ===
    d["ema_fast_slope"] = d["ema_fast"].pct_change() * 100
    d["rsi_change"] = d["rsi"].diff()
    d["atr_slope"] = d["atr"].pct_change() * 100

    # === VWAP ===
    if "volume" in d.columns:
        d["vwap"] = (d["close"] * d["volume"]).cumsum() / d["volume"].cumsum()

    # === Heikin-Ashi & Ichimoku (선택) ===
    ha = ta.ha(d["open"], d["high"], d["low"], d["close"])
    d = pd.concat([d, ha], axis=1)

    # ichimoku는 여러 dataframe을 튜플로 반환
    ichi_result = ta.ichimoku(d["high"], d["low"], d["close"])
    if (
        isinstance(ichi_result, tuple)
        and len(ichi_result) > 0
        and ichi_result[0] is not None
    ):
        d = pd.concat([d, ichi_result[0]], axis=1)  # 첫 번째 dataframe만 사용

    return d.dropna().reset_index(drop=True)


def trend_side(row) -> Literal["LONG", "SHORT"]:
    return "LONG" if row["ema_fast"] > row["ema_slow"] else "SHORT"


def minor_state(df_big, df_small) -> Literal["LONG", "SHORT"]:
    if (
        len(df_big) == 0
        or len(df_small) == 0
        or "lrs" not in df_big.columns
        or "lrs" not in df_small.columns
    ):
        return "SHORT"  # 기본값 반환

    up_big = df_big["lrs"].iloc[-1] > 0
    up_small = df_small["lrs"].iloc[-1] > 0
    return "LONG" if up_big and up_small else "SHORT"


# ─────────────────────────────────────────────
# 4.  트렌드·신호 함수


def signal_logic(
    dM1: pd.DataFrame,
    dM2: pd.DataFrame,
    dB: pd.DataFrame,
    dS: pd.DataFrame,
    cfg: ResumptionConfiguration,
) -> SignalResult:
    result = SignalResult(
        major_pass=False,
        ichimoku_pass=False,
        resumption_pass=False,
        macd_pass=False,
        rsi_pass=False,
        price_pass=False,
        volume_pass=False,
        final_side="NONE",
    )

    # ① Major filter
    side1 = trend_side(dM1.iloc[-1])
    side2 = trend_side(dM2.iloc[-1])
    adx1 = dM1["adx"].iloc[-1]  # ← Series.iloc 로 스칼라 추출
    adx2 = dM2["adx"].iloc[-1]
    bbw = (dM2["BBU_20_2.0"].iloc[-1] - dM2["BBL_20_2.0"].iloc[-1]) / dM2[
        "ema_slow"
    ].iloc[-1]
    adx_thresh = 25 if bbw > 1.2 else 20

    if not (side1 == side2 and min(adx1, adx2) >= adx_thresh):
        return result
    result.major_pass = True
    major = side1

    # ② Ichimoku filter
    ich = ta.ichimoku(dM2["high"], dM2["low"], dM2["close"])
    if ich is None:
        return result

    # Access the first element of the tuple returned by ichimoku
    ich_df = ich[0]

    if ich_df is None:
        return result

    spanA = ich_df["ISA_9"].iloc[-1]
    tenk = ich_df["ITS_9"].iloc[-1]
    kijun = ich_df["IKS_26"].iloc[-1]

    if not (dM2["close"].iloc[-1] > spanA and tenk > kijun):
        return result

    result.ichimoku_pass = True

    # ③ Resumption filter
    prev_minor = minor_state(dB.iloc[:-1], dS.iloc[:-1])
    curr_minor = minor_state(dB, dS)
    if not (prev_minor != major and curr_minor == major):
        return result
    result.resumption_pass = True

    # ④ MACD histogram filter
    macd = ta.macd(dS["close"])
    if macd is None:
        return result
    hist = macd["MACDh_12_26_9"].iloc[-1]
    if not ((major == "LONG" and hist > 0) or (major == "SHORT" and hist < 0)):
        return result
    result.macd_pass = True

    # ⑤ RSI centerline filter
    rsi = dS["rsi"].iloc[-1]
    if not ((major == "LONG" and rsi <= 50) or (major == "SHORT" and rsi >= 50)):
        return result
    result.rsi_pass = True

    # ⑥ Price filter (Donchian + VWAP)
    close = dS["close"].iloc[-1]
    vwap = dS["vwap"].iloc[-1]
    don_low = dS[f"DONCH_L_{cfg.indi.don_len}"].iloc[-1]
    don_high = dS[f"DONCH_U_{cfg.indi.don_len}"].iloc[-1]
    price_ok = (major == "LONG" and close < don_low and close < vwap) or (
        major == "SHORT" and close > don_high and close > vwap
    )
    if not price_ok:
        return result
    result.price_pass = True

    # ⑦ Volume filter
    vol = dS["volume"].iloc[-1]
    vol_avg = dS["volume"].tail(20).mean()
    if not (vol >= vol_avg * cfg.risk.vol_filter):
        return result
    result.volume_pass = True

    # 모두 통과!
    result.final_side = major
    return result


def sl_tp(
    price: float, atr: float, side: str, r: RiskConfiguration
) -> tuple[float, float]:
    if side == "LONG":
        return round(price - atr * r.atr_sl_mult, 2), round(
            price + atr * r.atr_tp_mult, 2
        )
    return round(price + atr * r.atr_sl_mult, 2), round(price - atr * r.atr_tp_mult, 2)


# ─────────────────────────────────────────────
# 5.  LLM 관련 함수 (1 기능 = 1 함수)
# ─────────────────────────────────────────────
def build_tf_snapshot(
    df: pd.DataFrame,
    n: int,
    prefix: str,
    cfg: ResumptionConfiguration,
) -> Dict[str, list]:
    """
    df: 지표가 붙은 DataFrame
    n: 최근 n 봉
    prefix: ex. "5m", "15m", "1h", "4h"
    """
    # CORE_COLS 는 add_indis 로 생성된 열 중, 스냅샷에 포함할 것들만
    CORE_COLS = [
        # OHLCV
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        # 파생 가격
        "hlc3",
        "oc2",
        # 추세
        "ema_fast",
        "ema_slow",
        "ema_minor",
        "ema_fast_slope",
        # 모멘텀
        "rsi",
        "rsi_change",
        "stoch_k",
        "stoch_d",
        "macd",
        "macd_signal",
        "roc",
        # 변동성
        "atr",
        "atr_percent",
        "natr",
        "atr_slope",
        # 추세 강도
        "adx",
        "lrs",
        # 볼밴·돈채널
        f"BBL_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
        f"BBU_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
        f"DONCH_L_{cfg.indi.don_len}",
        f"DONCH_U_{cfg.indi.don_len}",
        # 피봇 예시
        "P",
        "S1",
        "R1",
        "S2",
        "R2",
        # 프라이스 액션
        "candle_body",
        "upper_wick",
        "lower_wick",
        # VWAP
        "vwap",
        # HA / Ichimoku
        "HA_open",
        "HA_close",
        "ISA_9",
        "ISB_26",
        "ITS_9",
        "IKS_26",
        "ICS_26",
    ]
    snap: Dict[str, list] = {}
    for col in CORE_COLS:
        if col in df.columns:
            snap[f"{prefix}_{col}"] = df[col].iloc[-n:].round(4).tolist()
    return snap


def build_snapshot(
    # dS: pd.DataFrame,
    # dB: pd.DataFrame,
    # dM1: pd.DataFrame,
    # dM2: pd.DataFrame,
    # n_small: int,
    # n_big: int,
    # tfmS: str,
    # tfmB: str,
    # tfM1: str,
    # tfM2: str,
    timeframes: List[TimeFrameConfiguration],
    cfg: ResumptionConfiguration,
) -> dict:
    """
    dS, dB, dM1, dM2: 각각 가장 작은 minor → 큰 major 순으로
    tfmS, tfmB, tfM1, tfM2: "5m", "15m", "1h", "4h" 등
    n_small: minor 용
    n_big:   major 용
    """
    snap: dict = {}

    for timeframe in timeframes:
        if timeframe.dataframe is None:
            continue

        snap.update(
            build_tf_snapshot(
                timeframe.dataframe, timeframe.snapshot_length, timeframe.timeframe, cfg
            )
        )

    return snap


def llm_confirms(side: str, llm_resp: dict) -> bool:
    return llm_resp.get("decision") == side and llm_resp.get("confidence", 0) >= 0.5


def build_explanation(
    dM1: pd.DataFrame,
    dM2: pd.DataFrame,
    dB: pd.DataFrame,
    dS: pd.DataFrame,
    major: str,
    cfg: ResumptionConfiguration,
) -> Dict[str, str]:
    """
    각 단계(major trend, minor state, price/volume 필터)에
    대한 간단한 텍스트 설명을 반환합니다.
    """
    expl: Dict[str, str] = {}

    # A. Major trend 해석
    row4h = dM2.iloc[-1]
    row1h = dM1.iloc[-1]
    expl["major_trend"] = (
        f"Major={major}: 4h EMA50/200={row4h['ema_fast']:.2f}/{row4h['ema_slow']:.2f}, "
        f"1h EMA50/200={row1h['ema_fast']:.2f}/{row1h['ema_slow']:.2f}, "
        f"ADX(4h/1h)={row4h['adx']:.2f}/{row1h['adx']:.2f}."
    )

    # B. Minor (눌림→복귀) 해석
    prev_minor = minor_state(dB.iloc[:-1], dS.iloc[:-1])
    curr_minor = minor_state(dB, dS)
    expl["minor_resumption"] = (
        f"Previous minor_state={prev_minor}, current minor_state={curr_minor} "
        f"(기울기 LRS 기준)."
    )

    # C. Price 필터 해석
    last = dS.iloc[-1]
    don_low = last[f"DONCH_L_{cfg.indi.don_len}"]
    don_high = last[f"DONCH_U_{cfg.indi.don_len}"]
    if major == "LONG":
        cond = last["close"] < don_low and last["close"] < last["vwap"]
        desc = f"close({last['close']:.4f}) < DonchianLow({don_low:.4f}) and VWAP({last['vwap']:.4f})"
    else:
        cond = last["close"] > don_high and last["close"] > last["vwap"]
        desc = f"close({last['close']:.4f}) > DonchianHigh({don_high:.4f}) and VWAP({last['vwap']:.4f})"
    expl["price_filter"] = f"Price filter { '통과' if cond else '미통과' }: {desc}."

    # D. Volume 필터 해석
    avg_vol = dS["volume"].tail(20).mean()
    expl["volume_filter"] = (
        f"Last volume={last['volume']:.2f}, "
        f"20-bar avg*{cfg.risk.vol_filter:.1f}={avg_vol*cfg.risk.vol_filter:.2f}: "
        f"{'통과' if last['volume'] > avg_vol*cfg.risk.vol_filter else '미통과'}."
    )

    return expl
