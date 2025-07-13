import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends
from dependency_injector.wiring import Provide, inject

from myapi.containers import Container
from myapi.services.translate_service import TranslateService
from myapi.utils.auth import verify_bearer_token

router = APIRouter(prefix="/translate", tags=["translate"])


@router.get("/signals", dependencies=[Depends(verify_bearer_token)])
@inject
def get_translated_signals(
    target_date: Optional[dt.date] = dt.date.today(),
    service: TranslateService = Depends(Provide[Container.services.translate_service]),
):
    target_date = target_date if target_date else dt.date.today()

    result = service.translate_and_markdown(target_date)
    return result
