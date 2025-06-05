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
        payload = {"embeds": embeds, "content": ""}
        if content:  # (옵션) ping · 간단 텍스트
            payload["content"] = content[:2000]

        headers = {"Content-Type": "application/json"}
        response = requests.post(self.webhook_url, json=payload, headers=headers)
        response.raise_for_status()  # 실패 시 예외 발생
        return response.json()  # 성공 시 JSON 응답 반환
