from typing import List

from fastapi import APIRouter, Depends, HTTPException
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ticker.ticker_schema import (
    TickerCreate,
    TickerResponse,
    TickerUpdate,
)
from myapi.services.ticker_service import TickerService

router = APIRouter(prefix="/tickers", tags=["ticker"])


@router.post("/", response_model=TickerResponse)
@inject
def create_ticker(
    data: TickerCreate,
    service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    return service.create_ticker(data)


@router.get("/", response_model=List[TickerResponse])
@inject
def list_tickers(
    service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    return service.get_all_tickers()


@router.get("/{ticker_id}", response_model=TickerResponse)
@inject
def get_ticker(
    ticker_id: int,
    service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = service.get_ticker(ticker_id)
    if not ticker:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return ticker


@router.put("/{ticker_id}", response_model=TickerResponse)
@inject
def update_ticker(
    ticker_id: int,
    data: TickerUpdate,
    service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = service.update_ticker(ticker_id, data)
    if not ticker:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return ticker


@router.delete("/{ticker_id}")
@inject
def delete_ticker(
    ticker_id: int,
    service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    success = service.delete_ticker(ticker_id)
    if not success:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return {"result": "success"}
