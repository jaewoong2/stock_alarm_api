from fastapi import APIRouter, Depends, HTTPException
from myapi.domain.trading.coinone_schema import (
    CandlestickResponse,
    MarketResponse,
    OrderBookResponse,
    OrderRequest,
    TickerResponse,
    TradesResponse,
)
from myapi.services.coinone_service import CoinoneService
from myapi.containers import Container
from dependency_injector.wiring import inject, Provide

router = APIRouter(prefix="/trading")


@router.get(
    "/candlestick/{quote_currency}/{target_currency}",
    response_model=CandlestickResponse,
)
@inject
def candlestick_endpoint(
    quote_currency: str,
    target_currency: str,
    interval: str = "5m",
    limit: int = 72,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_candlestick(
            quote_currency, target_currency, interval, limit
        )
        # 실제 API 응답 구조에 맞춰 필드 이름을 변환해야 할 수 있음.
        # 여기서는 "candles" 필드에 캔들 데이터가 있다고 가정.
        return CandlestickResponse(
            result=data.get("result", "error"),
            error_code=data.get("error_code", ""),
            server_time=data.get("server_time", 0),
            candles=data.get("candles", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker_all/{quote_currency}", response_model=TickerResponse)
@inject
def ticker_all_endpoint(
    quote_currency: str,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_ticker_all(quote_currency)
        return TickerResponse(
            result=data.get("result", "error"),
            error_code=data.get("error_code", ""),
            server_time=data.get("server_time", 0),
            tickers={
                k: v
                for k, v in data.items()
                if k not in ["result", "error_code", "server_time"]
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/orderbook/{quote_currency}/{target_currency}", response_model=OrderBookResponse
)
@inject
def orderbook_endpoint(
    quote_currency: str,
    target_currency: str,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_orderbook(quote_currency, target_currency)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{quote_currency}/{target_currency}", response_model=TradesResponse)
@inject
def trades_endpoint(
    quote_currency: str,
    target_currency: str,
    size: int = 200,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_trades(quote_currency, target_currency, size)
        return TradesResponse(
            result=data.get("result", "error"),
            error_code=data.get("error_code", ""),
            server_time=data.get("server_time", 0),
            quote_currency=data.get("quote_currency", quote_currency),
            target_currency=data.get("target_currency", target_currency),
            transactions=data.get("transactions", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/markets/{quote_currency}/{target_currency}", response_model=MarketResponse
)
@inject
def markets_endpoint(
    quote_currency: str = "KRW",
    target_currency: str = "BTC",
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_markets(quote_currency, target_currency)
        return MarketResponse(
            result=data.get("result", "error"),
            error_code=data.get("error_code", ""),
            server_time=data.get("server_time", 0),
            markets=data.get("markets", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balances")
@inject
def balances_endpoint(
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_balance(["BTC", "KRW"])

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order")
@inject
def order(
    order: OrderRequest,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.place_order(order)

        return data["balances"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/active_orders")
@inject
def active_orders(
    symbol: str,
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.get_active_orders(symbol.upper())

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancle_order")
@inject
def cancle_order(
    order_id: str,
    symbol: str = "BTC",
    coinone_service: CoinoneService = Depends(Provide[Container.coinone_service]),
):
    try:
        data = coinone_service.cancel_order(
            order_id=order_id, target_currency=symbol.upper()
        )

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
