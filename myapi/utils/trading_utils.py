import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict

from sklearn.linear_model import LinearRegression

from myapi.domain.backdata.backdata_schema import (
    DirectionPredictionResponse,
    SupportResistanceResponse,
)


class TradingUtils:
    def __init__(
        self,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        macd_tolerance: float = 0.01,
        ma_tolerance: float = 0.01,
    ):
        self.rsi_overbought = rsi_overbought  # 일반적으로 70 이상에서 과매수
        self.rsi_oversold = rsi_oversold  # 일반적으로 30 이하에서 과매도
        self.macd_tolerance = macd_tolerance  # MACD 크로스오버 민감도
        self.ma_tolerance = ma_tolerance  # 이동평균선 비교 민감도

    def _check_rsi_with_confidence(
        self, rsi: float
    ) -> Tuple[Optional[str], float, str]:
        """RSI를 평가하여 신호, 신뢰도 및 의견을 반환합니다."""
        if not isinstance(rsi, (int, float)) or rsi is None:
            return (None, 0.0, "Invalid RSI value.")
        if rsi >= self.rsi_overbought:
            confidence = min(
                0.8 + (rsi - self.rsi_overbought) * 0.01, 0.95
            )  # 과매수 강도 반영
            return ("SELL", confidence, f"RSI({rsi:.1f}) is in an overbought zone.")
        elif rsi <= self.rsi_oversold:
            confidence = min(
                0.8 + (self.rsi_oversold - rsi) * 0.01, 0.95
            )  # 과매도 강도 반영
            return ("BUY", confidence, f"RSI({rsi:.1f}) is in an oversold zone.")
        return (None, 0.5, f"RSI({rsi:.1f}) is in a neutral state.")

    def _check_macd_trigger(self, macd: float, macd_signal: float, atr: float):
        """ATR 기반 변동성을 고려한 MACD 신호를 평가합니다."""
        if not all(
            isinstance(x, (int, float)) and x is not None
            for x in [macd, macd_signal, atr]
        ):
            return (None, 0.0, "Invalid MACD input.")
        tolerance = self.macd_tolerance * atr  # 변동성 기반 허용 범위
        diff = macd - macd_signal
        if abs(diff) < tolerance:
            return (
                None,
                0.5,
                f"MACD({macd:.2f}) and Signal({macd_signal:.2f}) are in a neutral state.",
            )
        elif diff > 0:
            confidence = min(0.8 + diff * 0.1, 0.9)
            return ("BUY", confidence, "MACD has crossed above the Signal line.")
        else:
            confidence = min(0.8 - diff * 0.1, 0.9)
            return ("SELL", confidence, "MACD has crossed below the Signal line.")

    def _check_bollinger_trigger(
        self,
        current_price: float,
        bollinger_upper: float,
        bollinger_lower: float,
        prev_price: float,
    ) -> Tuple[Optional[str], float, str]:
        """볼린저 밴드 기준 신호를 평가합니다."""
        if not all(
            isinstance(x, (int, float)) and x is not None
            for x in [current_price, bollinger_upper, bollinger_lower, prev_price]
        ):
            return (None, 0.0, "Invalid Bollinger Band input.")
        upper_diff = current_price - bollinger_upper
        lower_diff = bollinger_lower - current_price
        if upper_diff >= 0 and current_price < prev_price:
            confidence = min(0.7 + upper_diff * 0.05, 0.9)
            return (
                "SELL",
                confidence,
                f"Price({current_price:.2f}) has exceeded the upper band({bollinger_upper:.2f}), indicating a bearish outlook.",
            )
        elif lower_diff >= 0 and current_price > prev_price:
            confidence = min(0.7 + lower_diff * 0.05, 0.9)
            return (
                "BUY",
                confidence,
                f"Price({current_price:.2f}) has fallen below the lower band({bollinger_lower:.2f}), indicating a bullish outlook.",
            )
        return (
            None,
            0.5,
            f"Price({current_price:.2f}) is within the Bollinger Bands in a neutral state.",
        )

    def _check_triggers_with_adx(
        self, adx: float, short_ma: float, long_ma: float
    ) -> Tuple[Optional[str], float, str]:
        """ADX와 이동평균선을 활용한 추세 시장 신호를 평가합니다."""
        if not all(
            isinstance(x, (int, float)) and x is not None
            for x in [adx, short_ma, long_ma]
        ):
            return (None, 0.0, "Invalid ADX input.")
        if short_ma > long_ma and adx > 25:  # ADX 25 이상은 강한 추세로 간주
            confidence = min(0.8 + (adx - 25) * 0.01, 0.95)
            return ("BUY", confidence, f"ADX({adx:.1f}) indicates a strong uptrend.")
        elif short_ma < long_ma and adx > 25:
            confidence = min(0.8 + (adx - 25) * 0.01, 0.95)
            return (
                "SELL",
                confidence,
                f"ADX({adx:.1f}) indicates a strong downtrend.",
            )
        return (None, 0.5, f"ADX({adx:.1f}) indicates a neutral or weak trend.")

    def _combine_signals(
        self,
        signals: Dict[str, Optional[str]],
        weights: Dict[str, float],
        score: float = 0.0,
    ):
        """지표 신호를 가중치로 결합합니다."""
        total_weight = sum(weights.values())
        normalized_weights = {k: v / total_weight for k, v in weights.items()}

        total_score = score
        for key, signal in signals.items():
            value = 0
            if signal == "BUY":
                value = 1
            elif signal == "SELL":
                value = -1
            total_score += normalized_weights.get(key, 0) * value

        return (
            "BUY" if total_score > 0 else "SELL" if total_score < 0 else None,
            total_score,
        )

    def _check_triggers(
        self,
        rsi: Optional[float],
        macd: Optional[float],
        macd_signal: Optional[float],
        short_ma: Optional[float],
        long_ma: Optional[float],
        adx: Optional[float],
        bollinger_upper: Optional[float],
        bollinger_lower: Optional[float],
        current_price: Optional[float],
        atr: Optional[float],
        prev_price: Optional[float],
        target: Optional[float] = None,
        high: Optional[float] = None,
    ) -> Tuple[Optional[str], float, str, float]:
        """다양한 지표를 기반으로 최종 매매 신호를 생성합니다."""
        signals = {}
        confidences = {}
        opinions = []

        if (
            not rsi
            or not macd
            or not macd_signal
            or not short_ma
            or not long_ma
            or not atr
            or not adx
            or not bollinger_upper
            or not bollinger_lower
            or not current_price
            or not prev_price
        ):
            return None, 0.0, "Not enough indicators.", 0.0

        # RSI 신호
        rsi_signal, rsi_conf, rsi_op = self._check_rsi_with_confidence(rsi)
        signals["rsi"] = rsi_signal
        confidences["rsi"] = rsi_conf
        opinions.append(rsi_op)

        # MACD 신호
        ma_signal, macd_conf, macd_op = self._check_macd_trigger(macd, macd_signal, atr)
        signals["macd"] = ma_signal
        confidences["macd"] = macd_conf
        opinions.append(macd_op)

        # 볼린저 밴드 신호
        bb_signal, bb_conf, bb_op = self._check_bollinger_trigger(
            current_price, bollinger_upper, bollinger_lower, prev_price
        )
        signals["bollinger"] = bb_signal
        confidences["bollinger"] = bb_conf
        opinions.append(bb_op)

        # 매수/매도 조건 점수 계산
        buy_score = self.check_buy_condition(target, short_ma, current_price, high, atr)
        sell_score = self.check_sell_condition(current_price, short_ma, atr)

        # 추세 시장 여부에 따른 신호 결합
        weights = (
            {"macd": 0.4, "adx": 0.3, "rsi": 0.2, "bollinger": 0.1}
            if adx > 25
            else {"rsi": 0.4, "macd": 0.2, "bollinger": 0.4}
        )
        if adx > 25:
            adx_signal, adx_conf, adx_op = self._check_triggers_with_adx(
                adx, short_ma, long_ma
            )
            signals["adx"] = adx_signal
            confidences["adx"] = adx_conf
            opinions.append(adx_op)

        final_signal, total_scroes = self._combine_signals(
            signals, weights, buy_score + sell_score
        )

        # 신뢰도 계산
        final_confidence = 0.0
        if final_signal:
            total_weight, weighted_conf = 0.0, 0.0
            for key, signal in signals.items():
                if signal == final_signal:
                    weighted_conf += weights.get(key, 0) * confidences[key]
                    total_weight += weights.get(key, 0)
            final_confidence = weighted_conf / total_weight if total_weight > 0 else 0.0

        return final_signal, final_confidence, " | ".join(opinions), total_scroes

    def check_buy_condition(
        self,
        target: Optional[float],
        ma: float,
        price: float,
        high: Optional[float],
        atr: Optional[float] = None,
    ) -> float:
        """매수 조건 확인."""
        if not all(
            isinstance(x, (int, float)) or x is None
            for x in [target, ma, price, high, atr]
        ):
            return 0.0
        if target is None or high is None:
            return 0.0 if price < ma else 0.5 if price >= ma else 0.0
        volatility_factor = atr * 0.5 if atr else 0.0
        if (
            price >= target - volatility_factor
            and high <= target * 1.05
            and price >= ma
        ):
            return 0.5
        return 0.0

    def check_sell_condition(
        self, current_price: float, ma: float, atr: Optional[float] = None
    ) -> float:
        """매도 조건 확인."""
        if not all(
            isinstance(x, (int, float)) or x is None for x in [current_price, ma, atr]
        ):
            return 0.0
        if atr and current_price < ma - atr * 0.3:
            return -0.5
        return -0.5 if current_price < ma else 0.0

    def get_target_price(
        self, df: pd.DataFrame, k_value: float = 0.5
    ) -> Optional[float]:
        """목표 매수가 계산 (변동성 기반)."""
        if not isinstance(df, pd.DataFrame) or len(df) < 2:
            return None
        yesterday = df.iloc[-2]
        range_value = yesterday["high"] - yesterday["low"]
        return yesterday["close"] + range_value * k_value

    def get_support_resistance_pivots(
        self, df: pd.DataFrame, period: int = 1
    ) -> SupportResistanceResponse:
        """최근 데이터를 기반으로 피벗 포인트와 지지/저항선을 계산."""
        if len(df) < period:
            raise ValueError(f"At least {period} data points are required.")

        recent = df.tail(period)
        high = recent["high"].max()
        low = recent["low"].min()
        close = recent["close"].iloc[-1]

        if not all([pd.notna(high), pd.notna(low), pd.notna(close)]):
            raise ValueError("There are missing values in the data.")

        pivot = (high + low + close) / 3.0
        range_ = high - low

        s1 = 2 * pivot - high
        r1 = 2 * pivot - low
        s2 = pivot - range_
        r2 = pivot + range_

        return SupportResistanceResponse(
            pivot=round(float(pivot), 2),
            support_levels=[round(float(s1), 2), round(float(s2), 2)],
            resistance_levels=[round(float(r1), 2), round(float(r2), 2)],
        )

    def _check_support_resistance_trigger(
        self,
        current_price: float,
        s1: float,
        s2: float,
        r1: float,
        r2: float,
        pivot: float,
        volume_spike: bool,
    ) -> Tuple[Optional[str], float, str]:
        """지지/저항선을 기반으로 신호와 신뢰도를 계산."""
        distances: Dict[str, float] = {
            "to_s1": abs(current_price - s1),
            "to_s2": abs(current_price - s2),
            "to_r1": abs(current_price - r1),
            "to_r2": abs(current_price - r2),
            "to_pivot": abs(current_price - pivot),
        }

        closest_level = min(distances, key=lambda x: distances[x])
        closest_value = locals()[closest_level.split("_")[1]]
        signal = None
        confidence = 0.5
        opinion = f"Current price({current_price:.2f}) is near {closest_level}({closest_value:.2f})."

        if "s" in closest_level and current_price >= closest_value:
            signal = "BUY"
            confidence = 0.7
            opinion += " Potential rebound near the support level."
            if volume_spike:
                confidence += 0.1
                opinion += " Increased volume raises the confidence."
            if current_price < pivot:
                confidence -= 0.1
                opinion += " Confidence decreases below the pivot."
        elif "r" in closest_level and current_price <= closest_value:
            signal = "SELL"
            confidence = 0.7
            opinion += " Potential drop near the resistance level."
            if volume_spike:
                confidence += 0.1
                opinion += " Increased volume raises the confidence."
            if current_price > pivot:
                confidence -= 0.1
                opinion += " Confidence decreases above the pivot."
        elif current_price < s1:
            signal = "SELL"
            confidence = 0.8 if volume_spike else 0.6
            opinion += f" Breaking below S1({s1:.2f}) suggests a decline."
            if volume_spike:
                opinion += " Strong signal due to a surge in volume."
        elif current_price > r1:
            signal = "BUY"
            confidence = 0.8 if volume_spike else 0.6
            opinion += f" Breaking above R1({r1:.2f}) suggests an increase."
            if volume_spike:
                opinion += " Strong signal due to a surge in volume."

        return signal, confidence, opinion

    def predict_direction_using_levels(
        self,
        df: pd.DataFrame,
        current_price: float,
        lookback_period: int = 5,
        volume_threshold: float = 1.2,
        adx: Optional[float] = None,
    ) -> DirectionPredictionResponse:
        # 데이터 유효성 검사
        if df.empty or len(df) < lookback_period:
            raise ValueError(
                f"The DataFrame is empty or needs at least {lookback_period} rows."
            )
        if not all(col in df.columns for col in ["close", "volume", "high", "low"]):
            raise ValueError("The DataFrame lacks required columns.")

        if pd.isna(current_price):
            raise ValueError("current_price is NaN.")

        levels = self.get_support_resistance_pivots(df, period=lookback_period)
        s1, s2 = levels.support_levels
        r1, r2 = levels.resistance_levels
        pivot = levels.pivot

        if any(pd.isna(x) for x in [s1, s2, r1, r2, pivot]):
            raise ValueError("There are NaN values in support/resistance levels.")

        avg_volume = df["volume"].iloc[-lookback_period:-1].mean()
        current_volume = df["volume"].iloc[-1]
        volume_spike = current_volume > avg_volume * volume_threshold

        # 지지/저항선 신호
        sr_signal, sr_confidence, sr_opinion = self._check_support_resistance_trigger(
            current_price, s1, s2, r1, r2, pivot, volume_spike
        )

        # 선형 회귀 신호
        lr_signal, lr_confidence, lr_opinion = self._check_linear_regression_trigger(df)

        # 신호와 가중치 정의
        signals = {
            "support_resistance": sr_signal,
            "linear_regression": lr_signal,
        }
        confidences = {
            "support_resistance": sr_confidence,
            "linear_regression": lr_confidence,
        }
        opinions = [sr_opinion, lr_opinion]

        # ADX 기반 동적 가중치
        if adx is not None and adx > 25:  # 추세 시장
            weights = {"support_resistance": 0.4, "linear_regression": 0.4}
        else:  # 횡보 시장 또는 ADX 미제공
            weights = {"support_resistance": 0.3, "linear_regression": 0.3}

        # _combine_signals로 최종 신호 결합
        final_signal, score = self._combine_signals(signals, weights)

        # 신뢰도 계산
        final_confidence = 0.0
        if final_signal:
            total_weight, weighted_conf = 0.0, 0.0
            for key, signal in signals.items():
                if signal == final_signal:
                    weighted_conf += weights.get(key, 0) * confidences[key]
                    total_weight += weights.get(key, 0)
            final_confidence = weighted_conf / total_weight if total_weight > 0 else 0.5
        else:
            final_confidence = 0.5

        # 가장 가까운 수준 계산
        distances: Dict[str, float] = {
            "to_s1": abs(current_price - s1),
            "to_s2": abs(current_price - s2),
            "to_r1": abs(current_price - r1),
            "to_r2": abs(current_price - r2),
            "to_pivot": abs(current_price - pivot),
        }
        closest_level = min(distances, key=lambda x: distances[x])
        closest_value = locals()[closest_level.split("_")[1]]

        return DirectionPredictionResponse(
            current_price=round(float(current_price), 2),
            closest_level=closest_level,
            closest_value=round(float(closest_value), 2),
            prediction=final_signal if final_signal else "HOLD",
            confidence=min(max(round(final_confidence, 2), 0.0), 1.0),
            volume_spike=volume_spike,
            opinions=opinions,
            score=score,
        )

    def _check_linear_regression_trigger(
        self, df: pd.DataFrame, threshold: float = 0.001
    ):
        """선형 회귀 분석을 통해 신호와 신뢰도를 계산."""
        data_frame = df[["close"]].dropna().copy()
        if len(data_frame) < 2:
            return None, 0.0, "Not enough data to perform linear regression."

        X = np.arange(len(data_frame)).reshape(-1, 1)
        y = data_frame["close"].to_numpy().reshape(-1, 1)

        model = LinearRegression()
        model.fit(X, y)

        slope = model.coef_[0][0]
        r2 = model.score(X, y)
        trend = (
            "NEUTRAL"
            if abs(slope) < threshold
            else ("UPWARD" if slope > 0 else "DOWNWARD")
        )

        signal = None
        confidence = r2  # R²를 기본 신뢰도로 사용
        opinion = f"Linear regression trend: {trend}, slope: {slope:.4f}, R²: {r2:.4f}"

        if trend == "UPWARD":
            signal = "BUY"
            confidence = min(0.7 + abs(slope) * 0.1, 0.9) * r2
            opinion += " - Upward trend, indicating a buy signal."
        elif trend == "DOWNWARD":
            signal = "SELL"
            confidence = min(0.7 + abs(slope) * 0.1, 0.9) * r2
            opinion += " - Downward trend, indicating a sell signal."

        return signal, confidence, opinion
