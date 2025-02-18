"""Function printing python version."""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from myapi import containers
from myapi.routers import coinone_router, kakao_router, trading_router

from .routers import tqqq_router


app = FastAPI()
load_dotenv("myapi/.env")

app.container = containers.Container()  # type: ignore


origins = ["http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
