import logging
from math import log
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from myapi import containers
from myapi.exceptions.futures_exceptions import register_exception_handlers
from myapi.exceptions.index import ServiceException
from myapi.routers import (
    coinone_router,
    ticker_router,
    futures_router,
    kakao_router,
    signal_router,
    trading_router,
    news_router,
)
from myapi.utils.config import init_logging

from .routers import tqqq_router


app = FastAPI()
load_dotenv("myapi/.env")

app.container = containers.Container()  # type: ignore

init_logging()

origins = ["http://localhost:5173"]

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# CORS Middleware
is_dev = os.getenv("ENVIRONMENT", "dev").lower() == "dev"
if is_dev:
    origins = [
        "https://stock.bamtoly.com",
        "http://localhost:5173",
        "http://localhost:5174",
    ]
else:
    origins = ["https://stock.bamtoly.com"]

logger = logging.getLogger(__name__)

# 중복 미들웨어 제거하고 하나만 등록
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for logging requests and responses
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# Exception handler for ServiceException
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    logger.error(f"ServiceException: {exc.name} - {exc.detail}")
    return JSONResponse(
        status_code=400,  # Adjust the status code as needed
        content={"error": exc.name, "detail": exc.detail},
    )

    # Middleware acting as an interceptor to catch exceptions globally


@app.middleware("http")
async def exception_interceptor(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except ServiceException as se:
        # Here you can add logging or any other cross-cutting concerns
        logger.error(f"ServiceException: {se.name} - {se.detail}")
        return await service_exception_handler(request, se)
    except Exception as e:
        # Catch any other unhandled exceptions
        logger.error(f"Unhandled exception: {str(e)}")

        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": str(e)},
        )


@app.get("/hello")
def hello():
    """Function printing python version."""

    return {"message": "Hello World!!"}


app.include_router(tqqq_router.router)
app.include_router(kakao_router.router)
app.include_router(trading_router.router)
app.include_router(coinone_router.router)
app.include_router(futures_router.router)
app.include_router(signal_router.router)
app.include_router(ticker_router.router)
app.include_router(news_router.router)
handler = Mangum(app)
