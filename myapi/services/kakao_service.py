# services/kakao_service.py
import json
import requests

from myapi.domain.kakao.kakao_schema import KakaoToken, KakaoTokenResponse
from myapi.services.aws_service import AwsService
from myapi.utils.config import Settings


class KakaoService:
    def __init__(self, settings: Settings, aws_service: AwsService):
        self.rest_api_access_token = settings.KAKAO_REST_API_KEY
        self.kakao_my_auth_token = settings.KAKAO_MY_AUTH_TOKEN
        self.kakao_secret_key = settings.KAKAO_ADMIN_KEY
        self.base_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
        self.aws_service = aws_service

    def read_tokens(self):
        """
        AWS Secrets Manager에서 Kakao access_token과 refresh_token을 읽어 반환합니다.
        """
        secret_data = self.aws_service.get_secret()
        # secret_data에서 토큰 값을 읽어오되, 값이 없으면 빈 문자열로 반환합니다.
        return KakaoToken(
            access_token=secret_data.get("access_token", ""),
            refresh_token=secret_data.get("refresh_token", ""),
        )

    def refresh_toen(self, refresh_token) -> KakaoTokenResponse:

        url = "https://kauth.kakao.com/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        data = {
            "grant_type": "refresh_token",
            "client_id": self.rest_api_access_token,
            "redirect_uri": "https://api.bamtoly.com/api",
            "refresh_token": refresh_token,
        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()

        result: KakaoTokenResponse = KakaoTokenResponse(**response.json())

        return result

    def get_oauth_token(self) -> dict:
        """
        authorization code를 access token으로 교환하는 로직
        cURL 명령과 동일한 역할을 합니다.
        """

        url = "https://kauth.kakao.com/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        data = {
            "grant_type": "authorization_code",
            "client_id": self.rest_api_access_token,
            "redirect_uri": "https://api.bamtoly.com/api",
            "client_secret": self.kakao_secret_key,
            "code": self.kakao_my_auth_token,
        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()

        return response.json()

    def send_message(
        self,
        token: str,
        template_object: dict | None = None,
        message: str | None = None,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        }

        data = {"template_object": ""}

        if message and not template_object:
            data["template_object"] = json.dumps(
                {
                    "object_type": "text",
                    "text": message,
                    "link": {"web_url": "www.naver.com"},
                }
            )

        if template_object and not message:
            data["template_object"] = json.dumps(template_object)

        response = requests.post(self.base_url, data=data, headers=headers)
        # 요청 실패 시 예외 발생
        response.raise_for_status()
        return response.json()
