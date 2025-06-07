# discord_service.py
from typing import Dict, List
import requests

from myapi.utils.config import Settings


class DiscordService:
    def __init__(self, settings: Settings):
        self.webhook_url = settings.DISCORD_WEBHOOK_URL
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

    def send_message(self, content: str, embeds: List[Dict] | None = []):
        """
        디스코드 웹훅을 통해 메시지 전송
        """
        # payload = {"embeds": None, "content": ""}

        payload = dict()

        if content:  # (옵션) ping · 간단 텍스트
            payload["content"] = content[:2000]

        if embeds:  # (옵션) embed · 최대 10개
            payload["embeds"] = embeds

        if not content and not embeds:
            raise ValueError(
                "전송할 내용이 없습니다. content 또는 embeds를 제공해야 합니다."
            )

        headers = {"Content-Type": "application/json"}
        response = requests.post(self.webhook_url, json=payload, headers=headers)
        response.raise_for_status()  # 실패 시 예외 발생

        if not (response.status_code > 199 and response.status_code < 300):
            raise Exception(
                f"디스코드 메시지 전송 실패: {response.status_code} - {response.text}"
            )

        return {
            "status": "success",
            "message": "디스코드 메시지가 성공적으로 전송되었습니다.",
            "response_code": response.status_code,
        }  # 성공 시 응답 반환
