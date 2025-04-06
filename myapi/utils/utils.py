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
