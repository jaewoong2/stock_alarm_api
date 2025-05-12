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


def format_signal_response(response: SignalPromptResponse) -> str:
    """
    SignalPromptResponse 객체를 가독성 있는 마크다운 문자열로 변환합니다.

    Args:
        response: 분석 결과가 담긴 SignalPromptResponse 객체

    Returns:
        마크다운 형식의 분석 요약 문자열
    """

    probability_of_rising_up = response.probability_of_rising_up
    # 이모지 맵
    emoji_map = {
        "ticker": "🏷️",
        "recommendation": "🚦",
        "reasoning": "📝",
        "entry_price": "💰",
        "stop_loss_price": "🛡️",
        "take_profit_price": "🎯",
        "probability_of_rising_up": "📈",
    }

    lines = []

    try:
        # 헤더 (티커와 추천)
        lines.append(
            f"## {emoji_map['ticker']} {response.ticker} - {emoji_map['recommendation']} {response.recommendation}"
        )
        lines.append("")

        # 가격 정보 (추천이 HOLD가 아닐 경우에만)
        if response.recommendation != "HOLD":
            price_lines = []

            if response.entry_price is not None:
                price_lines.append(
                    f"{emoji_map['entry_price']} **진입가**: {response.entry_price}"
                )

            if (
                response.stop_loss_price is not None
                and response.entry_price is not None
            ):
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

            if (
                response.take_profit_price is not None
                and response.entry_price is not None
            ):
                # 목표가 퍼센테이지 계산 (진입가 대비)
                try:
                    tp_percentage = (
                        (
                            float(response.take_profit_price)
                            - float(response.entry_price)
                        )
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

            if probability_of_rising_up:
                price_lines.append(
                    f"{emoji_map['probability_of_rising_up']} **상승 확률**: {probability_of_rising_up}"
                )

            if price_lines:
                lines.append("### 가격 수준")
                lines.extend(price_lines)
                lines.append("")

        # 분석 이유
        lines.append("### 분석 근거")
        lines.append(f"{emoji_map['reasoning']} {response.reasoning}")

    except Exception as e:
        lines.append("🚨 **오류 발생:**")
        lines.append(f"```\n{str(e)}\n```")

    # 문자열로 반환
    return "\n".join(lines)
