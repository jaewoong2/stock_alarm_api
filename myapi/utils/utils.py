import datetime
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


def format_signal_response(response: SignalPromptResponse, model: str) -> str:
    """
    SignalPromptResponse 객체를 가독성 있는 마크다운 문자열로 변환합니다.

    Args:
        response: 분석 결과가 담긴 SignalPromptResponse 객체

    Returns:
        마크다운 형식의 분석 요약 문자열
    """

    # 이모지 맵
    emoji_map = {
        "ticker": "🏷️",
        "recommendation": "🚦",
        "reasoning": "📝",
        "entry_price": "💰",
        "close_price": " 😎",
        "stop_loss_price": "🛡️",
        "take_profit_price": "🎯",
        "probability_of_rising_up": "📈",
        "probability_of_rising_up_percentage": "📊",
        "think_steps": "💭",
    }

    lines = []

    try:
        # 헤더 (티커와 추천)

        lines.append(
            f"## [{model} 모델 사용] {emoji_map['ticker']} {response.ticker} - {emoji_map['recommendation']} {response.recommendation}"
        )
        lines.append("")

        price_lines = []

        if response.entry_price is not None:
            price_lines.append(
                f"{emoji_map['entry_price']} **진입가**: {response.entry_price}"
            )

        if response.close_price is not None:
            price_lines.append(
                f"{emoji_map['close_price']} **종가**: {response.close_price}"
            )

        if response.stop_loss_price is not None and response.entry_price is not None:
            try:
                sl_percentage = (
                    (float(response.stop_loss_price) - float(response.entry_price))
                    / float(response.entry_price)
                ) * 100
                price_lines.append(
                    f"{emoji_map['stop_loss_price']} **손절가**: {response.stop_loss_price} ({sl_percentage:.2f}%)"
                )
            except (ValueError, TypeError):
                price_lines.append(
                    f"{emoji_map['stop_loss_price']} **손절가**: {response.stop_loss_price}"
                )
        elif response.stop_loss_price is not None:
            price_lines.append(
                f"{emoji_map['stop_loss_price']} **손절가**: {response.stop_loss_price}"
            )

        if response.take_profit_price is not None and response.entry_price is not None:
            # 목표가 퍼센테이지 계산 (진입가 대비)
            try:
                tp_percentage = (
                    (float(response.take_profit_price) - float(response.entry_price))
                    / float(response.entry_price)
                ) * 100
                price_lines.append(
                    f"{emoji_map['take_profit_price']} **목표가**: {response.take_profit_price} ({tp_percentage:.2f}%)"
                )
            except (ValueError, TypeError):
                price_lines.append(
                    f"{emoji_map['take_profit_price']} **목표가**: {response.take_profit_price}"
                )
        elif response.take_profit_price is not None:
            price_lines.append(
                f"{emoji_map['take_profit_price']} **목표가**: {response.take_profit_price}"
            )

        if response.probability_of_rising_up is not None:
            price_lines.append(
                f"{emoji_map['probability_of_rising_up']} **상승 확률**: {response.probability_of_rising_up}"
            )

        if response.probability_of_rising_up_percentage is not None:
            price_lines.append(
                f"{emoji_map['probability_of_rising_up_percentage']} **상승 확률(%)**: {response.probability_of_rising_up_percentage:.2f}%"
            )

        if price_lines or len(price_lines) > 0:
            lines.append("### 가격 수준")
            lines.extend(price_lines)
            lines.append("")

        # 분석 이유
        lines.append("### 분석 근거")
        lines.append(f"{emoji_map['reasoning']} {response.reasoning}")

        lines.append("")
        # 생각 과정
        if response.think_steps:
            lines.append("### 생각 과정")
            lines.append(f"{emoji_map['think_steps']} {response.think_steps}")
            lines.append("")

        if response.good_things:
            lines.append("### 긍정적인 요소")
            lines.append(response.good_things)
            lines.append("")

        if response.bad_things:
            lines.append("### 부정적인 요소")
            lines.append(response.bad_things)
            lines.append("")

    except Exception as e:
        lines.append("🚨 **오류 발생:**")
        lines.append(f"```\n{str(e)}\n```")
        print(f"오류 발생: {str(e)}")

    # 문자열로 반환
    return "\n".join(lines)


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
        "RS_SHORT",
        "RS_MID",
    ]

    # 교집합만 선택해 예상치 못한 결측 컬럼 오류 방지
    cols_to_use = [c for c in keep_cols if c in df.columns]

    return df.loc[:, cols_to_use].round(3).tail(rows).to_csv()


