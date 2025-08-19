import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from myapi import containers
from myapi.exceptions.index import ServiceException
from myapi.routers import health_router
from myapi.utils.config import init_logging

app = FastAPI()
load_dotenv("myapi/.env")
app.container = containers.Container()  # type: ignore

init_logging()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    logger.error(f"ServiceException: {exc.name} - {exc.detail}")
    return JSONResponse(
        status_code=400,
        content={"error": exc.name, "detail": exc.detail},
    )


@app.get("/")
def hello() -> dict:
    return {"message": "Hello World!"}


app.include_router(health_router.router)

handler = Mangum(app)
