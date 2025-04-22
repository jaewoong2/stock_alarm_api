"""
하위 TF 역방향 → 다시 대세 방향 복귀” 구조는 검증된 트렌드‑팔로 + 눌림 매수 기법으로
① 다중 TF 추세 강도(ADX) 필터, ② 복귀 신호의 다중 확인(MACD·BB·RSI), ③ ATR‑기반 동적 SL/TP
과도한 역추세 스캘핑을 억제하면서 추세 재개 구간만

"""

from typing import Dict, Literal
import pandas as pd
import pandas_ta as ta

from myapi.domain.futures.futures_schema import BotCfg, IndiCfg, RiskCfg


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
                f"DCL_{c.don_len}": f"DONCH_L_{c.don_len}",
                f"DCU_{c.don_len}": f"DONCH_U_{c.don_len}",
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
    d_major1, d_major2, d_minor_big, d_minor_small, cfg: BotCfg
) -> Literal["LONG", "SHORT", "NONE"]:
    # 데이터프레임이 비어 있는지 확인
    if (
        len(d_major1) == 0
        or len(d_major2) == 0
        or len(d_minor_big) == 0
        or len(d_minor_small) == 0
    ):
        return "NONE"

    # 1) 대세
    side_major1 = trend_side(d_major1.iloc[-1])
    side_major2 = trend_side(d_major2.iloc[-1])
    if (
        side_major1 != side_major2
        or min(d_major1.iloc[-1]["adx"], d_major2.iloc[-1]["adx"]) < 20
    ):
        return "NONE"
    major = side_major1

    # 이전 데이터가 충분한지 확인
    if len(d_minor_big) <= 1 or len(d_minor_small) <= 1:
        return "NONE"

    # 2) 직전 minor 역방향 → 현재 minor 대세
    prev_minor = minor_state(d_minor_big.iloc[:-1], d_minor_small.iloc[:-1])
    curr_minor = minor_state(d_minor_big, d_minor_small)
    if prev_minor != major and curr_minor == major:
        # 3) 가격이 Donchian 극단+VWAP 조건
        row = d_minor_small.iloc[-1]
        donch_col_low = f"DONCH_L_{cfg.indi.don_len}"
        donch_col_high = f"DONCH_U_{cfg.indi.don_len}"

        # 필요한 열이 존재하는지 확인
        if donch_col_low not in row or donch_col_high not in row:
            return "NONE"

        if major == "LONG":
            cond_price = (
                row["close"] < row[donch_col_low] and row["close"] < row["vwap"]
            )
        else:
            cond_price = (
                row["close"] > row[donch_col_high] and row["close"] > row["vwap"]
            )
        if (
            cond_price
            and row["volume"]
            > d_minor_small["volume"].tail(20).mean() * cfg.risk.vol_filter
        ):
            return major
    return "NONE"


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
    # don_low = last[f"DONCH_L_{cfg.indi.don_len}"]
    # don_high = last[f"DONCH_U_{cfg.indi.don_len}"]
    # if major == "LONG":
    #     cond = last["close"] < don_low and last["close"] < last["vwap"]
    #     desc = f"close({last['close']:.4f}) < DonchianLow({don_low:.4f}) and VWAP({last['vwap']:.4f})"
    # else:
    #     cond = last["close"] > don_high and last["close"] > last["vwap"]
    #     desc = f"close({last['close']:.4f}) > DonchianHigh({don_high:.4f}) and VWAP({last['vwap']:.4f})"
    # expl["price_filter"] = f"Price filter { '통과' if cond else '미통과' }: {desc}."

    # D. Volume 필터 해석
    avg_vol = dS["volume"].tail(20).mean()
    expl["volume_filter"] = (
        f"Last volume={last['volume']:.2f}, "
        f"20-bar avg*{cfg.risk.vol_filter:.1f}={avg_vol*cfg.risk.vol_filter:.2f}: "
        f"{'통과' if last['volume'] > avg_vol*cfg.risk.vol_filter else '미통과'}."
    )

    return expl
