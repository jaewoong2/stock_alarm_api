"""
하위 TF 역방향 → 다시 대세 방향 복귀” 구조는 검증된 트렌드‑팔로 + 눌림 매수 기법으로
① 다중 TF 추세 강도(ADX) 필터, ② 복귀 신호의 다중 확인(MACD·BB·RSI), ③ ATR‑기반 동적 SL/TP
과도한 역추세 스캘핑을 억제하면서 추세 재개 구간만

"""

from typing import Dict, Literal, Union
import pandas as pd
import pandas_ta as ta

from myapi.domain.futures.futures_schema import BotCfg, IndiCfg, RiskCfg


def add_indicators(df: pd.DataFrame, c: IndiCfg) -> pd.DataFrame:
    d = df.copy()
    d["ema_fast"] = ta.ema(d["close"], c.ema_fast)
    d["ema_slow"] = ta.ema(d["close"], c.ema_slow)
    d["ema_minor"] = ta.ema(d["close"], c.ema_minor)
    d["rsi"] = ta.rsi(d["close"], c.rsi_len)
    d["atr"] = ta.atr(d["high"], d["low"], d["close"], c.atr_len)
    adx_result = ta.adx(d["high"], d["low"], d["close"], c.adx_len)
    if adx_result is not None:
        d["adx"] = adx_result["ADX_" + str(c.adx_len)]
    else:
        d["adx"] = pd.Series([None] * len(d))
    bb = ta.bbands(d["close"], c.bb_len, c.bb_std)
    return pd.concat([d, bb], axis=1).dropna()


# ─────────────────────────────────────────────
# 4.  트렌드·신호 함수
# ─────────────────────────────────────────────
def trend_row(row) -> Literal["LONG", "SHORT"]:
    return "LONG" if row["ema_fast"] > row["ema_slow"] else "SHORT"


def major_trend(
    d4h: pd.DataFrame, d1h: pd.DataFrame
) -> Literal["LONG", "SHORT", "NONE"]:
    side4, side1 = trend_row(d4h.iloc[-1]), trend_row(d1h.iloc[-1])
    if side4 == side1 and min(d4h.iloc[-1]["adx"], d1h.iloc[-1]["adx"]) > 20:
        return side4
    return "NONE"


def slope(series: pd.Series[Union[int, float]]) -> Literal["UP", "DOWN"]:
    return "UP" if series.diff().iloc[-1] > 0 else "DOWN"


def minor_state(d15: pd.DataFrame, d5: pd.DataFrame) -> Literal["LONG", "SHORT"]:
    if slope(d15["ema_minor"]) == "UP" and slope(d5["ema_minor"]) == "UP":
        return "LONG"
    return "SHORT"


def is_resumption(d15: pd.DataFrame, d5: pd.DataFrame, major: str) -> bool:
    prev = minor_state(d15.iloc[:-1], d5.iloc[:-1])
    curr = minor_state(d15, d5)
    return prev != major and curr == major


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
    df: pd.DataFrame, n: int, prefix: str, cfg: BotCfg
) -> Dict[str, list]:
    cols = [
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
        f"BBU_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
        f"BBL_{cfg.indi.bb_len}_{cfg.indi.bb_std}",
    ]
    return {f"{prefix}_{c}": df[c].iloc[-n:].round(4).tolist() for c in cols}


def build_snapshot(
    d5: pd.DataFrame,
    d15: pd.DataFrame,
    d1: pd.DataFrame,
    d4: pd.DataFrame,
    n_small: int,
    n_big: int,
    cfg: BotCfg,
) -> dict:
    s = {}
    s.update(build_tf_snapshot(d5, n_small, "5m", cfg))
    s.update(build_tf_snapshot(d15, n_small, "15m", cfg))
    s.update(build_tf_snapshot(d1, n_big, "1h", cfg))
    s.update(build_tf_snapshot(d4, n_big, "4h", cfg))
    return s


def llm_confirms(side: str, llm_resp: dict) -> bool:
    return llm_resp.get("decision") == side and llm_resp.get("confidence", 0) >= 0.5
