from fastapi import APIRouter, Depends, HTTPException
import requests
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.kakao.kakao_schema import KakaoToken
from myapi.routers import tqqq_router
from myapi.services.aws_service import AwsService
from myapi.services.kakao_service import (
    KakaoService,
)

router = APIRouter(prefix="/api/kakao")


@router.get("/token")
@inject
async def get_token(
    kakao_service: KakaoService = Depends(Provide[Container.kakao_service]),
    aws_service: AwsService = Depends(Provide[Container.aws_service]),
):
    tokens = kakao_service.get_oauth_token()

    aws_service.update_secret(tokens)

    return tokens


@router.post("/refresh")
@inject
async def refresh_token(
    aws_service: AwsService = Depends(Provide[Container.aws_service]),
    kakao_service: KakaoService = Depends(Provide[Container.kakao_service]),
):
    try:

        secret_data = aws_service.get_secret()
        prev_token = KakaoToken(
            access_token=secret_data.get("access_token", ""),
            refresh_token=secret_data.get("refresh_token", ""),
        )

        token = kakao_service.refresh_toen(prev_token.refresh_token)
        secret_data = {}

        secret_data["access_token"] = token.access_token
        if token.refresh_token:
            secret_data["refresh_token"] = token.refresh_token
        else:
            secret_data["refresh_token"] = prev_token.refresh_token

        aws_service.update_secret(secret_data)

        return {"message": "Success"}

    except Exception as e:
        auth_token = kakao_service.get_oauth_token()
        if auth_token:
            aws_service.update_secret(auth_token)

        return e


@router.post("/send-kakao-message")
@inject
async def send_kakao_message_endpoint(
    kakao_service: KakaoService = Depends(Provide[Container.kakao_service]),
    aws_service: AwsService = Depends(Provide[Container.aws_service]),
):
    """
    카카오톡 메시지 전송 API 엔드포인트
    """
    try:
        await refresh_token()
        secret_data = aws_service.get_secret()
        token = KakaoToken(
            access_token=secret_data.get("access_token", ""),
            refresh_token=secret_data.get("refresh_token", ""),
        )

        text_message = tqqq_router.create_answer()

        template_object = {
            "object_type": "text",
            "text": text_message,
            "link": {
                "web_url": "https://m.stock.naver.com/worldstock/etf/TQQQ.O/total",
                "mobile_web_url": "https://m.stock.naver.com/worldstock/etf/TQQQ.O/total",
            },
            "button_title": "네이버 금융 보기",
        }

        kakao_service.send_message(
            token=token.access_token, template_object=template_object
        )

        return {"status": "success", "data": template_object}
    except requests.exceptions.HTTPError as http_err:
        # 카카오 API 호출 중 HTTP 에러가 발생한 경우
        raise HTTPException(
            status_code=500, detail=f"Kakao API error: {http_err.response.text}"
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
