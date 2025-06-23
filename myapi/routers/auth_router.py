from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from myapi.utils.auth import create_access_token
from myapi.utils.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBasic()


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
