# discord_service.py
import requests
import os

from myapi.utils.config import Settings


class DiscordService:
    def __init__(self, settings: Settings):
        self.webhook_url = settings.DISCORD_WEBHOOK_URL
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL 환경 변수가 설정되지 않았습니다.")

    def send_message(self, content: str):
        """
        디스코드 웹훅을 통해 메시지 전송
        """
        payload = {"content": content}
        response = requests.post(self.webhook_url, json=payload)
        response.raise_for_status()  # 실패 시 예외 발생
