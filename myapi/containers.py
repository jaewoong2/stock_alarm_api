from dependency_injector import containers, providers

from myapi.database import get_db
from myapi.repositories.trading_repository import TradingRepository
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.coinone_service import CoinoneService
from myapi.services.discord_service import DiscordService
from myapi.services.kakao_service import KakaoService
from myapi.services.backdata_service import BackDataService
from myapi.services.tqqq_service import TqqqService
from myapi.services.trading_service import TradingService
from myapi.utils.config import Settings


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "myapi.routers.kakao_router",
            "myapi.routers.tqqq_router",
            "myapi.routers.trading_router",
            "myapi.routers.coinone_router",
        ],
    )

    # DB 딕셔너리 리소스 제공자
    db = providers.Resource(get_db)

    config = providers.Singleton(Settings)

    trading_repository = providers.Singleton(TradingRepository, db_session=db)

    aws_service = providers.Factory(AwsService, settings=config)
    kakao_service = providers.Factory(
        KakaoService, settings=config, aws_service=aws_service
    )
    backdata_service = providers.Factory(
        BackDataService, settings=config, trading_repository=trading_repository
    )
    tqqq_service = providers.Factory(TqqqService, settings=config)

    ai_service = providers.Factory(AIService, settings=config)
    # log_service = providers.Singleton(LogService)
    coinone_service = providers.Factory(CoinoneService, settings=config)
    trading_service = providers.Factory(
        TradingService,
        settings=config,
        ai_service=ai_service,
        backdata_service=backdata_service,
        coinone_service=coinone_service,
        trading_repository=trading_repository,
    )

    discord_service = providers.Factory(DiscordService, settings=config)
