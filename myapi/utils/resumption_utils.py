"""
하위 TF 역방향 → 다시 대세 방향 복귀” 구조는 검증된 트렌드‑팔로 + 눌림 매수 기법으로
① 다중 TF 추세 강도(ADX) 필터, ② 복귀 신호의 다중 확인(MACD·BB·RSI), ③ ATR‑기반 동적 SL/TP
과도한 역추세 스캘핑을 억제하면서 추세 재개 구간만

"""

from typing import Literal
import pandas as pd


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


def llm_confirms(side: str, llm_resp: dict) -> bool:
    return llm_resp.get("decision") == side and llm_resp.get("confidence", 0) >= 0.5
