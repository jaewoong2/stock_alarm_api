from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.database import get_db
from myapi.domain.futures.futures_schema import (
    FuturesCreate,
    FuturesResponse,
    TechnicalAnalysis,
)
from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.futures_service import FuturesService

router = APIRouter(prefix="/futures", tags=["futures"])


@router.post("/", response_model=FuturesResponse)
@inject
async def create_futures(
    futures: FuturesCreate,
    db: Session = Depends(get_db),
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    repo: FuturesRepository = Depends(lambda: FuturesRepository()),
):
    return repo.create_futures(db, futures)


@router.get("/{symbol}", response_model=List[FuturesResponse])
@inject
async def get_futures(
    symbol: str,
    db: Session = Depends(get_db),
    repo: FuturesRepository = Depends(lambda: FuturesRepository()),
):
    futures = repo.get_futures_by_symbol(db, symbol)
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
        return {"symbol": symbol, "price": ticker.last}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{symbol}", response_model=TechnicalAnalysis)
@inject
async def get_technical_analysis(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        return futures_service.perform_technical_analysis(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/openai-analysis/{symbol}")
@inject
async def get_openai_analysis(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        return futures_service.analyze_with_openai(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI analysis failed: {str(e)}")


@router.post("/execute/{symbol}", response_model=FuturesResponse)
@inject
async def execute_futures_with_ai(
    symbol: str,
    quantity: float = 0.001,
    db: Session = Depends(get_db),
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    repo: FuturesRepository = Depends(lambda: FuturesRepository()),
):
    try:
        return futures_service.execute_futures_with_suggestion(
            db, symbol, quantity, repo
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )
