"""
하위 TF 역방향 → 다시 대세 방향 복귀” 구조는 검증된 트렌드‑팔로 + 눌림 매수 기법으로
① 다중 TF 추세 강도(ADX) 필터, ② 복귀 신호의 다중 확인(MACD·BB·RSI), ③ ATR‑기반 동적 SL/TP
과도한 역추세 스캘핑을 억제하면서 추세 재개 구간만

"""

from typing import Dict, Literal
import pandas as pd
import pandas_ta as ta

from myapi.domain.futures.futures_schema import BotCfg, IndiCfg, RiskCfg, SignalResult


def add_indis(df: pd.DataFrame, c: IndiCfg) -> pd.DataFrame:
    d = df.copy()
    d["ema_fast"] = ta.ema(d["close"], c.ema_fast)
    d["ema_slow"] = ta.ema(d["close"], c.ema_slow)
    d["ema_minor"] = ta.ema(d["close"], c.ema_minor)
    d["rsi"] = ta.rsi(d["close"], c.rsi_len)
    d["atr"] = ta.atr(d["high"], d["low"], d["close"], c.atr_len)
    adx_result = ta.adx(d["high"], d["low"], d["close"], c.adx_len)
    if adx_result is not None:
        d["adx"] = adx_result["ADX_14"]
    else:
        d["adx"] = pd.Series([None] * len(d), index=d.index)
    bb = ta.bbands(d["close"], c.bb_len, c.bb_std)
    d = pd.concat([d, bb], axis=1)
    don = ta.donchian(d["high"], d["low"], length=c.don_len)
    # pandas_ta 기본 이름은 DCL_{len}, DCU_{len} 입니다.

    if don is not None:
        don = don.rename(
            columns={
                f"DCL_{c.don_len}_{c.don_len}": f"DONCH_L_{c.don_len}",
                f"DCU_{c.don_len}_{c.don_len}": f"DONCH_U_{c.don_len}",
            }
        )

    d = pd.concat([d, don], axis=1)

    d["lrs"] = ta.linreg(d["ema_minor"], length=c.lrs_len)
    d["vwap"] = (d["close"] * d["volume"]).cumsum() / d["volume"].cumsum()

    return d.dropna()


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
    cfg: BotCfg,
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


def sl_tp(price: float, atr: float, side: str, r: RiskCfg) -> tuple[float, float]:
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
    cfg: BotCfg,
) -> Dict[str, list]:
    """
    df: 지표가 붙은 DataFrame
    n: 최근 n 봉
    prefix: ex. "5m", "15m", "1h", "4h"
    """
    # CORE_COLS 는 add_indis 로 생성된 열 중, 스냅샷에 포함할 것들만
    CORE_COLS = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ema_fast",
        "ema_slow",
        "ema_minor",
        "rsi",
        "atr",
        "adx",
        "lrs",
        f"BBL_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
        f"BBU_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
        f"DONCH_L_{cfg.indi.don_len}",
        f"DONCH_U_{cfg.indi.don_len}",
        "vwap",
        # HA / Ichimoku 가 add_indis 에서 생성된다면
        # "ha_open",
        # "ha_close",
        # "ISA_9",
        # "ISB_26",
        # "ITS_9",
        # "IKS_26",
        # "ICS_26",
    ]
    snap: Dict[str, list] = {}
    for col in CORE_COLS:
        if col in df.columns:
            snap[f"{prefix}_{col}"] = df[col].iloc[-n:].round(4).tolist()
    return snap


def build_snapshot(
    dS: pd.DataFrame,
    dB: pd.DataFrame,
    dM1: pd.DataFrame,
    dM2: pd.DataFrame,
    n_small: int,
    n_big: int,
    tfmS: str,
    tfmB: str,
    tfM1: str,
    tfM2: str,
    cfg: BotCfg,
) -> dict:
    """
    dS, dB, dM1, dM2: 각각 가장 작은 minor → 큰 major 순으로
    tfmS, tfmB, tfM1, tfM2: "5m", "15m", "1h", "4h" 등
    n_small: minor 용
    n_big:   major 용
    """
    snap: dict = {}
    # 작은 minor (예: 5m)
    snap.update(build_tf_snapshot(dS, n_small * 3, tfmS, cfg))
    # 큰 minor (예: 15m)
    snap.update(build_tf_snapshot(dB, n_small, tfmB, cfg))
    # 작은 major (예: 1h)
    snap.update(build_tf_snapshot(dM1, n_big, tfM1, cfg))
    # 큰 major (예: 4h)
    snap.update(build_tf_snapshot(dM2, n_big * 4, tfM2, cfg))
    return snap


def llm_confirms(side: str, llm_resp: dict) -> bool:
    return llm_resp.get("decision") == side and llm_resp.get("confidence", 0) >= 0.5


def build_explanation(
    dM1: pd.DataFrame,
    dM2: pd.DataFrame,
    dB: pd.DataFrame,
    dS: pd.DataFrame,
    major: str,
    cfg: BotCfg,
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
