from fastapi import APIRouter, Depends, HTTPException, Query


from myapi.utils.auth import verify_bearer_token
from typing import List, Literal, Optional
from datetime import datetime, timedelta
import datetime as dt

from myapi.utils.date_utils import validate_date

from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.signal.signal_schema import DefaultTickers, GetSignalRequest
from myapi.domain.ticker.ticker_schema import (
    SignalAccuracyResponse,
    TickerCreate,
    TickerLatestWithChangeResponse,
    TickerOrderBy,
    TickerResponse,
    TickerUpdate,
    TickerMultiDateQuery,
    TickerChangeResponse,
    UpdateTickerRequest,
)
from myapi.services.db_signal_service import DBSignalService
from myapi.services.ticker_service import TickerService
from myapi.utils.utils import get_prev_date

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
    request_date: dt.date = Query(..., alias="date", description="조회할 날짜"),
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    validate_date(request_date)
    ticker = ticker_service.get_ticker_by_date(symbol, request_date)
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


@router.post("/update", dependencies=[Depends(verify_bearer_token)])
@inject
def update_ticker_informations(
    request: UpdateTickerRequest,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    """
    티커 정보를 업데이트합니다. 이 엔드포인트는 티커의 심볼, 이름, 가격 등을 갱신합니다.
    """
    try:
        results = []

        if request.start_date and request.end_date:
            start_date, end_date = (
                datetime.strptime(request.start_date, "%Y-%m-%d"),
                datetime.strptime(request.end_date, "%Y-%m-%d"),
            )
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

        tickers = ticker_service.get_all_ticker_name()

        backday = (end_date - start_date).days

        if backday <= 0:
            raise HTTPException(
                status_code=400, detail="종료 날짜는 시작 날짜보다 이후여야 합니다"
            )
        if not tickers:
            raise HTTPException(
                status_code=400, detail="업데이트할 티커 목록이 비어 있습니다"
            )

        for ticker in tickers:
            result = ticker_service.update_ticker_informations(
                ticker=ticker,
                start=start_date,
                end=end_date,
            )

            results.append(result)

        return {
            "message": "Ticker information updated successfully",
            "results": results,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"티커 정보 업데이트 중 오류 발생: {str(e)}"
        )


@router.get("/signals", response_model=List[SignalAccuracyResponse])
@inject
def get_signal_accuracy(
    db_signal_service: DBSignalService = Depends(
        Provide[Container.services.db_signal_service]
    ),
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    """
    주어진 티커들의 시그널 예측 정확도를 평가합니다.
    """
    try:
        # 기본 티커 목록 가져오기
        tickers = DefaultTickers

        if not tickers:
            raise HTTPException(status_code=404, detail="등록된 티커가 없습니다")

        # 시그널 정확도 조회
        signals = db_signal_service.get_all_signals(GetSignalRequest())
        tickers = ticker_service.get_all_tickers()

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"시그널 정확도 조회 중 오류 발생: {str(e)}"
        )


@router.get("/weekly/price-movement")
@inject
def get_weekly_price_movement(
    tickers: Optional[str] = None,
    reference_date: Optional[dt.date] = dt.date.today(),
    direction: Literal["up", "down"] = "up",
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    """일주일간 가격이 상승하거나 하락한 횟수를 조회합니다."""

    ticker_list = (
        [t.strip().upper() for t in tickers.split(",") if t]
        if tickers
        else DefaultTickers
    )

    yesterday = dt.date.today() - timedelta(days=1)

    end_dt = validate_date(
        reference_date - timedelta(days=1) if reference_date else yesterday
    )
    start_dt = end_dt - timedelta(days=6)

    tickers_with_count = ticker_service.count_price_movements(
        ticker_list, start_dt, end_dt, direction
    )

    return {
        "tickers": tickers_with_count,
    }


@router.get("/order-by/date")
@inject
def get_tickers_ordered_by(
    target_date: Optional[dt.date] = dt.date.today(),
    direction: Literal["asc", "desc"] = "asc",
    field: Literal["close_change", "volume_change"] = "close_change",
    limit: int = 20,
    ticker_service: TickerService = Depends(Provide[Container.services.ticker_service]),
):
    """
    티커를 심볼, 가격, 변화율에 따라 정렬하여 조회합니다.
    """

    target_date = validate_date(target_date) if target_date else dt.date.today()
    target_date_yesterday = get_prev_date(target_date)

    response = ticker_service.get_ticker_orderby(
        target_date_yesterday, TickerOrderBy(field=field, direction=direction), limit
    )

    return response
