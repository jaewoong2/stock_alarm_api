from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from datetime import date

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ticker.ticker_schema import (
    TickerCreate,
    TickerResponse,
    TickerUpdate,
    TickerMultiDateQuery,
    TickerChangeResponse,
)
from myapi.services.ticker_service import TickerService

router = APIRouter(
    prefix="/tickers",
    tags=["tickers"],
)


@router.get("/{ticker_id}", response_model=TickerResponse)
@inject
def get_ticker(
    ticker_id: int,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = ticker_service.get_ticker(ticker_id)
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return ticker


@router.get("/symbol/{symbol}", response_model=TickerResponse)
@inject
def get_ticker_by_symbol(
    symbol: str,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = ticker_service.get_ticker_by_symbol(symbol)
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return ticker


@router.get("/", response_model=List[TickerResponse])
@inject
def get_tickers(
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    return ticker_service.get_all_tickers()


@router.post("/", response_model=TickerResponse)
@inject
def create_ticker(
    ticker: TickerCreate,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    existing = ticker_service.get_ticker_by_symbol(ticker.symbol)
    if existing:
        raise HTTPException(status_code=400, detail="Symbol already registered")

    return ticker_service.create_ticker(ticker)


@router.put("/{ticker_id}", response_model=TickerResponse)
@inject
def update_ticker(
    ticker_id: int,
    ticker: TickerUpdate,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    updated_ticker = ticker_service.update_ticker(ticker_id, ticker)
    if updated_ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return updated_ticker


@router.delete("/{ticker_id}")
@inject
def delete_ticker(
    ticker_id: int,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    if not ticker_service.delete_ticker(ticker_id):
        raise HTTPException(status_code=404, detail="Ticker not found")
    return {"message": "Ticker deleted successfully"}


# 새로운 엔드포인트: 특정 날짜의 티커 정보 조회
@router.get("/by-date", response_model=TickerResponse)
@inject
def get_ticker_by_date(
    symbol: str = Query(..., description="티커 심볼"),
    date: date = Query(..., description="조회할 날짜"),
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = ticker_service.get_ticker_by_date(symbol, date)
    if ticker is None:
        raise HTTPException(
            status_code=404, detail="해당 날짜의 티커 정보를 찾을 수 없습니다"
        )

    return ticker


# 새로운 엔드포인트: 날짜별 변화율 조회
@router.post("/changes", response_model=List[TickerChangeResponse])
@inject
def get_ticker_changes(
    query: TickerMultiDateQuery,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    # 심볼이 존재하는지 확인
    ticker = ticker_service.get_ticker_by_symbol(query.symbol)
    if ticker is None:
        raise HTTPException(
            status_code=404, detail="해당 심볼의 티커를 찾을 수 없습니다"
        )

    # 날짜 리스트에 대한 변화율 조회
    changes = ticker_service.get_ticker_changes(query.symbol, query.dates)
    if not changes:
        raise HTTPException(
            status_code=404, detail="요청한 날짜에 대한 데이터를 찾을 수 없습니다"
        )

    return changes
