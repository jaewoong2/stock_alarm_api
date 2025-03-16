# routers/trading_router.py
import logging
from urllib.parse import quote, urlparse
from fastapi import APIRouter, Depends, Request
from myapi.domain.trading.trading_model import TechnicalAnalysisResponse
from myapi.services.ai_service import AIService
from myapi.services.discord_service import DiscordService
from myapi.services.kakao_service import KakaoService
from myapi.services.trading.trade_service import TradingService
from myapi.containers import Container
from dependency_injector.wiring import inject, Provide

router = APIRouter(prefix="/trading")

logger = logging.getLogger(__name__)


@router.get("/prediction", tags=["trading"])
@inject
def prediction_with_chart(
    symbol: str,
    interval: str = "15m",
    trading_service: TradingService = Depends(
        Provide[Container.services.trading_service]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
):
    information = trading_service.trade_executor._get_information(
        symbol, interval, 200, is_plot_use=True
    )

    prompt = """
    The chart includes candlesticks along with Bollinger Bands (BB, 200), RSI, MACD, and ADX indicators.
    
    **I want more specific price movement and price level**
    
    it is not real chart, so you can analyze the chart.

    Please think about the following:
        1. What might the price movement look like over the next 1-2 hours based on these indicators?
        2. What price level could be considered for limiting losses (potential stop loss line)?
        3. What price level might be suitable for entering a position (potential buy line)?
        4. What price level could be a reasonable target for securing gains (potential take profit line)?
        5. What is Your recommendation For me acting right now? 
    """

    if information.plot_image_path is None:
        return None

    encoded_image_url = quote(information.plot_image_path, safe=":/")

    analyze = ai_service.analzye_image(prompt=prompt, image_path=encoded_image_url)

    result = ai_service.transform_message_to_schema(analyze, TechnicalAnalysisResponse)

    return result


@router.get("/monitoring", tags=["trading"])
@inject
def monitoring(
    symbol: str,
    interval: str = "30m",
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
            symbol=symbol.upper(),
            percentage=100,
            interval="1h",
            opinion=content.message,
        )

        result = trade_info.action.model_dump_json()
        logger.info(result)

        discord_service.send_message(content=result)

    return content


@router.post("/trade/{symbol}", tags=["trading"])
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


@router.post("/trade/{symbol}", tags=["trading"])
@inject
def grid_trading(
    symbol: str,
    interval: str = "30m",
    trading_service: TradingService = Depends(
        Provide[Container.services.trading_service]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):

    current_infromations = trading_service.trade_monitor.monitor_triggers(
        symbol=symbol, interval=interval, size=200
    )

    if current_infromations.indicators is None:
        return

    ai_result = ai_service.analyze_grid(
        indicators=current_infromations.indicators,
        symbol=symbol,
        interval=interval,
        size=200,
        market_data={},
    )
