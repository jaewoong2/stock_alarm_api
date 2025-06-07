import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import date, timedelta

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ticker.ticker_schema import (
    SignalAccuracyResponse,
    TickerCreate,
    TickerLatestWithChangeResponse,
    TickerResponse,
    TickerUpdate,
    TickerMultiDateQuery,
    TickerChangeResponse,
)
from myapi.services.db_signal_service import DBSignalService
from myapi.services.ticker_service import TickerService

router = APIRouter(
    prefix="/tickers",
    tags=["tickers"],
)


@router.get("/symbol/{symbol}", response_model=List[TickerResponse])
@inject
def get_ticker_by_symbol(
    symbol: str,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    ticker = ticker_service.get_ticker_by_symbol(symbol)
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    return ticker


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
    # date_obj = datetime.date.fromisoformat(date)  # 문자열을 date 객체로 변환
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


# get_latest_tickers_with_changes 엔드포인트 수정
@router.get("/latest", response_model=List[TickerLatestWithChangeResponse])
@inject
async def get_latest_tickers_with_changes(
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
):
    """
    모든 티커의 가장 최근 데이터와 전날 대비 가격 변화율, 그리고 관련 시그널 정보를 제공합니다.
    """
    try:
        # 수정된 메서드 호출
        tickers = ticker_service.get_latest_tickers_with_changes()

        # 각 티커에 대한 전날 시그널 정보 추가
        for ticker in tickers:
            if not ticker.date:
                continue

            yesterday = ticker.date - timedelta(days=1)
            signals = await db_signal_service.get_signals_by_date_and_ticker(
                ticker.symbol, yesterday
            )
            if signals and len(signals) > 0:
                # 시그널이 존재하면 첫 번째 시그널 정보만 사용
                ticker.signal = signals[0].model_dump()

        return tickers
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"티커 데이터 조회 중 오류 발생: {str(e)}"
        )


# 시그널 예측 정확도 평가
@router.get("/signal-accuracy/{ticker}", response_model=SignalAccuracyResponse)
@inject
def evaluate_signal_accuracy(
    ticker: str,
    signal_id: Optional[int] = None,
    days: Optional[int] = 5,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    """
    특정 티커의 시그널 예측 정확도를 평가합니다.
    - ticker: 티커 심볼
    - signal_id: 평가할 시그널 ID (없으면 가장 최근 시그널 사용)
    - days: 몇 일 후의 결과를 확인할지 (기본 5일)
    """
    try:
        if not ticker:
            raise HTTPException(status_code=400, detail="티커 심볼이 필요합니다")
        if not days or days <= 0:
            raise HTTPException(status_code=400, detail="일 수는 1 이상이어야 합니다")
        if signal_id is not None and days <= 0:
            raise HTTPException(
                status_code=400,
                detail="시그널 ID가 있을 때는 days를 1 이상으로 설정해야 합니다",
            )

        if signal_id is None:
            raise HTTPException(
                status_code=404, detail="해당 티커에 대한 시그널이 없습니다"
            )
        # 시그널 정확도 평가 메서드 호출
        result = ticker_service.evaluate_signal_accuracy(ticker, signal_id, days)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"시그널 정확도 평가 중 오류 발생: {str(e)}"
        )
