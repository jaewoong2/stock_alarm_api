from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from myapi import containers
from myapi.exceptions.index import ServiceException
from myapi.routers import coinone_router, kakao_router, trading_router
from myapi.utils.config import init_logging

from .routers import tqqq_router


app = FastAPI()
load_dotenv("myapi/.env")

app.container = containers.Container()  # type: ignore

init_logging()

origins = ["http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for ServiceException
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
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
        return await service_exception_handler(request, se)
    except Exception as e:
        # Catch any other unhandled exceptions
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
handler = Mangum(app)
