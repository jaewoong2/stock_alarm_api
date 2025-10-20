from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import yfinance

from myapi.domain.signal.signal_schema import DefaultTickers
from myapi.utils.auth import create_access_token
from myapi.utils.config import get_settings
from myapi.utils.yfinance_cache import configure_yfinance_cache, safe_get_ticker_info
import os
import requests
from typing import Iterable, Dict, Optional

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBasic()

configure_yfinance_cache()


@router.post("/token")
def generate_token(credentials: HTTPBasicCredentials = Depends(security)):
    """Generate a JWT access token using basic auth credentials."""
    settings = get_settings()

    if (
        credentials.username != settings.AUTH_USERNAME
        or credentials.password != settings.AUTH_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        {"sub": credentials.username},
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}
