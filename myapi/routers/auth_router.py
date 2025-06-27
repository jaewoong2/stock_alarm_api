from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from myapi.domain.signal.signal_schema import DefaultTickers
from myapi.utils.auth import create_access_token
from myapi.utils.config import get_settings
import os
import requests
from typing import Iterable, Dict, Optional

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


def download_ticker_logo(
    ticker: str,
    save_dir: str = "logos",
    overwrite: bool = False,
    timeout: int | float = 10,
) -> Optional[str]:
    """
    FMP 이미지 엔드포인트에서 주어진 티커의 로고 PNG를 내려받아 저장한다.

    Parameters
    ----------
    ticker : str
        주식 티커 (예: "AAPL", "MSFT").
    save_dir : str, default "logos"
        파일을 저장할 폴더. 없으면 자동 생성.
    overwrite : bool, default False
        이미 파일이 있으면 덮어쓸지 여부.
    timeout : int | float, default 10
        requests.get 타임아웃(초).

    Returns
    -------
    str | None
        성공 시 저장된 파일의 경로, 실패 시 None.
    """
    ticker = ticker.upper()
    url = f"https://financialmodelingprep.com/image-stock/{ticker}.png"
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"{ticker}.png")

    if os.path.exists(path) and not overwrite:
        print(f"[SKIP] {ticker}: already exists → {path}")
        return path  # 이미 파일이 있으면 그대로 반환

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as err:
        print(f"[FAIL] {ticker}: HTTP error → {err}")
        return None

    # FMP는 존재하지 않는 티커에 대해 1×1 pixel GIF를 반환하는 경우가 있으므로
    # 실제 이미지 크기가 100바이트 미만이면 실패로 간주
    if len(resp.content) < 100:
        print(f"[FAIL] {ticker}: no valid logo returned")
        return None

    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"[OK] {ticker}: saved → {path}")
    return path


def download_many(
    tickers: Iterable[str],
    save_dir: str = "logos",
    overwrite: bool = False,
    timeout: int | float = 10,
) -> Dict[str, Optional[str]]:
    """
    여러 개의 티커를 한 번에 다운로드.

    Returns
    -------
    dict
        {티커: 파일경로 또는 None}
    """
    return {
        t.upper(): download_ticker_logo(
            t, save_dir=save_dir, overwrite=overwrite, timeout=timeout
        )
        for t in tickers
    }


@router.get("/download_logo")
def download_logo(
    save_dir: str = "logos",
    overwrite: bool = False,
    timeout: int | float = 10,
):
    """
    특정 티커의 로고를 다운로드합니다.

    Parameters:
    - ticker: 주식 티커 (예: "AAPL", "MSFT").
    - save_dir: 저장할 디렉토리 (기본값: "logos").
    - overwrite: 이미 파일이 있으면 덮어쓸지 여부 (기본값: False).
    - timeout: 요청 타임아웃 (초, 기본값: 10).

    Returns:
    - 성공 시 저장된 파일의 경로, 실패 시 None.
    """
    return download_many(DefaultTickers, save_dir, overwrite, timeout)
