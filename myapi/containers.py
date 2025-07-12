from dependency_injector import containers, providers

from myapi.database import get_db
from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.ticker_repository import TickerRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.db_signal_service import DBSignalService
from myapi.services.discord_service import DiscordService
from myapi.services.signal_service import SignalService
from myapi.services.ticker_service import TickerService
from myapi.services.web_search_service import WebSearchService
from myapi.services.translate_service import TranslateService
from myapi.utils.config import Settings


class ConfigModule(containers.DeclarativeContainer):
    """Environment configuration"""

    config = providers.Singleton(Settings)


class RepositoryModule(containers.DeclarativeContainer):
    """Database repositories"""

    get_db = providers.Resource(get_db)
    signals_repository = providers.Factory(SignalsRepository, db_session=get_db)
    ticker_repository = providers.Factory(TickerRepository, db_session=get_db)
    web_search_repository = providers.Factory(
        WebSearchResultRepository, db_session=get_db
    )


class ServiceModule(containers.DeclarativeContainer):
    """Service layer dependencies"""

    config = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()

    aws_service = providers.Factory(AwsService, settings=config.config)
    ai_service = providers.Factory(AIService, settings=config.config)
    discord_service = providers.Factory(DiscordService, settings=config.config)

    signal_service = providers.Factory(
        SignalService,
        signals_repository=repositories.signals_repository,
        web_search_repository=repositories.web_search_repository,
        settings=config.config,
    )
    ticker_service = providers.Factory(
        TickerService,
        ticker_repository=repositories.ticker_repository,
        signals_repository=repositories.signals_repository,
        signals_service=signal_service,
    )
    db_signal_service = providers.Factory(
        DBSignalService, repository=repositories.signals_repository
    )
    websearch_service = providers.Factory(
        WebSearchService,
        websearch_repository=repositories.web_search_repository,
        ai_service=ai_service,
    )
    translate_service = providers.Factory(
        TranslateService,
        signals_repository=repositories.signals_repository,
        analysis_repository=repositories.web_search_repository,
    )


class Container(containers.DeclarativeContainer):
    """Application container"""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "myapi.routers.signal_router",
            "myapi.routers.ticker_router",
            "myapi.routers.news_router",
            "myapi.routers.auth_router",
            "myapi.routers.translate_router",
        ]
    )

    config = providers.Container(ConfigModule)
    repositories = providers.Container(RepositoryModule)
    services = providers.Container(
        ServiceModule, config=config, repositories=repositories
    )
