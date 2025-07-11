from __future__ import annotations

import datetime
from fastapi import APIRouter, Depends
from dependency_injector.wiring import Provide, inject

from myapi.containers import Container
from myapi.services.translate_service import TranslateService
from myapi.utils.auth import verify_bearer_token

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/signals", dependencies=[Depends(verify_bearer_token)])
@inject
def get_translated_signals(
    target_date: datetime.date,
    service: TranslateService = Depends(Provide[Container.services.translate_service]),
):
    result = service.translate_and_markdown(target_date)
    return result

