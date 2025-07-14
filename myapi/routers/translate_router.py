import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends
from dependency_injector.wiring import Provide, inject

from myapi.containers import Container
from myapi.services.translate_service import TranslateService
from myapi.utils.auth import verify_bearer_token

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("/signals", dependencies=[Depends(verify_bearer_token)])
@inject
def translate_signals(
    target_date: Optional[dt.date] = dt.date.today(),
    service: TranslateService = Depends(Provide[Container.services.translate_service]),
):
    """
    특정 날짜의 신호를 번역하고 마크다운 형식으로 반환합니다.
    """
    target_date = target_date if target_date else dt.date.today()

    result = service.translate_and_markdown(target_date)
    return result


@router.get("/signals")
@inject
def get_translated_signals(
    target_date: Optional[dt.date] = dt.date.today(),
    service: TranslateService = Depends(Provide[Container.services.translate_service]),
):
    target_date = target_date if target_date else dt.date.today()

    result = service.get_translated_signals(target_date)
    return result


@router.get("/signals/ticker")
@inject
def get_translated_signals_by_ticker(
    ticker: str,
    target_date: Optional[dt.date] = dt.date.today(),
    service: TranslateService = Depends(Provide[Container.services.translate_service]),
):
    target_date = target_date if target_date else dt.date.today()
    result = service.get_translated_by_ticker(ticker=ticker, target_date=target_date)
    return result
