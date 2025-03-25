import base64
from os import system
import time
from urllib.parse import quote, urlencode
from venv import logger
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

from pydantic_core import Url
from regex import D
import requests
from myapi.domain.ai.const import generate_futures_prompt
from myapi.domain.futures.futures_schema import (
    FuturesBalance,
    FuturesBalancePositionInfo,
    FuturesBalances,
    FuturesConfigRequest,
    FuturesOrderRequest,
    FuturesResponse,
    FuturesVO,
    PlaceFuturesOrder,
    PlaceFuturesOrderResponse,
    TechnicalAnalysis,
    PivotPoints,
    BollingerBands,
    MACDResult,
    Ticker,
    FutureOpenAISuggestion,
)
from myapi.domain.trading.trading_model import Trade
from myapi.domain.trading.trading_schema import TechnicalIndicators
from typing import Dict, List, Optional
import logging
from openai import OpenAI

from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.backdata_service import BackDataService
from myapi.utils.config import Settings
from myapi.utils.indicators import get_technical_indicators

logger = logging.getLogger(__name__)


# Function to encode the image url From web
def encode_image(image_url: str):
    return base64.b64encode(requests.get(image_url).content).decode("utf-8")


def calculate_pivot_points(df: pd.DataFrame) -> PivotPoints:
    last_candle = df.iloc[-1]
    pivot = (last_candle["high"] + last_candle["low"] + last_candle["close"]) / 3
    support1 = 2 * pivot - last_candle["high"]
    resistance1 = 2 * pivot - last_candle["low"]
    support2 = pivot - (last_candle["high"] - last_candle["low"])
    resistance2 = pivot + (last_candle["high"] - last_candle["low"])
    return PivotPoints(
        pivot=pivot,
        support1=support1,
        resistance1=resistance1,
        support2=support2,
        resistance2=resistance2,
    )


def calculate_bollinger_bands(
    df: pd.DataFrame, window: int = 20, num_std: int = 2
) -> BollingerBands:
    rolling_mean = df["close"].rolling(window=window).mean()
    rolling_std = df["close"].rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return BollingerBands(
        middle_band=rolling_mean.iloc[-1],
        upper_band=upper_band.iloc[-1],
        lower_band=lower_band.iloc[-1],
    )


def calculate_macd(df: pd.DataFrame) -> MACDResult:
    exp12 = df["close"].ewm(span=12, adjust=False).mean()
    exp26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal

    # .iat를 사용해 스칼라 값 추출
    prev_macd = macd.iat[-2]
    prev_signal = signal.iat[-2]
    last_macd = macd.iat[-1]
    last_signal = signal.iat[-1]

    crossover = prev_macd < prev_signal and last_macd > last_signal
    crossunder = prev_macd > prev_signal and last_macd < last_signal

    return MACDResult(
        macd=last_macd,
        signal=last_signal,
        histogram=histogram.iat[-1],
        crossover=crossover,
        crossunder=crossunder,
    )


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff().to_numpy()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.zeros(len(df))
    avg_loss = np.zeros(len(df))
    for i in range(period, len(df)):
        avg_gain[i] = np.mean(gain[i - period : i])
        avg_loss[i] = np.mean(loss[i - period : i])
    rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
    rsi = 100 - (100 / (1 + np.nan_to_num(rs)))
    return pd.Series(rsi, index=df.index)


def detect_divergence_advanced(
    df: pd.DataFrame, indicator: pd.Series, lookback: int = 5
) -> bool:
    recent_prices = df["close"].iloc[-lookback:]
    recent_indicator = indicator.iloc[-lookback:]
    price_high = recent_prices.max()
    price_low = recent_prices.min()
    indicator_high = recent_indicator.max()
    indicator_low = recent_indicator.min()
    current_price = df["close"].iloc[-1]
    current_indicator = indicator.iloc[-1]
    return (current_price >= price_high and current_indicator < indicator_high) or (
        current_price <= price_low and current_indicator > indicator_low
    )


