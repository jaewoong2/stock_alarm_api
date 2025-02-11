from fastapi import APIRouter, Depends, HTTPException
import requests
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.kakao.kakao_schema import KakaoToken
from myapi.routers import tqqq_router
from myapi.services.aws_service import AwsService
from myapi.services.kakao_service import (
    KakaoService,
)  # service에서 발생할 수 있는 requests 예외 처리를 위해 사용


router = APIRouter(prefix="/api/kakao")


@router.post("/refresh")
@inject
async def refresh_token(
    kakao_service: KakaoService = Depends(Provide[Container.kakao_service]),
):
    secret_data = AwsService.get_secret()
    prev_token = KakaoToken(
        access_token=secret_data.get("kakao_access_token", ""),
        refresh_token=secret_data.get("kakao_refresh_token", ""),
    )

    token = kakao_service.refresh_toen(prev_token.refresh_token)
    secret_data = {}

    secret_data["kakao_access_token"] = token.access_token
    if token.refresh_token:
        secret_data["kakao_refresh_token"] = token.refresh_token
    else:
        secret_data["kakao_refresh_token"] = prev_token.refresh_token

    AwsService.update_secret(secret_data)

    return {"message": "Success"}


@router.post("/send-kakao-message")
@inject
async def send_kakao_message_endpoint(
    kakao_service: KakaoService = Depends(Provide[Container.kakao_service]),
):
    """
    카카오톡 메시지 전송 API 엔드포인트
    """
    try:
        await refresh_token()
        secret_data = AwsService.get_secret()
        token = KakaoToken(
            access_token=secret_data.get("kakao_access_token", ""),
            refresh_token=secret_data.get("kakao_refresh_token", ""),
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
