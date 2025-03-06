# routers/trading_router.py
import logging
from fastapi import APIRouter, Depends, Request
from myapi.services.discord_service import DiscordService
from myapi.services.kakao_service import KakaoService
from myapi.services.trading.trade_service import TradingService
from myapi.containers import Container
from dependency_injector.wiring import inject, Provide

router = APIRouter(prefix="/trading")

logger = logging.getLogger(__name__)


@router.get("/monitoring")
@inject
def monitoring(
    symbol: str,
    interval: str = "15m",
    trading_service: TradingService = Depends(
        Provide[Container.services.trading_service]
    ),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    content = trading_service.monitor_triggers(symbol=symbol, interval=interval)

    logger.info(content)

    discord_service.send_message(content=content.model_dump_json())

    if content.status == "BUY" or content.status == "SELL":
        trade_info = trading_service.execute_trade(
            symbol=symbol,
            percentage=100,
            interval="1h",
            opinion=content.message,
        )

        result = trade_info.action.model_dump_json()
        logger.info(result)

        discord_service.send_message(content=result)

    return content


@router.post("/trade/{symbol}")
@inject
def trade(
    symbol: str,
    percentage: int = 100,
    interval: str = "",
    opinion: str = "",
    trading_service: TradingService = Depends(
        Provide[Container.services.trading_service]
    ),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    """
    코인 심볼과 주문 수량을 받아서 매매를 실행합니다.
    AI 판단 결과에 따라 주문이 실행되며, 실행 내역은 로그에 저장됩니다.
    """
    trade_info = trading_service.execute_trade(
        symbol=symbol,
        percentage=percentage / 100,
        interval=interval,
        opinion=opinion,
    )

    discord_service.send_message(content=trade_info.action.model_dump_json())

    return trade_info
