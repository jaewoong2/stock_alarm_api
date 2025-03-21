import ccxt
import pandas as pd
import numpy as np
import json
from datetime import datetime
from sqlalchemy.orm import Session
from myapi.domain.futures.futures_schema import (
    FuturesCreate,
    FuturesResponse,
    TechnicalAnalysis,
    PivotPoints,
    BollingerBands,
    MACDResult,
    Ticker,
    OpenAISuggestion,
)
from myapi.repositories.futures_repository import FuturesRepository
from typing import Optional, Dict  # Dict 추가
import logging
from openai import OpenAI


class FuturesService:
    def __init__(self, api_key: str, secret: str, openai_api_key: str):
        self.exchange = ccxt.binance(
            {
                "apiKey": api_key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        self.openai_client = OpenAI(api_key=openai_api_key)

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
            ask = ticker.get("ask")
            high = ticker.get("high")
            low = ticker.get("low")

            if last_price is None:
                raise ValueError(f"Ticker 'last' price is None for {symbol}")

            return Ticker(
                last=float(last_price),  # None 체크 후 변환
                bid=float(bid) if isinstance(bid, (float, int)) else None,
                ask=float(ask) if isinstance(ask, (float, int)) else None,
                high=float(high) if isinstance(high, (float, int)) else None,
                low=float(low) if isinstance(low, (float, int)) else None,
            )
        except Exception as e:
            logging.error(f"fetch_ticker error: {e}")
            raise

    def calculate_pivot_points(self, df: pd.DataFrame) -> PivotPoints:
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
        self, df: pd.DataFrame, window: int = 20, num_std: int = 2
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

    def calculate_macd(self, df: pd.DataFrame) -> MACDResult:
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

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df["close"].diff().to_numpy()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.zeros(len(df))
        avg_loss = np.zeros(len(df))
        for i in range(period, len(df)):
            avg_gain[i] = np.mean(gain[i - period : i])
            avg_loss[i] = np.mean(loss[i - period : i])
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return pd.Series(rsi, index=df.index)

    def detect_divergence_advanced(
        self, df: pd.DataFrame, indicator: pd.Series, lookback: int = 5
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

    def calculate_fibonacci(self, df: pd.DataFrame) -> Dict[str, float]:
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

    def analyze_volume(self, df: pd.DataFrame) -> str:
        volume_trend = df["volume"].diff().mean()
        price_trend = df["close"].diff().mean()
        if volume_trend > 0 and price_trend > 0:
            return "strong"
        elif volume_trend < 0 and price_trend > 0:
            return "weak"
        else:
            return "neutral"

    def perform_technical_analysis(self, symbol: str) -> TechnicalAnalysis:
        df = self.fetch_ohlcv(symbol)
        pivots = self.calculate_pivot_points(df)
        bb = self.calculate_bollinger_bands(df)
        fib_levels = self.calculate_fibonacci(df)
        macd_data = self.calculate_macd(df)
        macd_series = pd.Series([macd_data.macd] * len(df), index=df.index)
        rsi = self.calculate_rsi(df)
        return TechnicalAnalysis(
            support=pivots.support1,
            resistance=pivots.resistance1,
            pivot=pivots.pivot,
            support2=pivots.support2,
            resistance2=pivots.resistance2,
            bollinger_bands=bb,
            fibonacci_levels=fib_levels,
            macd_divergence=self.detect_divergence_advanced(df, macd_series),
            macd_crossover=macd_data.crossover,
            macd_crossunder=macd_data.crossunder,
            rsi_divergence=self.detect_divergence_advanced(df, rsi),
            volume_trend=self.analyze_volume(df),
        )

    def analyze_with_openai(self, symbol: str) -> OpenAISuggestion:
        analysis = self.perform_technical_analysis(symbol)
        df = self.fetch_ohlcv(symbol)
        recent_data = df.tail(10).to_dict(orient="records")
        prompt = f"""
        You are an expert in cryptocurrency futures trading. Analyze the following technical data and recent OHLCV data for {symbol} to suggest a trading action.
        Provide your response as a JSON object with keys: "decision", "reasoning", "tp", "sl".

        ### Technical Analysis Data:
        {analysis.json(indent=2)}

        ### Recent OHLCV Data (last 10 candles):
        {json.dumps(recent_data, indent=2)}

        Make sure your response is valid JSON.
        """
        try:
            response = self.openai_client.beta.chat.completions.parse(
                model="o1-mini",
                messages=[
                    {"role": "system", "content": "You are a trading expert."},
                    {"role": "user", "content": prompt},
                ],
                response_format=OpenAISuggestion,
            )

            content = response.choices[0].message.parsed
            if content is None:
                raise ValueError("OpenAI response content is None")

            if content.decision not in ["buy", "sell", "hold"]:
                raise ValueError("Invalid OpenAI decision")

            return content
        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            raise ValueError("Invalid OpenAI response") from e

    def execute_futures_with_suggestion(
        self, symbol: str, quantity: float, repo: FuturesRepository
    ):
        suggestion = self.analyze_with_openai(symbol)
        decision = suggestion.decision.lower()
        tp = suggestion.tp
        sl = suggestion.sl
        ticker = self.fetch_ticker(symbol)
        current_price = ticker.last

        if decision == "buy":
            order = self.exchange.create_market_buy_order(symbol, quantity)
            futures = FuturesCreate(
                symbol=symbol, price=current_price, quantity=quantity, side="buy"
            )
            # 명시적으로 None 체크
            db_futures = repo.create_futures(
                db, futures, position_type="long", take_profit=tp, stop_loss=sl
            )
        elif decision == "sell":
            current_futures, row = repo.get_open_futures(symbol)
            if current_futures is not None and current_futures.position_type == "long":
                order = self.exchange.create_market_sell_order(symbol, quantity)
                return repo.update_futures_status(db, current_futures, "closed")
            else:
                order = self.exchange.create_market_sell_order(symbol, quantity)
                futures = FuturesCreate(
                    symbol=symbol, price=current_price, quantity=quantity, side="sell"
                )
                db_futures = repo.create_futures(
                    db, futures, position_type="short", take_profit=tp, stop_loss=sl
                )
        else:
            current_futures = repo.get_open_futures(symbol)
            if current_futures is not None:
                return current_futures
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
            )

        if tp is not None and sl is not None:
            position_type = db_futures.position_type or "long"
            self.set_tp_sl(symbol, position_type, quantity, tp, sl)
        self.monitor_futures(db, symbol, repo)
        return db_futures

    def set_tp_sl(
        self, symbol: str, position_type: str, quantity: float, tp: float, sl: float
    ):
        try:
            if position_type == "long":
                self.exchange.create_order(
                    symbol,
                    "limit",
                    "sell",
                    quantity,
                    tp,
                    params={"stopPrice": tp, "reduceOnly": True},
                )
                self.exchange.create_order(
                    symbol,
                    "limit",
                    "sell",
                    quantity,
                    sl,
                    params={"stopPrice": sl, "reduceOnly": True},
                )
            elif position_type == "short":
                self.exchange.create_order(
                    symbol,
                    "limit",
                    "buy",
                    quantity,
                    tp,
                    params={"stopPrice": tp, "reduceOnly": True},
                )
                self.exchange.create_order(
                    symbol,
                    "limit",
                    "buy",
                    quantity,
                    sl,
                    params={"stopPrice": sl, "reduceOnly": True},
                )
        except Exception as e:
            logging.error(f"TP/SL order creation failed: {e}")

    def monitor_futures(self, symbol: str, repo: FuturesRepository):
        futures, row = repo.get_open_futures(symbol)
        if futures is None:
            return
        ticker = self.fetch_ticker(symbol)
        current_price = ticker.last

        if futures.position_type == "long":
            if (
                futures.take_profit is not None
                and current_price >= float(futures.take_profit)
            ) or (
                futures.stop_loss is not None
                and current_price <= float(futures.stop_loss)
            ):
                repo.update_futures_status(row, "closed")

        elif futures.position_type == "short":
            if (
                futures.take_profit is not None
                and current_price <= float(futures.take_profit)
            ) or (
                futures.stop_loss is not None
                and current_price >= float(futures.stop_loss)
            ):
                repo.update_futures_status(row, "closed")
