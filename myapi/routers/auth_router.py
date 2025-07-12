from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import yfinance

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


def get_ticker_logo_yahoo(ticker: str):
    """Yahoo Finance에서 로고 URL 가져오기"""
    try:
        stock = yfinance.Ticker(ticker)
        info = stock.info
        return info.get("logo_url", None)
    except Exception as e:
        print(f"[ERROR] {ticker}: Yahoo Finance API error → {e}")
        return None


def download_ticker_logo_yahoo(
    ticker: str,
    save_dir: str = "logos_yahoo",
    overwrite: bool = False,
    timeout: int | float = 10,
) -> Optional[str]:
    """
    Yahoo Finance API에서 주어진 티커의 로고를 다운로드하여 저장한다.

    Parameters
    ----------
    ticker : str
        주식 티커 (예: "AAPL", "MSFT").
    save_dir : str, default "logos_yahoo"
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
    logo_url = get_ticker_logo_yahoo(ticker)

    if not logo_url:
        print(f"[FAIL] {ticker}: no logo URL found in Yahoo Finance")
        return None

    os.makedirs(save_dir, exist_ok=True)

    # URL에서 파일 확장자 추출, 없으면 기본값으로 png 사용
    file_extension = logo_url.split(".")[-1].split("?")[0] if "." in logo_url else "png"
    if file_extension not in ["png", "jpg", "jpeg", "gif", "svg"]:
        file_extension = "png"

    path = os.path.join(save_dir, f"{ticker}.{file_extension}")

    if os.path.exists(path) and not overwrite:
        print(f"[SKIP] {ticker}: already exists → {path}")
        return path

    try:
        resp = requests.get(logo_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as err:
        print(f"[FAIL] {ticker}: HTTP error → {err}")
        return None

    # 이미지 크기 체크
    if len(resp.content) < 100:
        print(f"[FAIL] {ticker}: no valid logo returned")
        return None

    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"[OK] {ticker}: saved → {path}")
    return path


def download_many_yahoo(
    tickers: Iterable[str],
    save_dir: str = "logos_yahoo",
    overwrite: bool = False,
    timeout: int | float = 10,
) -> Dict[str, Optional[str]]:
    """
    Yahoo Finance API를 사용하여 여러 개의 티커 로고를 한 번에 다운로드.

    Returns
    -------
    dict
        {티커: 파일경로 또는 None}
    """
    return {
        t.upper(): download_ticker_logo_yahoo(
            t, save_dir=save_dir, overwrite=overwrite, timeout=timeout
        )
        for t in tickers
    }


@router.get("/download_logo_yahoo")
def download_logo_yahoo(
    save_dir: str = "logos_yahoo",
    overwrite: bool = False,
    timeout: int | float = 10,
):
    """
    Yahoo Finance API를 사용하여 DefaultTickers의 로고를 다운로드합니다.

    Parameters:
    - save_dir: 저장할 디렉토리 (기본값: "logos_yahoo").
    - overwrite: 이미 파일이 있으면 덮어쓸지 여부 (기본값: False).
    - timeout: 요청 타임아웃 (초, 기본값: 10).

    Returns:
    - 성공한 티커들의 파일 경로 딕셔너리
    """
    result = download_many_yahoo(DefaultTickers, save_dir, overwrite, timeout)
    successful_downloads = {k: v for k, v in result.items() if v is not None}
    failed_downloads = [k for k, v in result.items() if v is None]

    return {
        "successful_downloads": successful_downloads,
        "failed_downloads": failed_downloads,
        "total_attempted": len(result),
        "successful_count": len(successful_downloads),
        "failed_count": len(failed_downloads),
    }


@router.get("/download_single_logo_yahoo/{ticker}")
def download_single_logo_yahoo(
    ticker: str,
    save_dir: str = "logos_yahoo",
    overwrite: bool = False,
    timeout: int | float = 10,
):
    """
    Yahoo Finance API를 사용하여 특정 티커의 로고를 다운로드합니다.

    Parameters:
    - ticker: 주식 티커 (예: "AAPL", "MSFT").
    - save_dir: 저장할 디렉토리 (기본값: "logos_yahoo").
    - overwrite: 이미 파일이 있으면 덮어쓸지 여부 (기본값: False).
    - timeout: 요청 타임아웃 (초, 기본값: 10).

    Returns:
    - 성공 시 저장된 파일의 경로, 실패 시 에러 메시지
    """
    result_path = download_ticker_logo_yahoo(ticker, save_dir, overwrite, timeout)

    if result_path:
        return {
            "success": True,
            "ticker": ticker.upper(),
            "file_path": result_path,
            "message": f"Successfully downloaded logo for {ticker.upper()}",
        }
    else:
        return {
            "success": False,
            "ticker": ticker.upper(),
            "file_path": None,
            "message": f"Failed to download logo for {ticker.upper()}",
        }


def get_ticker_logo_alpha_vantage(ticker: str, api_key: str = ""):
    """Alpha Vantage API에서 회사 정보 및 로고 URL 가져오기"""
    if not api_key:
        # 환경변수에서 API 키 가져오기 (없으면 데모 키 사용)
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "demo")

    try:
        url = f"https://www.alphavantage.co/query"
        params = {"function": "OVERVIEW", "symbol": ticker, "apikey": api_key}

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Alpha Vantage는 직접 로고 URL을 제공하지 않으므로
        # 회사명을 이용해 다른 소스에서 로고를 찾는 방법 사용
        company_name = data.get("Name", "")
        if company_name:
            # Logo.dev API 사용 (무료)
            logo_url = f"https://img.logo.dev/{ticker.lower()}.com?token=pk_X-1ZO13GSgeOoUrIuJ6GMQ"
            return logo_url

        return None
    except Exception as e:
        print(f"[ERROR] {ticker}: Alpha Vantage API error → {e}")
        return None


def get_ticker_logo_polygon(ticker: str, api_key: str = ""):
    """Polygon.io API에서 로고 URL 가져오기"""
    if not api_key:
        # 환경변수에서 API 키 가져오기
        api_key = os.environ.get("POLYGON_API_KEY", "")
        if not api_key:
            print(f"[ERROR] {ticker}: Polygon API key not found")
            return None

    try:
        url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
        params = {"apikey": api_key}

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Polygon.io에서 로고 URL 추출
        results = data.get("results", {})
        branding = results.get("branding", {})
        logo_url = branding.get("logo_url")

        return logo_url
    except Exception as e:
        print(f"[ERROR] {ticker}: Polygon API error → {e}")
        return None


def get_ticker_logo_clearbit(ticker: str):
    """Clearbit Logo API를 사용하여 로고 URL 가져오기 (무료)"""
    try:
        # 대부분의 주요 기업들은 ticker.com 형태의 도메인을 가지고 있음
        logo_url = f"https://logo.clearbit.com/{ticker.lower()}.com"

        # URL이 유효한지 확인
        response = requests.head(logo_url, timeout=5)
        if response.status_code == 200:
            return logo_url
        else:
            # 실패 시 다른 형태 시도
            alternative_domains = [
                f"{ticker.lower()}.com",
                f"{ticker.lower()}inc.com",
                f"{ticker.lower()}corp.com",
            ]

            for domain in alternative_domains:
                alt_url = f"https://logo.clearbit.com/{domain}"
                alt_response = requests.head(alt_url, timeout=5)
                if alt_response.status_code == 200:
                    return alt_url

        return None
    except Exception as e:
        print(f"[ERROR] {ticker}: Clearbit API error → {e}")
        return None


def download_ticker_logo_alternative(
    ticker: str,
    save_dir: str = "logos_alternative",
    overwrite: bool = False,
    timeout: int | float = 10,
    api_source: str = "clearbit",
) -> Optional[str]:
    """
    다양한 API를 사용하여 주어진 티커의 로고를 다운로드하여 저장한다.

    Parameters
    ----------
    ticker : str
        주식 티커 (예: "AAPL", "MSFT").
    save_dir : str, default "logos_alternative"
        파일을 저장할 폴더. 없으면 자동 생성.
    overwrite : bool, default False
        이미 파일이 있으면 덮어쓸지 여부.
    timeout : int | float, default 10
        requests.get 타임아웃(초).
    api_source : str, default "clearbit"
        사용할 API ("clearbit", "polygon", "alpha_vantage").

    Returns
    -------
    str | None
        성공 시 저장된 파일의 경로, 실패 시 None.
    """
    ticker = ticker.upper()

    # API에 따라 로고 URL 가져오기
    if api_source == "clearbit":
        logo_url = get_ticker_logo_clearbit(ticker)
    elif api_source == "polygon":
        logo_url = get_ticker_logo_polygon(ticker)
    elif api_source == "alpha_vantage":
        logo_url = get_ticker_logo_alpha_vantage(ticker)
    else:
        print(f"[ERROR] {ticker}: Unknown API source '{api_source}'")
        return None

    if not logo_url:
        print(f"[FAIL] {ticker}: no logo URL found using {api_source}")
        return None

    os.makedirs(save_dir, exist_ok=True)

    # URL에서 파일 확장자 추출
    file_extension = logo_url.split(".")[-1].split("?")[0] if "." in logo_url else "png"
    if file_extension not in ["png", "jpg", "jpeg", "gif", "svg"]:
        file_extension = "png"

    path = os.path.join(save_dir, f"{ticker}.{file_extension}")

    if os.path.exists(path) and not overwrite:
        print(f"[SKIP] {ticker}: already exists → {path}")
        return path

    try:
        resp = requests.get(logo_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as err:
        print(f"[FAIL] {ticker}: HTTP error → {err}")
        return None

    # 이미지 크기 체크
    if len(resp.content) < 100:
        print(f"[FAIL] {ticker}: no valid logo returned")
        return None

    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"[OK] {ticker}: saved → {path}")
    return path


def download_many_alternative(
    tickers: Iterable[str],
    save_dir: str = "logos_alternative",
    overwrite: bool = False,
    timeout: int | float = 10,
    api_source: str = "clearbit",
) -> Dict[str, Optional[str]]:
    """
    다양한 API를 사용하여 여러 개의 티커 로고를 한 번에 다운로드.

    Returns
    -------
    dict
        {티커: 파일경로 또는 None}
    """
    return {
        t.upper(): download_ticker_logo_alternative(
            t,
            save_dir=save_dir,
            overwrite=overwrite,
            timeout=timeout,
            api_source=api_source,
        )
        for t in tickers
    }


@router.get("/download_logo_alternative")
def download_logo_alternative(
    save_dir: str = "logos_alternative",
    overwrite: bool = False,
    timeout: int | float = 10,
    api_source: str = "clearbit",
):
    """
    다양한 API를 사용하여 DefaultTickers의 로고를 다운로드합니다.

    Parameters:
    - save_dir: 저장할 디렉토리 (기본값: "logos_alternative").
    - overwrite: 이미 파일이 있으면 덮어쓸지 여부 (기본값: False).
    - timeout: 요청 타임아웃 (초, 기본값: 10).
    - api_source: 사용할 API ("clearbit", "polygon", "alpha_vantage").

    Returns:
    - 성공한 티커들의 파일 경로 딕셔너리
    """
    result = download_many_alternative(
        DefaultTickers, save_dir, overwrite, timeout, api_source
    )
    successful_downloads = {k: v for k, v in result.items() if v is not None}
    failed_downloads = [k for k, v in result.items() if v is None]

    return {
        "api_source": api_source,
        "successful_downloads": successful_downloads,
        "failed_downloads": failed_downloads,
        "total_attempted": len(result),
        "successful_count": len(successful_downloads),
        "failed_count": len(failed_downloads),
    }


@router.get("/download_single_logo_alternative/{ticker}")
def download_single_logo_alternative(
    ticker: str,
    save_dir: str = "logos_alternative",
    overwrite: bool = False,
    timeout: int | float = 10,
    api_source: str = "clearbit",
):
    """
    다양한 API를 사용하여 특정 티커의 로고를 다운로드합니다.

    Parameters:
    - ticker: 주식 티커 (예: "AAPL", "MSFT").
    - save_dir: 저장할 디렉토리 (기본값: "logos_alternative").
    - overwrite: 이미 파일이 있으면 덮어쓸지 여부 (기본값: False).
    - timeout: 요청 타임아웃 (초, 기본값: 10).
    - api_source: 사용할 API ("clearbit", "polygon", "alpha_vantage").

    Returns:
    - 성공 시 저장된 파일의 경로, 실패 시 에러 메시지
    """
    result_path = download_ticker_logo_alternative(
        ticker, save_dir, overwrite, timeout, api_source
    )

    if result_path:
        return {
            "success": True,
            "ticker": ticker.upper(),
            "file_path": result_path,
            "api_source": api_source,
            "message": f"Successfully downloaded logo for {ticker.upper()} using {api_source}",
        }
    else:
        return {
            "success": False,
            "ticker": ticker.upper(),
            "file_path": None,
            "api_source": api_source,
            "message": f"Failed to download logo for {ticker.upper()} using {api_source}",
        }
