from dependency_injector import containers, providers

from myapi.database import get_db
from myapi.services.aws_service import AwsService
from myapi.utils.config import Settings

class ConfigModule(containers.DeclarativeContainer):
    """Application configuration."""

    config = providers.Singleton(Settings)

class RepositoryModule(containers.DeclarativeContainer):
    """Database repositories."""

    get_db = providers.Resource(get_db)

class ServiceModule(containers.DeclarativeContainer):
    """Service layer dependencies."""

    config = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()

    aws_service = providers.Factory(AwsService, settings=config.config)

class Container(containers.DeclarativeContainer):
    """Application container."""

    wiring_config = containers.WiringConfiguration(
        modules=["myapi.routers.health_router"],
    )

    config = providers.Container(ConfigModule)
    repositories = providers.Container(RepositoryModule)
    services = providers.Container(
        ServiceModule, config=config, repositories=repositories
    )
