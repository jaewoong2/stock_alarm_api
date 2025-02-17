"""Function printing python version."""

from fastapi import APIRouter, Depends, HTTPException, status
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.services.tqqq_service import TqqqService


router = APIRouter(prefix="/api/tqqq")


# --- 설정 변수 ---
DATA_RANGE_DAYS = 400  # 가져올 데이터 일수
DEFAULT_GRAPH_DISPLAY_DAYS = 100  # 차트에 표시할 기본 일수


# Envelope 상한 (200일 SMA × 1.1): 이 평균에 10%를 추가한 값으로,
# 주가가 이 상한선을 넘어서면 일반적으로
# "가격이 평균보다 많이 상승했다"는 의미로 해석할 수 있습니다.
@router.get(
    "/fetch",
    status_code=status.HTTP_200_OK,
    response_model=str,
)
@inject
def create_answer(
    tqqq_service: TqqqService = Depends(Provide[Container.tqqq_service]),
):
    try:
        result = tqqq_service.get_actions()
        message = tqqq_service.recommend_to_message(result)

        return message

    except Exception as e:
        print(e)
        # 에러 발생 시, 500 에러 반환
        raise HTTPException(status_code=500, detail="Error generating response.")
