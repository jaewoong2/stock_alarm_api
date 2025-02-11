"""Function printing python version."""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware

from myapi import containers
from myapi.routers import kakao_router

from .routers import tqqq_router


app = FastAPI()
load_dotenv("myapi/.env")
os.getenv("AWS_ACCESS_KEY_ID")
app.container = containers.Container()


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
handler = Mangum(app)