def format_signal_embed(response: SignalPromptResponse, model: str):
    """
    SignalPromptResponse → Discord embed JSON.
    반환값은 embeds 배열 한 개(길어질 경우 여러 개)이다.
    """
    emoji = {
        "ticker": "🏷️",
        "recommendation": "🚦",
        "reasoning": "📝",
        "entry_price": "💰",
        "stop_loss_price": "🛡️",
        "take_profit_price": "🎯",
        "prob_up": "📈",
        "prob_up_pct": "📊",
        "think": "💭",
        "senarios": "📜",
    }

    # ── 1. 헤더(타이틀) ───────────────────────────────
    title = f"[{model} 모델] {emoji['ticker']} {response.ticker}"
    if response.recommendation:
        title += f"  |  {emoji['recommendation']} {response.recommendation}"

    # ── 2. 설명(Description) ─────────────────────────
    desc_lines = []
    if response.reasoning:
        desc_lines.append(f"{emoji['reasoning']} **분석 근거**\n{response.reasoning}")

    if response.think_steps:
        desc_lines.append(f"{emoji['think']} **생각 과정**\n{response.think_steps}")

    description = "\n\n".join(desc_lines)[:2048]  # 안전 차단

    # ── 3. 필드(가격 정보 등) ────────────────────────
    fields = []

    def add_field(name, value, inline=False):
        if value is None or value == "":
            return
        fields.append(
            {
                "name": name[:256],
                "value": str(value)[:1024],
                "inline": inline,
            }
        )

    # 가격 필드
    add_field(f"{emoji['entry_price']} 진입가", response.entry_price, inline=True)
    if response.stop_loss_price:
        if response.entry_price:
            try:
                sl_pct = (
                    (float(response.stop_loss_price) - float(response.entry_price))
                    / float(response.entry_price)
                    * 100
                )
                value = f"{response.stop_loss_price} ({sl_pct:.2f}%)"
            except Exception:
                value = response.stop_loss_price
        else:
            value = response.stop_loss_price
        add_field(f"{emoji['stop_loss_price']} 손절가", value, inline=True)

    if response.take_profit_price:
        if response.entry_price:
            try:
                tp_pct = (
                    (float(response.take_profit_price) - float(response.entry_price))
                    / float(response.entry_price)
                    * 100
                )
                value = f"{response.take_profit_price} ({tp_pct:.2f}%)"
            except Exception:
                value = response.take_profit_price
        else:
            value = response.take_profit_price
        add_field(f"{emoji['take_profit_price']} 목표가", value, inline=True)

    add_field(
        f"{emoji['prob_up']} 상승 확률", response.probability_of_rising_up, inline=True
    )
    if response.probability_of_rising_up_percentage is not None:
        add_field(
            f"{emoji['prob_up_pct']} 상승 확률(%)",
            f"{response.probability_of_rising_up_percentage:.2f}%",
            inline=True,
        )

    # 긍/부정 요소(길 수 있어서 개별 필드로)
    if response.good_things:
        add_field("👍 긍정 요소", response.good_things, inline=False)
    if response.bad_things:
        add_field("👎 부정 요소", response.bad_things, inline=False)

    if response.senarios:
        add_field(f"{emoji['senarios']} 시나리오", response.senarios, inline=False)

    # ── 4. embed 객체 완성 ───────────────────────────
    embed = {
        "title": title[:256],
        "description": description,
        "fields": fields,
        # 선택 사항: 색상·타임스탬프·author·footer 등
        "color": (
            0x2ECC71 if "BUY" in (response.recommendation or "").upper() else 0xE74C3C
        ),
        # "timestamp": datetime.datetime.now().isoformat() + "Z",  # ISO 8601 형식
    }
    return [embed]


from datetime import datetime, timedelta


def get_prev_date(date=None):
    """
    주어진 날짜의 이전 영업일(워크데이)을 반환합니다.
    월요일이면 금요일, 나머지 평일이면 전날을 반환합니다.

    Args:
        date: datetime 객체 또는 None (None이면 오늘 날짜 사용)

    Returns:
        datetime: 이전 영업일
    """
    if date is None:
        date = datetime.now()

    # 요일 확인 (0=월요일, 1=화요일, ..., 6=일요일)
    weekday = date.weekday()

    if weekday == 0:  # 월요일
        # 3일 전 (금요일)
        prev_date = date - timedelta(days=3)
    elif weekday == 6:  # 일요일
        # 2일 전 (금요일)
        prev_date = date - timedelta(days=2)
    elif weekday == 5:  # 토요일
        # 1일 전 (금요일)
        prev_date = date - timedelta(days=1)
    else:  # 화요일~금요일
        # 1일 전
        prev_date = date - timedelta(days=1)

    return prev_date