def calculate_fibonacci(df: pd.DataFrame) -> Dict[str, float]:
    high = df["high"].max()
    low = df["low"].min()
    diff = high - low
    return {
        "0.0%": high,
        "23.6%": high - (diff * 0.236),
        "38.2%": high - (diff * 0.382),
        "50.0%": high - (diff * 0.5),
        "61.8%": high - (diff * 0.618),
        "100.0%": low,
    }


def analyze_volume(df: pd.DataFrame) -> str:
    volume_trend = df["volume"].diff().mean()
    price_trend = df["close"].diff().mean()
    if volume_trend > 0 and price_trend > 0:
        return "strong"
    elif volume_trend < 0 and price_trend > 0:
        return "weak"
    else:
        return "neutral"


def create_analysis_prompt(
    symbol: str,
    timeframe: str,
    analysis: TechnicalAnalysis,
    indicators: TechnicalIndicators,
    current_price: float,
) -> str:
    prompt = f"""
        You are a seasoned financial analyst with expertise in technical trading indicators. I will provide you with a set of technical analysis results for a stock or cryptocurrency (symbol: {symbol}, timeframe: {timeframe}). Your task is to analyze the indicators and recommend a trading action: "buy," "sell," or "hold." Explain your reasoning step-by-step, considering the following indicators: pivot points, Bollinger Bands, Fibonacci levels, MACD (including divergence and crossovers), RSI (including divergence), and volume trend. If the data is insufficient or ambiguous, state that clearly.

        Here’s the data:
        - Pivot: {analysis.pivot}
        - Support1: {analysis.support}, Support2: {analysis.support2}
        - Resistance1: {analysis.resistance}, Resistance2: {analysis.resistance2}
        - Bollinger Bands: Middle={analysis.bollinger_bands.middle_band}, Upper={analysis.bollinger_bands.upper_band}, Lower={analysis.bollinger_bands.lower_band}
        - Fibonacci Levels: {analysis.fibonacci_levels}
        - MACD: Crossover={analysis.macd_crossover}, Crossunder={analysis.macd_crossunder}, Divergence={analysis.macd_divergence}
        - RSI: Divergence={analysis.rsi_divergence}
        - Volume Trend: {analysis.volume_trend}
        - Current Price: {current_price}
        - Technical Indicators:{indicators.description}

        Please provide your recommendation and explain how each indicator contributes to your decision.
    """
    return prompt.strip()


