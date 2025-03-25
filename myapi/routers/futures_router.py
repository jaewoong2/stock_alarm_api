from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.database import get_db
from myapi.domain.futures.futures_schema import (
    ExecuteFuturesRequest,
    FuturesConfigRequest,
    FuturesCreate,
    FuturesResponse,
    TechnicalAnalysis,
    TechnicalAnalysisRequest,
)
from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.futures_service import FuturesService

router = APIRouter(prefix="/futures", tags=["futures"])


@router.get("/balance", tags=["futures"])
@inject
async def get_futures_balance(
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    return futures_service.fetch_balnce()


@router.get("/{symbol}", tags=["futures"], response_model=List[FuturesResponse])
@inject
async def get_futures(
    symbol: str,
    repo: FuturesRepository = Depends(
        Provide[Container.repositories.futures_repository]
    ),
):
    futures = repo.get_futures_by_symbol(symbol)
    if not futures:
        raise HTTPException(status_code=404, detail="No futures found")
    return futures


@router.get("/ticker/{symbol}")
@inject
async def get_ticker(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        ticker = futures_service.fetch_ticker(symbol)
        return {"symbol": f"{symbol}/USDT", "price": ticker.last}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{symbol}", tags=["futures"], response_model=TechnicalAnalysis)
@inject
async def get_technical_analysis(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        df = futures_service.fetch_ohlcv(symbol)
        return futures_service.perform_technical_analysis(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/openai-analysis")
@inject
async def get_openai_analysis(
    data: TechnicalAnalysisRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        return futures_service.analyze_with_openai(
            data.symbol, timeframe=data.interval, limit=data.size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI analysis failed: {str(e)}")


@router.post("/execute", tags=["futures"])
@inject
async def execute_futures_with_ai(
    data: ExecuteFuturesRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        # AI 분석 요청

        # 분석 결과 Logging / Discode 전송

        # AI 분석 결과를 바탕으로 선물 거래 실행
        # - 기존 거래
        #   - 같은 포지션 일 경우, (TP/SL) 수정
        #   - 다른 포지션 일 경우, 전체 주문 취소, 포지션 종료 및 새롭게 시작
        #   - 취소 일 경우, 전체 주문 취소, 포지션 종료

        # 선물 거래 결과 Logging / Discode 전송

        # 전체 결과 DB 저장

        return futures_service.execute_futures_with_suggestion(
            data.symbol, data.target_currency, data.limit, data.timeframe
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )


@router.post("/config", tags=["futures"])
@inject
async def set_futures_config(
    data: FuturesConfigRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        return futures_service.set_position(data)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )
