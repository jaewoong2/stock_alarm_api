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
from myapi.services.trading.trade_service import TradingService
from myapi.utils.config import Settings


class ConfigModule(containers.DeclarativeContainer):
    """환경 설정 및 공통 의존성 관리"""

    config = providers.Singleton(Settings)


class RepositoryModule(containers.DeclarativeContainer):
    """데이터베이스 관련 의존성 관리"""

    db = providers.Resource(get_db)
    trading_repository = providers.Singleton(TradingRepository, db_session=db)


class ServiceModule(containers.DeclarativeContainer):
    """각 서비스의 의존성 관리"""

    config = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()

    aws_service = providers.Factory(AwsService, settings=config.config)
    kakao_service = providers.Factory(
        KakaoService, settings=config.config, aws_service=aws_service
    )
    backdata_service = providers.Factory(
        BackDataService,
        settings=config.config,
        trading_repository=repositories.trading_repository,
    )
    tqqq_service = providers.Factory(TqqqService, settings=config.config)
    ai_service = providers.Factory(AIService, settings=config.config)
    coinone_service = providers.Factory(CoinoneService, settings=config.config)
    trading_service = providers.Factory(
        TradingService,
        settings=config.config,
        ai_service=ai_service,
        backdata_service=backdata_service,
        coinone_service=coinone_service,
        trading_repository=repositories.trading_repository,
    )
    discord_service = providers.Factory(DiscordService, settings=config.config)


class Container(containers.DeclarativeContainer):
    """전체 의존성 컨테이너"""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "myapi.routers.kakao_router",
            "myapi.routers.tqqq_router",
            "myapi.routers.trading_router",
            "myapi.routers.coinone_router",
        ],
    )

    config = providers.Container(ConfigModule)
    repositories = providers.Container(RepositoryModule)
    services = providers.Container(
        ServiceModule, config=config, repositories=repositories
    )