class FuturesService:
    def __init__(
        self,
        settings: Settings,
        futures_repository: FuturesRepository,
        backdata_service: BackDataService,
    ):
        self.exchange = ccxt.binance(
            config={
                "apiKey": settings.BINANCE_FUTURES_API_KEY,
                "secret": settings.BINANCE_FUTURES_API_SECRET,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.futures_repository = futures_repository
        self.backdata_service = backdata_service

    def get_position(self, symbol: str):
        _symbol = symbol
        if not _symbol.endswith("USDT"):
            _symbol += "USDT"

        positions = self.exchange.fapiPrivateV2GetPositionRisk({"symbol": _symbol})

        if positions and len(positions) > 0:
            current_leverage = int(positions[0].get("leverage", 0))
            current_margin_type = positions[0].get("marginType", "").upper()
            # LONG, SHORT
            return current_leverage, current_margin_type

        return None, None

    def set_position(self, trade_config_data: FuturesConfigRequest):
        current_leverage, current_margin_type = self.get_position(
            trade_config_data.symbol
        )

        if current_leverage is None or current_margin_type is None:
            self.exchange.fapiprivate_post_leverage(
                {
                    "symbol": trade_config_data.symbol,
                    "leverage": trade_config_data.leverage,
                }
            )
            self.exchange.fapiprivate_post_margintype(
                {
                    "symbol": trade_config_data.symbol,
                    "marginType": trade_config_data.margin_type,
                }
            )

            return "Trade config set successfully."

        # 첫 번째 포지션 정보 사용 (일반적으로 단일 symbol 조회시 첫 번째 결과가 해당 심볼의 정보)
        result = ""

        # 레버리지 비교 및 설정
        if current_leverage != trade_config_data.leverage:
            self.exchange.fapiprivate_post_leverage(
                {
                    "symbol": trade_config_data.symbol,
                    "leverage": trade_config_data.leverage,
                }
            )
            result += f"Leverage updated to {trade_config_data.leverage}x. "

        # 마진 타입 비교 및 설정
        requested_margin_type = trade_config_data.margin_type.upper()
        if current_margin_type != requested_margin_type:
            self.exchange.fapiprivate_post_margintype(
                {
                    "symbol": trade_config_data.symbol,
                    "marginType": trade_config_data.margin_type,
                }
            )
            result += f"Margin type updated to {requested_margin_type}. "

        return result if result else "Current config is up to date."

    def fetch_balnce(self, is_future: bool = True, symbols: List[str] = ["USDT"]):
        params = {}
        result = {
            "positions": {},
            "balances": None,
        }

        if is_future:
            params["type"] = "future"

        balances = self.exchange.fetch_balance(params)

        # for position in balances["info"].get("positions", []):
        #     if position["symbol"] in symbols:
        #         posi = self.get_positions(position["symbol"])
        #         result["positions"][position["symbol"]] = posi

        result["balances"] = {
            symbol: balances[symbol] for symbol in balances if symbol in symbols
        }

        result["positions"] = {
            symbol: self.get_positions(symbol + "USDT")
            for symbol in balances
            if (symbol in symbols) and (symbol != "USDT")
        }

        return FuturesBalances(
            balances=[
                FuturesBalance(
                    symbol=symbol,
                    free=float(result["balances"][symbol]["free"] or 0),
                    used=float(result["balances"][symbol]["used"] or 0),
                    total=float(result["balances"][symbol]["total"] or 0),
                    positions=(
                        result["positions"][symbol]
                        if symbol in result["positions"]
                        else None
                    ),
                )
                for symbol in result["balances"]
            ]
        )

    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def fetch_ticker(self, symbol: str) -> Ticker:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            last_price = ticker.get("last")

            bid = ticker.get("bid")
            ask = ticker.get("ask")
            high = ticker.get("high")
            low = ticker.get("low")
            open_ = ticker.get("open")
            close_ = ticker.get("close")

            if last_price is None:
                raise ValueError(f"Ticker 'last' price is None for {symbol}")

            return Ticker(
                last=float(last_price),  # None 체크 후 변환
                bid=float(bid) if isinstance(bid, (float, int)) else None,
                ask=float(ask) if isinstance(ask, (float, int)) else None,
                high=float(high) if isinstance(high, (float, int)) else None,
                low=float(low) if isinstance(low, (float, int)) else None,
                open=float(open_) if isinstance(open_, (float, int)) else None,
                close=float(close_) if isinstance(close_, (float, int)) else None,
            )

        except Exception as e:
            logging.error(f"fetch_ticker error: {e}")
            raise

    def get_current_futures_pirce(self, symbol: str):
        return self.exchange.fetch_ticker(symbol)

    def get_market(self, symbol: str):
        markets = self.exchange.load_markets(False, {"type": "future"})
        market = markets[symbol + "/USDT"]
        filters = market["info"]["filters"]

        min_notional = float(
            [f for f in filters if f["filterType"] == "NOTIONAL"][0]["minNotional"]
        )
        lot_size = float(
            [f for f in filters if f["filterType"] == "LOT_SIZE"][0]["minQty"]
        )

        return min_notional, lot_size

    def analyze_with_openai(
        self, symbol: str, timeframe="1h", limit=500, target_currency="BTC"
    ) -> FutureOpenAISuggestion:
        current_leverage, _ = self.get_position(symbol)
        candles_info = self.fetch_ohlcv(symbol, timeframe, limit)
        analysis = self.perform_technical_analysis(df=candles_info)

        technical_indicators, _ = get_technical_indicators(
            df=candles_info, length=limit, reverse=False
        )
        current_time = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

        plot_image_path = self.backdata_service.upload_plot_image(
            df=candles_info, length=500, path=f"{symbol}_{current_time}.png"
        )
        encoded_image_url = encode_image(quote(plot_image_path, safe=":/"))

        currnt_price = self.fetch_ticker(symbol)
        balances = self.fetch_balnce(is_future=True, symbols=[target_currency, "USDT"])
        target_balance = [
            balance
            for balance in balances.balances
            if balance.symbol == target_currency
        ]

        balance = target_balance[0] if len(target_balance) > 0 else None

        min_notional, min_amount = self.get_market(symbol=target_currency)

        prompt, system_prompt = generate_futures_prompt(
            balances_data=(
                balances.model_dump_json()
                if isinstance(balances, FuturesBalances)
                else ""
            ),
            technical_analysis=analysis.model_dump(),
            interval=timeframe,
            market_data=currnt_price.model_dump(),
            technical_indicators=technical_indicators.model_dump(),
            additional_context=f"",
            target_currency=target_currency,
            position=balance.model_dump_json() if balance else "None",
            leverage=current_leverage or 0,
            quote_currency="USDT",
            minimum_usdt=min_notional,
            minimum_amount=min_amount,
        )

        logger.info(f"Prompt: {prompt}")

        try:
            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image_url}",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    },
                ],
                frequency_penalty=0.0,  # 반복 억제 정도
                presence_penalty=0.0,  # 새로운 주제 도입 억제
                response_format=FutureOpenAISuggestion,
            )

            content = response.choices[0].message.parsed

            if content is None:
                raise ValueError("OpenAI response content is None")

            return content
        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            raise ValueError("Invalid OpenAI response") from e

    def fetch_active_orders(self, symbol: str):
        return self.exchange.fetch_open_orders(symbol)

    def cancel_all_orders(self, symbol: str = "BTCUSDT"):
        active_orders_api = self.fetch_active_orders(symbol)
        active_orders_db = self.futures_repository.get_all_futures(symbol=symbol)

        order_ids = [order.order_id for order in active_orders_db]

        for order in active_orders_api:
            if order["id"] in order_ids:
                self.futures_repository.update_futures_status(
                    order_id=order["id"], status="canceled"
                )
                self.exchange.cancel_order(order["id"].upper(), symbol)

    def execute_futures_with_suggestion(
        self, symbol: str, target_currency="BTC", limit=500, timeframe="1h"
    ):

        suggestion = self.analyze_with_openai(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            target_currency=target_currency,
        )

        logger.info(f"Received suggestion: {suggestion.model_dump_json()}")

        decision = suggestion.action.upper()
        tp, sl = suggestion.order.tp_price, suggestion.order.sl_price
        ticker = self.fetch_ticker(symbol)
        current_price = ticker.last

        balances = self.fetch_balnce(is_future=True, symbols=[target_currency, "USDT"])
        target_balance_ = [
            balance
            for balance in balances.balances
            if balance.symbol == target_currency
        ]

        target_balance = target_balance_[0] if len(target_balance_) > 0 else None

        if decision == "CANCLE":
            return self.cancel_all_orders(symbol)

        if decision == "BUY":
            if (
                target_balance
                and target_balance.positions
                and target_balance.positions.position == "SHORT"
            ):
                self.exchange.create_limit_buy_order(
                    symbol,
                    float(target_balance.used) or 0.0,
                    suggestion.order.price,
                    params={"reduceOnly": True},
                )
                logging.info(
                    f"Closed short position for {symbol} at {suggestion.order.price}"
                )

            # 신규 long 포지션 생성
            logging.info(f"Set TP {tp} and SL {sl} for long position on {symbol}")
            orders = self.place_long_order(suggestion.order)
            if orders.buy_order:
                future = self.order_to_futures(
                    order=orders.buy_order, parent_order_id=""
                )
                self.futures_repository.create_futures(
                    futures=future, position_type="LONG"
                )

            if orders.tp_order and orders.buy_order:
                future = self.order_to_futures(
                    order=orders.tp_order, parent_order_id=orders.buy_order.order_id
                )
                self.futures_repository.create_futures(
                    futures=future,
                    position_type="TAKE_PROFIT",
                    take_profit=tp,
                    stop_loss=None,
                )

            if orders.sl_order and orders.buy_order:
                future = self.order_to_futures(
                    order=orders.sl_order, parent_order_id=orders.buy_order.order_id
                )
                self.futures_repository.create_futures(
                    futures=future,
                    position_type="STOP_LOSS",
                    take_profit=None,
                    stop_loss=sl,
                )

            return orders

        if decision == "SELL":
            if (
                target_balance
                and target_balance.positions
                and target_balance.positions.position == "LONG"
            ):
                # 기존 long 포지션 청산
                self.exchange.create_limit_buy_order(
                    symbol,
                    float(target_balance.used) or 0.0,
                    suggestion.order.price,
                    params={"reduceOnly": True},
                )
                logging.info(
                    f"Closed short position for {symbol} at {suggestion.order.price}"
                )

            # 신규 short 포지션 생성
            logging.info(f"Set TP {tp} and SL {sl} for short position on {symbol}")
            orders = self.place_short_order(suggestion.order)

            if orders.sell_order:
                future = self.order_to_futures(
                    order=orders.sell_order, parent_order_id=""
                )
                self.futures_repository.create_futures(
                    futures=future, position_type="SHORT"
                )

            if orders.tp_order and orders.sell_order:
                future = self.order_to_futures(
                    order=orders.tp_order, parent_order_id=orders.sell_order.order_id
                )
                self.futures_repository.create_futures(
                    futures=future,
                    position_type="TAKE_PROFIT",
                    take_profit=tp,
                    stop_loss=None,
                )

            if orders.sl_order and orders.sell_order:
                future = self.order_to_futures(
                    order=orders.sl_order, parent_order_id=orders.sell_order.order_id
                )
                self.futures_repository.create_futures(
                    futures=future,
                    position_type="STOP_LOSS",
                    take_profit=None,
                    stop_loss=sl,
                )

            return orders

        else:  # decision == "hold"
            return FuturesResponse(
                id=-1,
                symbol=symbol,
                price=current_price,
                quantity=0,
                side="hold",
                timestamp=datetime.now(),
                position_type=None,
                take_profit=None,
                stop_loss=None,
                status="open",
                order_id="",
                parent_order_id="",
            )

    def perform_technical_analysis(self, df: pd.DataFrame):
        pivots = calculate_pivot_points(df)
        bb = calculate_bollinger_bands(df)
        fib_levels = calculate_fibonacci(df)
        macd_data = calculate_macd(df)
        macd_series = pd.Series([macd_data.macd] * len(df), index=df.index)
        rsi = calculate_rsi(df)

        return TechnicalAnalysis(
            support=pivots.support1,
            resistance=pivots.resistance1,
            pivot=pivots.pivot,
            support2=pivots.support2,
            resistance2=pivots.resistance2,
            bollinger_bands=bb,
            fibonacci_levels=fib_levels,
            macd_divergence=detect_divergence_advanced(df, macd_series),
            macd_crossover=macd_data.crossover,
            macd_crossunder=macd_data.crossunder,
            rsi_divergence=detect_divergence_advanced(df, rsi),
            volume_trend=analyze_volume(df),
        )

    def place_long_order(self, order: FuturesOrderRequest):
        # self.set_position(
        #     FuturesConfigRequest(
        #         symbol=order.symbol,
        #         leverage=order.leverage,
        #         margin_type="ISOLATED",
        #     )
        # )

        if not order.symbol.endswith("USDT"):
            order.symbol += "USDT"

        buy_order = self.exchange.create_order(
            symbol=order.symbol,
            type="limit",
            side="buy",
            amount=order.quantity,
            price=order.price,
        )

        tp_order = self.exchange.create_order(
            symbol=order.symbol,
            type="TAKE_PROFIT_MARKET",  # type: ignore
            side="sell",
            amount=order.quantity,
            price=None,
            params={"stopPrice": order.tp_price, "reduceOnly": True},
        )

        sl_order = self.exchange.create_order(
            symbol=order.symbol,
            type="STOP_MARKET",  # type: ignore
            side="sell",
            amount=order.quantity,
            price=None,
            params={"stopPrice": order.sl_price, "reduceOnly": True},
        )

        return PlaceFuturesOrderResponse(
            sell_order=None,
            buy_order=PlaceFuturesOrder(
                id=buy_order["id"] if buy_order["id"] else "",
                order_id=buy_order["info"]["orderId"],
                symbol=buy_order["info"]["symbol"],
                origQty=buy_order["info"]["origQty"],
                avgPrice=buy_order["info"]["avgPrice"],
                cumQuote=buy_order["info"]["cumQuote"],
                clientOrderId=buy_order["info"]["clientOrderId"],
                side=buy_order["info"]["side"],
                triggerPrice=None,
                stopPrice=None,
            ),
            tp_order=PlaceFuturesOrder(
                id=tp_order["id"] if tp_order["id"] else "",
                order_id=tp_order["info"]["orderId"],
                symbol=tp_order["info"]["symbol"],
                origQty=tp_order["info"]["origQty"],
                avgPrice=tp_order["info"]["avgPrice"],
                cumQuote=tp_order["info"]["cumQuote"],
                clientOrderId=tp_order["info"]["clientOrderId"],
                side=tp_order["info"]["side"],
                triggerPrice=tp_order["info"]["stopPrice"],
                stopPrice=tp_order["info"]["stopPrice"],
            ),
            sl_order=PlaceFuturesOrder(
                id=sl_order["id"] if sl_order["id"] else "",
                order_id=sl_order["info"]["orderId"],
                symbol=sl_order["info"]["symbol"],
                origQty=sl_order["info"]["origQty"],
                avgPrice=sl_order["info"]["avgPrice"],
                cumQuote=sl_order["info"]["cumQuote"],
                clientOrderId=sl_order["info"]["clientOrderId"],
                side=sl_order["info"]["side"],
                triggerPrice=sl_order["info"]["stopPrice"],
                stopPrice=sl_order["info"]["stopPrice"],
            ),
        )

    def place_short_order(self, order: FuturesOrderRequest):
        # self.set_position(
        #     FuturesConfigRequest(
        #         symbol=order.symbol,
        #         leverage=order.leverage,
        #         margin_type="ISOLATED",
        #     )
        # )

        if not order.symbol.endswith("USDT"):
            order.symbol += "USDT"

        sell_order = self.exchange.create_order(
            symbol=order.symbol,
            type="limit",
            side="sell",
            amount=order.quantity,
            price=order.price,
        )

        tp_order = self.exchange.create_order(
            symbol=order.symbol,
            type="TAKE_PROFIT_MARKET",  # type: ignore
            side="buy",
            amount=order.quantity,
            price=None,
            params={"stopPrice": order.tp_price, "reduceOnly": True},
        )

        sl_order = self.exchange.create_order(
            symbol=order.symbol,
            type="STOP_MARKET",  # type: ignore
            side="buy",
            amount=order.quantity,
            price=None,
            params={"stopPrice": order.sl_price, "reduceOnly": True},
        )

        return PlaceFuturesOrderResponse(
            buy_order=None,
            sell_order=PlaceFuturesOrder(
                id=sell_order["id"] if sell_order["id"] else "",
                order_id=sell_order["info"]["orderId"],
                symbol=sell_order["info"]["symbol"],
                origQty=sell_order["info"]["origQty"],
                avgPrice=sell_order["info"]["avgPrice"],
                cumQuote=sell_order["info"]["cumQuote"],
                clientOrderId=sell_order["info"]["clientOrderId"],
                side=sell_order["info"]["side"],
                triggerPrice=None,
                stopPrice=None,
            ),
            tp_order=PlaceFuturesOrder(
                id=tp_order["id"] if tp_order["id"] else "",
                order_id=tp_order["info"]["orderId"],
                symbol=tp_order["info"]["symbol"],
                origQty=tp_order["info"]["origQty"],
                avgPrice=tp_order["info"]["avgPrice"],
                cumQuote=tp_order["info"]["cumQuote"],
                clientOrderId=tp_order["info"]["clientOrderId"],
                side=tp_order["info"]["side"],
                triggerPrice=tp_order["info"]["stopPrice"],
                stopPrice=tp_order["info"]["stopPrice"],
            ),
            sl_order=PlaceFuturesOrder(
                id=sl_order["id"] if sl_order["id"] else "",
                order_id=sl_order["info"]["orderId"],
                symbol=sl_order["info"]["symbol"],
                origQty=sl_order["info"]["origQty"],
                avgPrice=sl_order["info"]["avgPrice"],
                cumQuote=sl_order["info"]["cumQuote"],
                clientOrderId=sl_order["info"]["clientOrderId"],
                side=sl_order["info"]["side"],
                triggerPrice=sl_order["info"]["stopPrice"],
                stopPrice=sl_order["info"]["stopPrice"],
            ),
        )

    def cancel_order(self, order_id: str):
        order = self.exchange.cancel_order(order_id)
        return order

    def get_positions(self, symbol: str):
        positons = self.exchange.fetch_positions([symbol])

        if not positons or len(positons) == 0:
            return FuturesBalancePositionInfo(
                position="NONE",
                position_amt=0,
                entry_price=0,
                leverage=None,
                unrealized_profit=0,
            )
        return FuturesBalancePositionInfo(
            position=positons[0]["side"].upper(),
            position_amt=positons[0]["info"]["positionAmt"],
            entry_price=positons[0]["entryPrice"],
            leverage=positons[0]["leverage"] or None,
            unrealized_profit=positons[0]["unrealizedPnl"],
        )

    def close_long_position(self, symbol: str, quantity: Optional[float] = None):
        positions = self.exchange.fetch_positions([symbol])
        for pos in positions:
            if pos["symbol"] == symbol and pos["positionAmt"] > 0:
                pos_size = pos["positionAmt"]
                if quantity is None:
                    quantity = pos_size
                else:
                    quantity = min(quantity, pos_size)
                break
        else:
            raise ValueError("No long position found for symbol")
        order = self.exchange.create_order(
            symbol, "market", "sell", quantity or 0.0, None, {"reduceOnly": True}
        )
        return order

    def close_short_position(self, symbol: str, quantity: Optional[float] = None):
        positions = self.exchange.fetch_positions([symbol])
        for pos in positions:
            if pos["symbol"] == symbol and pos["positionAmt"] < 0:
                pos_size = -pos["positionAmt"]
                if quantity is None:
                    quantity = pos_size
                else:
                    quantity = min(quantity, pos_size)
                break
        else:
            raise ValueError("No short position found for symbol")
        order = self.exchange.create_order(
            symbol, "market", "buy", quantity or 0.0, None, {"reduceOnly": True}
        )
        return order

    def order_to_futures(
        self, order: PlaceFuturesOrder, parent_order_id: str, side: str = "TAKE_PROFIT"
    ):
        return FuturesVO(
            id=None,
            timestamp=datetime.now(),
            status="open",
            symbol=order.symbol,
            price=order.avgPrice if order.avgPrice else 0.0,
            quantity=order.origQty,
            side=order.side,
            position_type=side,
            take_profit=order.triggerPrice if order.triggerPrice else 0.0,
            stop_loss=order.stopPrice if order.stopPrice else 0.0,
            order_id=order.order_id,
            parent_order_id=parent_order_id,
        )
