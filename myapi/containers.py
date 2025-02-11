from dependency_injector import containers, providers

from myapi.services.kakao_service import KakaoService
from myapi.services.tqqq_service import TqqqService


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "myapi.routers.kakao_router",
            "myapi.routers.tqqq_router",
        ],
    )

    kakao_service = providers.Factory(KakaoService)
    tqqq_service = providers.Factory(TqqqService)
