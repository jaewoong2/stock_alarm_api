import base64
from urllib.parse import quote
from venv import logger
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

import requests
from myapi.domain.ai.const import generate_futures_prompt
from myapi.domain.futures.futures_schema import (
    FuturesActionType,
    FuturesBalance,
    FuturesBalancePositionInfo,
    FuturesBalances,
    FuturesConfigRequest,
    FuturesOrderRequest,
    FuturesVO,
    HeikinAshiAnalysis,
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

from myapi.exceptions.futures_exceptions import (
    ExchangeConnectionException,
    InvalidSuggestionException,
    OrderCancellationException,
    OrderCreationException,
    PositionCloseException,
)
from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.backdata_service import BackDataService
from myapi.utils.config import Settings
from myapi.utils.indicators import get_technical_indicators

logger = logging.getLogger(__name__)


def generate_prompt_for_image(interval: str, symbol: str, length: int) -> str:
    return f"""
        The image below is a {interval} candle chart of {symbol} (With {length} length).
        with MA (3, 21, 50), Bollinger Band (BB_500), RSI, MACD, and ADX shown.
        
        I'm looking for opportunities to enter the Long/Short position in the short term.
        Looking to maintain a risk-reward ratio of 1:2 or higher.

        Question:
            - Analyze the chart and provide a detailed analysis of the current market situation technically.
            - Based on current chart indicators, which position entry (long/short) looks favorable, and why?
            - To what extent is it reasonable to set up a line of hands and blades?
            - Please let me know what additional factors of market volatility should be noted.
        """


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
    rsi = 100 - (100 / (1 + np.nan_to_num(rs, nan=0.0)))
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


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    df에는 최소한 'open', 'high', 'low', 'close' 컬럼이 존재해야 함.
    하이킨 아시(Heikin Ashi) 캔들 정보를 계산한 뒤,
    HA_Open, HA_High, HA_Low, HA_Close 컬럼을 추가하여 반환합니다.
    """

    # 원본 df를 복사해서 사용(기존 df 보호)
    ha_df = df.copy()

    # 1) HA_Close 공식: (Open + High + Low + Close) / 4
    ha_df["HA_Close"] = (
        ha_df["open"] + ha_df["high"] + ha_df["low"] + ha_df["close"]
    ) / 4.0

    # 우선 모든 HA_Open을 0으로 초기화
    ha_df["HA_Open"] = 0.0

    # 첫 번째 캔들(0번 인덱스)의 HA_Open 초기값 설정
    # 일반적으로 (현재봉 open + 현재봉 close)/2 로 많이 사용
    ha_df["open"] = pd.to_numeric(ha_df["open"], errors="coerce")
    ha_df["close"] = pd.to_numeric(ha_df["close"], errors="coerce")

    ha_df.loc[ha_df.index[0], "HA_Open"] = (
        pd.to_numeric(ha_df.loc[ha_df.index[0], "open"], errors="coerce")
        + pd.to_numeric(ha_df.loc[ha_df.index[0], "close"], errors="coerce")
    ) / 2.0

    # 2) 이후 캔들부터는 HA_Open = (이전 HA_Open + 이전 HA_Close) / 2
    for i in range(1, len(ha_df)):
        ha_df.loc[ha_df.index[i], "HA_Open"] = (
            pd.to_numeric(ha_df.loc[ha_df.index[i - 1], "HA_Open"], errors="coerce")
            + pd.to_numeric(ha_df.loc[ha_df.index[i - 1], "HA_Close"], errors="coerce")
        ) / 2.0

    # 3) HA_High = max(일반봉 High, HA_Open, HA_Close)
    ha_df["HA_High"] = ha_df[["high", "HA_Open", "HA_Close"]].max(axis=1)

    # 4) HA_Low = min(일반봉 Low, HA_Open, HA_Close)
    ha_df["HA_Low"] = ha_df[["low", "HA_Open", "HA_Close"]].min(axis=1)

    return ha_df


def analyze_heikin_ashi_model(
    ha_df: pd.DataFrame, lookback: int = 5
) -> HeikinAshiAnalysis:
    """
    Analyze the last `lookback` Heikin Ashi candles and return the result as a Pydantic BaseModel (HeikinAshiAnalysis).
    Interpretation strings are provided in English.
    """
    # 1) Get the subset of recent candles
    recent_df = ha_df.iloc[-lookback:].copy()

    # 2) Determine bullish/bearish candles
    recent_df["is_bull"] = recent_df["HA_Close"] > recent_df["HA_Open"]
    recent_df["is_bear"] = recent_df["HA_Close"] < recent_df["HA_Open"]

    # 3) Identify Doji candles
    body_size = (recent_df["HA_Close"] - recent_df["HA_Open"]).abs()
    candle_range = recent_df["HA_High"] - recent_df["HA_Low"]
    # If the body is less than 10% of the entire candle range, consider it a Doji
    recent_df["doji"] = (candle_range > 0) & ((body_size / candle_range) < 0.1)

    # 4) Calculate upper/lower tails
    recent_df["upper_tail"] = recent_df["HA_High"] - recent_df[
        ["HA_Open", "HA_Close"]
    ].max(axis=1)
    recent_df["lower_tail"] = (
        recent_df[["HA_Open", "HA_Close"]].min(axis=1) - recent_df["HA_Low"]
    )

    # ===== Basic Statistics =====
    num_bull = int(recent_df["is_bull"].sum())
    num_bear = int(recent_df["is_bear"].sum())
    num_doji = int(recent_df["doji"].sum())

    # (a) Consecutive Bull/Bear
    consecutive_bull = 0
    consecutive_bear = 0

    # Count consecutive bullish candles from the most recent
    for i in reversed(range(len(recent_df))):
        if recent_df["is_bull"].iloc[i]:
            consecutive_bull += 1
            # Stop if we see a bear candle just before
            if i < len(recent_df) - 1 and recent_df["is_bear"].iloc[i + 1]:
                break
        else:
            break

    # Count consecutive bearish candles
    for i in reversed(range(len(recent_df))):
        if recent_df["is_bear"].iloc[i]:
            consecutive_bear += 1
            if i < len(recent_df) - 1 and recent_df["is_bull"].iloc[i + 1]:
                break
        else:
            break

    # (b) Average upper/lower tail lengths
    avg_upper_tail = recent_df["upper_tail"].mean() if len(recent_df) > 0 else 0.0
    avg_lower_tail = recent_df["lower_tail"].mean() if len(recent_df) > 0 else 0.0

    # (c) Simple interpretation in English
    interpretation = None
    if consecutive_bull > 2 and avg_lower_tail < avg_upper_tail:
        interpretation = (
            "A strong bullish trend may be in place: multiple consecutive bullish HA candles "
            "with relatively small lower tails."
        )
    elif consecutive_bear > 2 and avg_upper_tail < avg_lower_tail:
        interpretation = (
            "A strong bearish trend may be in place: multiple consecutive bearish HA candles "
            "with relatively small upper tails."
        )
    elif num_doji > 0:
        interpretation = f"{num_doji} Doji candle(s) detected, indicating uncertainty or a potential trend reversal."
    else:
        interpretation = "No distinct pattern of consecutive candles found. Trend signals are not strongly indicated."

    # (d) Build the Pydantic model
    result = HeikinAshiAnalysis(
        total_candles=lookback,
        num_bull=num_bull,
        num_bear=num_bear,
        num_doji=num_doji,
        consecutive_bull=consecutive_bull,
        consecutive_bear=consecutive_bear,
        avg_upper_tail=avg_upper_tail,
        avg_lower_tail=avg_lower_tail,
        interpretation=interpretation,
    )
    return result


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

        # params.symbols
        params["symbols"] = symbols

        if is_future:
            params["type"] = "future"

        balances = self.exchange.fetch_balance(params)

        result["balances"] = {"USDT": balances["USDT"]}

        result["positions"] = {
            symbol: self.get_positions(symbol + "USDT")
            for symbol in symbols
            if symbol != "USDT"
        }

        return FuturesBalances(
            balances=[
                FuturesBalance(
                    symbol=symbol,
                    free=(
                        float(result["balances"][symbol]["free"] or 0)
                        if symbol in result["balances"]
                        else 0
                    ),
                    used=(
                        float(result["balances"][symbol]["used"] or 0)
                        if symbol in result["balances"]
                        else 0
                    ),
                    total=(
                        float(result["balances"][symbol]["total"] or 0)
                        if symbol in result["balances"]
                        else 0
                    ),
                    positions=(
                        result["positions"][symbol]
                        if symbol in result["positions"]
                        else None
                    ),
                )
                for symbol in symbols
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

    def generate_technical_prompts(
        self,
        symbol: str,
        balances: Optional[FuturesBalances],
        target_position: Optional[FuturesBalancePositionInfo],
        addtion_context: str = "",
        timeframe="1h",
        limit=500,
        target_currency="BTC",
    ):
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
            additional_context=addtion_context,
            target_currency=target_currency,
            position=target_position.model_dump_json() if target_position else "None",
            leverage=current_leverage or 0,
            quote_currency="USDT",
            minimum_usdt=min_notional,
            minimum_amount=min_amount,
        )

        logger.info(f"Prompt: {prompt}")

        return prompt, system_prompt, encoded_image_url

    def fetch_active_orders(self, symbol: str):
        return self.exchange.fetch_open_orders(symbol)

    def cancle_order(self, symbol: str):
        """
        포지션이 없는 경우, 관련 된 모든 주문을 취소합니다.
        """

        # API 를 통해 현재 열려있는 Order 를 찾습니다.
        active_orders_api = self.fetch_active_orders(symbol)
        # DB 에서 Parents Order 를 찾습니다.
        parents_orders = self.futures_repository.get_parents_orders(symbol)
        # DB 에서 Parents Order Id와 일치하는 것을 찾습니다.
        for order in parents_orders:
            children_orders = self.futures_repository.get_children_orders(
                parent_order_id=order.order_id
            )
            self.futures_repository.update_futures_status(
                order_id=order.order_id, status="canceled"
            )
            for children_order in children_orders:
                self.futures_repository.update_futures_status(
                    order_id=children_order.order_id, status="canceled"
                )
                if children_order.order_id in [
                    api_order.get("clientOrderId") for api_order in active_orders_api
                ]:
                    self.exchange.cancel_order(children_order.order_id, symbol)

    def cancel_all_orders(self, symbol: str = "BTCUSDT"):
        # API 를 통해 현재 열려있는 Order 를 찾습니다.
        active_orders_api = self.fetch_active_orders(symbol)
        # DB 를 통해 Order를 모두 찾습니다
        active_orders_db = self.futures_repository.get_all_futures(symbol=symbol)

        order_ids = [order.order_id for order in active_orders_db]

        for order in active_orders_api:
            if order["id"] in order_ids:
                self.futures_repository.update_futures_status(
                    order_id=order["id"], status="canceled"
                )
                self.exchange.cancel_order(order["id"], symbol)

    def execute_futures_with_suggestion(
        self,
        symbol: str,
        suggestion: FutureOpenAISuggestion,
        target_balance: Optional[FuturesBalance],
    ):
        """
        주어진 제안에 따라 선물 거래를 실행합니다.

        Returns:
            Tuple[Any, Optional[str]]: (결과 객체, 오류 메시지(있는 경우))
        """
        logger.info(f"Received suggestion: {suggestion.model_dump_json()}")

        try:
            # 입력값 검증
            if not suggestion or not suggestion.action:
                raise InvalidSuggestionException("No valid action in suggestion")

            if not symbol:
                raise InvalidSuggestionException("Symbol is required")

            # 현재 가격 조회
            try:
                ticker = self.fetch_ticker(symbol)
                current_price = ticker.last
            except Exception as e:
                logger.error(f"Failed to fetch ticker for {symbol}: {str(e)}")
                raise ExchangeConnectionException(f"Failed to fetch ticker: {str(e)}")

            # CLOSE_ORDER 액션 처리
            if suggestion.action == FuturesActionType.CLOSE_ORDER:
                try:
                    if target_balance and target_balance.positions:
                        position = target_balance.positions
                        quantity = (
                            float(suggestion.order.quantity)
                            if suggestion.order and suggestion.order.quantity
                            else 0.0
                        )

                        # 포지션 유형에 따라 적절한 청산 로직 실행
                        if position.position.upper() == "SHORT":
                            logger.info(
                                f"Closing SHORT position for {symbol} with amount {quantity}"
                            )
                            self.exchange.create_market_buy_order(
                                symbol=symbol,
                                amount=quantity,
                                params={"reduceOnly": True},
                            )
                            logger.info(
                                f"Successfully closed SHORT position for {symbol}"
                            )

                        elif position.position.upper() == "LONG":
                            logger.info(
                                f"Closing LONG position for {symbol} with amount {quantity}"
                            )
                            self.exchange.create_market_sell_order(
                                symbol=symbol,
                                amount=quantity,
                                params={"reduceOnly": True},
                            )
                            logger.info(
                                f"Successfully closed LONG position for {symbol}"
                            )
                        else:
                            logger.warning(f"No position to close for {symbol}")

                    # 미체결 주문 취소
                    try:
                        self.cancel_all_orders(symbol)
                        logger.info(
                            f"Successfully canceled all open orders for {symbol}"
                        )
                    except Exception as cancel_err:
                        logger.error(f"Failed to cancel orders: {str(cancel_err)}")
                        raise OrderCancellationException(
                            f"Failed to cancel orders: {str(cancel_err)}"
                        )

                    return (
                        FuturesVO(
                            id=None,
                            timestamp=datetime.now(),
                            order_id="",
                            parent_order_id="",
                            symbol=symbol,
                            price=current_price,
                            quantity=0,
                            side="close",
                            position_type="CLOSE",
                            take_profit=None,
                            stop_loss=None,
                            status="closed",
                        ),
                        None,
                    )

                except ccxt.NetworkError as e:
                    logger.error(f"Network error while closing position: {str(e)}")
                    raise ExchangeConnectionException(f"Network error: {str(e)}")
                except ccxt.ExchangeError as e:
                    logger.error(f"Exchange error while closing position: {str(e)}")
                    raise PositionCloseException(f"Exchange error: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error while closing position: {str(e)}")
                    raise PositionCloseException(f"Unexpected error: {str(e)}")

            # LONG 액션 처리
            elif suggestion.action == FuturesActionType.LONG:
                # 기존 SHORT 포지션이 있으면 청산
                if (
                    target_balance
                    and target_balance.positions
                    and target_balance.positions.position == "SHORT"
                ):
                    logger.info(
                        f"Closing existing SHORT position before opening LONG for {symbol}"
                    )
                    try:
                        self.exchange.create_limit_buy_order(
                            symbol,
                            (
                                abs(float(target_balance.positions.position_amt))
                                if target_balance.positions.position_amt is not None
                                else 0.0
                            ),
                            suggestion.order.price,
                            params={"reduceOnly": True},
                        )
                        logger.info(
                            f"Successfully created order to close SHORT position"
                        )

                        # 기존 주문 취소
                        self.cancel_all_orders(symbol)
                        logger.info(
                            f"Successfully canceled existing orders for {symbol}"
                        )
                    except Exception as close_err:
                        logger.error(f"Error closing SHORT position: {str(close_err)}")
                        # 오류는 기록하지만 계속 진행 - 완전한 실패 대신 부분적 실행 허용

                # 신규 LONG 포지션 생성
                logger.info(
                    f"Setting TP {suggestion.order.tp_price} and SL {suggestion.order.sl_price} for LONG position on {symbol}"
                )

                try:
                    orders = self.place_long_order(suggestion.order)
                except Exception as order_err:
                    logger.error(f"Failed to place LONG order: {str(order_err)}")
                    raise OrderCreationException(
                        f"Failed to place LONG order: {str(order_err)}"
                    )

                # DB에 주문 정보 저장
                try:
                    if orders.buy_order:
                        future = self.order_to_futures(
                            order=orders.buy_order, parent_order_id=""
                        )
                        self.futures_repository.create_futures(
                            futures=future, position_type="LONG"
                        )
                        logger.info(f"Successfully saved LONG order to database")

                    if orders.tp_order and orders.buy_order:
                        future = self.order_to_futures(
                            order=orders.tp_order,
                            parent_order_id=orders.buy_order.clientOrderId,
                        )
                        self.futures_repository.create_futures(
                            futures=future,
                            position_type="TAKE_PROFIT",
                            take_profit=suggestion.order.tp_price,
                            stop_loss=None,
                        )
                        logger.info(f"Successfully saved TP order to database")

                    if orders.sl_order and orders.buy_order:
                        future = self.order_to_futures(
                            order=orders.sl_order,
                            parent_order_id=orders.buy_order.order_id,
                        )
                        self.futures_repository.create_futures(
                            futures=future,
                            position_type="STOP_LOSS",
                            take_profit=None,
                            stop_loss=suggestion.order.sl_price,
                        )
                        logger.info(f"Successfully saved SL order to database")
                except Exception as db_err:
                    logger.error(f"Failed to save order to database: {str(db_err)}")
                    # DB 저장 실패는 기록하지만 주문 자체는 이미 완료되었으므로 계속 진행

                return orders, None

            # SHORT 액션 처리
            elif suggestion.action == FuturesActionType.SHORT:
                # 기존 LONG 포지션이 있으면 청산
                if (
                    target_balance
                    and target_balance.positions
                    and target_balance.positions.position == "LONG"
                ):
                    logger.info(
                        f"Closing existing LONG position before opening SHORT for {symbol}"
                    )
                    try:
                        self.exchange.create_limit_buy_order(
                            symbol,
                            (
                                abs(float(target_balance.positions.position_amt))
                                if target_balance.positions.position_amt is not None
                                else 0.0
                            ),
                            suggestion.order.price,
                            params={"reduceOnly": True},
                        )
                        logger.info(
                            f"Successfully created order to close LONG position"
                        )

                        # 기존 주문 취소
                        self.cancel_all_orders(symbol)
                        logger.info(
                            f"Successfully canceled existing orders for {symbol}"
                        )
                    except Exception as close_err:
                        logger.error(f"Error closing LONG position: {str(close_err)}")
                        # 오류는 기록하지만 계속 진행 - 완전한 실패 대신 부분적 실행 허용

                # 신규 SHORT 포지션 생성
                logger.info(
                    f"Setting TP {suggestion.order.tp_price} and SL {suggestion.order.sl_price} for SHORT position on {symbol}"
                )

                try:
                    orders = self.place_short_order(suggestion.order)
                except Exception as order_err:
                    logger.error(f"Failed to place SHORT order: {str(order_err)}")
                    raise OrderCreationException(
                        f"Failed to place SHORT order: {str(order_err)}"
                    )

                # DB에 주문 정보 저장
                try:
                    if orders.sell_order:
                        future = self.order_to_futures(
                            order=orders.sell_order, parent_order_id=""
                        )
                        self.futures_repository.create_futures(
                            futures=future, position_type="SHORT"
                        )
                        logger.info(f"Successfully saved SHORT order to database")

                    if orders.tp_order and orders.sell_order:
                        future = self.order_to_futures(
                            order=orders.tp_order,
                            parent_order_id=orders.sell_order.clientOrderId,
                        )
                        self.futures_repository.create_futures(
                            futures=future,
                            position_type="TAKE_PROFIT",
                            take_profit=suggestion.order.tp_price,
                            stop_loss=None,
                        )
                        logger.info(f"Successfully saved TP order to database")

                    if orders.sl_order and orders.sell_order:
                        future = self.order_to_futures(
                            order=orders.sl_order,
                            parent_order_id=orders.sell_order.clientOrderId,
                        )
                        self.futures_repository.create_futures(
                            futures=future,
                            position_type="STOP_LOSS",
                            take_profit=None,
                            stop_loss=suggestion.order.sl_price,
                        )
                        logger.info(f"Successfully saved SL order to database")
                except Exception as db_err:
                    logger.error(f"Failed to save order to database: {str(db_err)}")
                    # DB 저장 실패는 기록하지만 주문 자체는 이미 완료되었으므로 계속 진행

                return orders, None

        except InvalidSuggestionException as e:
            logger.error(f"Invalid suggestion: {str(e)}")
            return None, f"Invalid suggestion: {str(e)}"
        except ExchangeConnectionException as e:
            logger.error(f"Exchange connection error: {str(e)}")
            return None, f"Exchange connection error: {str(e)}"
        except OrderCreationException as e:
            logger.error(f"Order creation error: {str(e)}")
            return None, f"Order creation error: {str(e)}"
        except OrderCancellationException as e:
            logger.error(f"Order cancellation error: {str(e)}")
            return None, f"Order cancellation error: {str(e)}"
        except PositionCloseException as e:
            logger.error(f"Position close error: {str(e)}")
            return None, f"Position close error: {str(e)}"
        except ccxt.BaseError as e:
            logger.error(f"CCXT error: {str(e)}")
            return None, f"CCXT error: {str(e)}"
        except Exception as e:
            logger.error(
                f"Unexpected error in execute_futures_with_suggestion: {str(e)}"
            )
            return None, f"Unexpected error: {str(e)}"

    def perform_technical_analysis(self, df: pd.DataFrame):
        pivots = calculate_pivot_points(df)
        bb = calculate_bollinger_bands(df)
        fib_levels = calculate_fibonacci(df)
        macd_data = calculate_macd(df)
        macd_series = pd.Series([macd_data.macd] * len(df), index=df.index)
        rsi = calculate_rsi(df)
        ha_df = calculate_heikin_ashi(df)
        ha_analysis = analyze_heikin_ashi_model(ha_df)

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
            ha_analysis=ha_analysis.model_dump(),
        )

    def place_long_order(self, order: FuturesOrderRequest):

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
        positions = self.exchange.fetch_positions([symbol])

        if not positions or len(positions) == 0:
            return FuturesBalancePositionInfo(
                position="NONE",
                position_amt=0,
                entry_price=0,
                leverage=None,
                unrealized_profit=0,
            )
        return FuturesBalancePositionInfo(
            position=positions[0]["side"].upper(),
            position_amt=positions[0]["info"]["positionAmt"],
            entry_price=positions[0]["entryPrice"],
            leverage=positions[0]["leverage"] or None,
            unrealized_profit=positions[0]["unrealizedPnl"],
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
            order_id=order.clientOrderId,
            parent_order_id=parent_order_id,
        )
