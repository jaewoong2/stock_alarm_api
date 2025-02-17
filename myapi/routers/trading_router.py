# routers/trading_router.py
from fastapi import APIRouter, Depends
from myapi.services.trading_service import TradingService
from myapi.containers import Container
from dependency_injector.wiring import inject, Provide

router = APIRouter(prefix="/trading")


@router.get("")
@inject
def get_trading_information(
    trading_service: TradingService = Depends(Provide[Container.trading_service]),
):
    """
    코인 거래 정보를 가져옵니다.
    """
    trading_info = trading_service.get_trading_information()

    return trading_info


@router.post("/trade/{symbol}/{amount}")
@inject
def trade(
    symbol: str,
    percentage: int = 100,
    trading_service: TradingService = Depends(Provide[Container.trading_service]),
):
    """
    코인 심볼과 주문 수량을 받아서 매매를 실행합니다.
    AI 판단 결과에 따라 주문이 실행되며, 실행 내역은 로그에 저장됩니다.
    """
    trade_info = trading_service.execute_trade(symbol, percentage / 100)
    return trade_info
