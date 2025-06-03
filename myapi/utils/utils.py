from pandas import DataFrame
from myapi.domain.signal.signal_schema import SignalPromptResponse


def format_trade_summary(data: dict):
    # 이모지 맵
    emoji_map = {
        "detail_summary": "📝",
        "action": "🚦",
        "order": "📦",
        "symbol": "💱",
        "quantity": "🔢",
        "price": "💰",
        "tp_price": "🎯",
        "sl_price": "🛡️",
        "leverage": "⚙️",
    }

    lines = []

    try:
        if not isinstance(data, dict):
            raise ValueError("입력 데이터는 딕셔너리여야 합니다.")

        # 상세 요약
        lines.append(f"{emoji_map['detail_summary']} **상세 요약:**")
        detail = data.get("detaild_summary", "없음")
        if not isinstance(detail, str):
            detail = str(detail)
        lines.append(detail)
        lines.append("")

        # 각 주문 정보
        for order_key in ["first_order", "second_order", "third_order"]:
            order = data.get(order_key)

            if not isinstance(order, dict):
                lines.append(
                    f"{emoji_map['order']} **{order_key.replace('_', ' ').title()}**: 데이터 없음 또는 형식 오류"
                )
                lines.append("")
                continue  # 다음으로

            lines.append(
                f"{emoji_map['order']} **{order_key.replace('_', ' ').title()}**"
            )

            for field_key in [
                "action",
                "symbol",
                "quantity",
                "price",
                "tp_price",
                "sl_price",
                "leverage",
            ]:
                value = order.get(field_key, "없음")
                # 타입 강제 변환 (문자열로)
                try:
                    value_str = str(value)
                except Exception:
                    value_str = "변환 오류"

                lines.append(f"{emoji_map.get(field_key, '')} {field_key}: {value_str}")

            lines.append("")  # 줄바꿈

    except Exception as e:
        lines.append("🚨 오류 발생:")
        lines.append(str(e))

    # 문자열로 반환
    return "\n".join(lines)


def format_signal_response(
    response: SignalPromptResponse,
    model: str,
    *,
    show_think_steps: bool = True,
) -> str:
    """Convert a :class:`SignalPromptResponse` into Discord‑friendly Markdown.

    Parameters
    ----------
    response : SignalPromptResponse
        Parsed signal data.
    model : str
        Name of the ML / quant model that produced the signal (e.g. "GOOGLE").
    show_think_steps : bool, default ``False``
        Whether to append the full `think_steps` chain‑of‑thought (if present).

    Returns
    -------
    str
        Richly formatted Markdown block ready for Discord.
    """

    # ---------------------------
    # Emoji palette (feel free to tweak!)
    # ---------------------------
    E = {
        "header": "#️⃣",  # header bullet
        "ticker": "🏷️",
        "reco": "🚦",
        "entry": "💰",
        "stop": "🛡️",
        "target": "🎯",
        "prob": "📈",
        "reason": "📝",
        "scenario": "🔮",
        "think": "🤔",
    }

    md: list[str] = []  # incremental build

    # Header ---------------------------------------------------------------
    md.append(f"### {E['header']}  **{model} 모델 사용**  {E['header']}")
    # Ticker + Recommendation tag -----------------------------------------
    md.append(
        f"### {E['ticker']} **{response.ticker.upper()}**  ─  {E['reco']} **{response.recommendation}**"
    )
    md.append("")

    # Trade levels ---------------------------------------------------------
    if response.recommendation != "HOLD":
        price_lines: list[str] = []

        if response.entry_price is not None:
            price_lines.append(f"{E['entry']} **진입가**: `{response.entry_price}`")

        if response.stop_loss_price is not None:
            perc = (
                (
                    (response.stop_loss_price - response.entry_price)
                    / response.entry_price
                    * 100
                )
                if response.entry_price
                else None
            )
            txt = f" ({perc:+.2f}%)" if perc is not None else ""
            price_lines.append(
                f"{E['stop']} **손절가**: `{response.stop_loss_price}`{txt}"
            )

        if response.take_profit_price is not None:
            perc = (
                (
                    (response.take_profit_price - response.entry_price)
                    / response.entry_price
                    * 100
                )
                if response.entry_price
                else None
            )
            txt = f" ({perc:+.2f}%)" if perc is not None else ""
            price_lines.append(
                f"{E['target']} **목표가**: `{response.take_profit_price}`{txt}"
            )

        # probability block – prefer percentage if supplied, fallback to string
        if response.probability_of_rising_up_percentage is not None:
            prob_str = f"{response.probability_of_rising_up_percentage:.0f}%"
        else:
            prob_str = response.probability_of_rising_up or "N/A"
        price_lines.append(f"{E['prob']} **상승 확률**: {prob_str}")

        # Collapse into Markdown subsection
        if price_lines:
            md.append("#### 📊 가격 수준")
            md.extend(price_lines)
            md.append("")

    # Core reasoning -------------------------------------------------------
    md.append("#### 분석 근거")
    md.append(f"{E['reason']} {response.reasoning}")

    # Optional scenario analysis
    if response.senarios:
        md.append("")
        md.append("#### 시나리오 분석")
        md.append(f"{E['scenario']} {response.senarios}")

    # Optional chain‑of‑thought (hidden by default)
    if show_think_steps and response.think_steps:
        md.append("")
        md.append("<details><summary>추가적인 Think Steps 보기</summary>\n\n")
        md.append(f"{E['think']} {response.think_steps}")
        md.append("\n\n</details>")

    # Join everything together
    return "\n".join(md)


def export_slim_tail_csv(df: DataFrame, rows: int = 260):
    """
    마지막 `rows`행만 가져와 필요한 컬럼만 남기고
    소수점 3자리로 반올림해 CSV로 저장한다.

    Parameters
    ----------
    df   : pandas.DataFrame
    path : str – 저장할 파일 경로
    rows : int – 뒤에서부터 가져올 행 수 (기본 260)
    """
    keep_cols = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "SMA5",
        "SMA20",
        "SMA50",
        "SMA150",
        "SMA200",
        "ATR14",
        "ATR_PCT",
        "RSI14",
        "RSI5",
        "MACD_12_26_9",
        "MACDh_12_26_9",
        "MACDs_12_26_9",
        "VOL20",
        "BBP_20_2.0",
        "BB_WIDTH",
        "ADX_14",
        "DMP_14",
        "DMN_14",
        "ROC1",
        "ROC5",
        "VWAP",
        "GAP_PCT",
    ]

    # 교집합만 선택해 예상치 못한 결측 컬럼 오류 방지
    cols_to_use = [c for c in keep_cols if c in df.columns]

    return df.loc[:, cols_to_use].round(3).tail(rows).to_csv()
