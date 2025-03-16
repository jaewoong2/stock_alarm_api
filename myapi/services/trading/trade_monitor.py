# myapi/services/trading/trade_monitor.py

import logging
from typing import Any, Dict
from fastapi import HTTPException

from myapi.domain.trading.coinone_schema import TriggerResponse
from myapi.services.backdata_service import BackDataService
from myapi.utils.indicators import get_technical_indicators
from myapi.utils.trading_utils import TradingUtils

logger = logging.getLogger(__name__)


class TradeMonitor:
    def __init__(
        self, backdata_service: BackDataService, trading_utils: TradingUtils
    ) -> None:
        self.backdata_service = backdata_service
        self.trading_utils = trading_utils

    def monitor_triggers(
        self, symbol: str, interval: str = "15m", size: int = 200
    ) -> TriggerResponse:
        """
        캔들 데이터와 기술적 지표를 기반으로 트리거 신호를 모니터링하여 반환합니다.
        """
        try:
            current_info: Dict[str, Any] = self.backdata_service.get_market_data(
                symbol.upper()
            )

            candles = self.backdata_service.get_coinone_candles(
                quote_currency="KRW",
                target_currency=symbol.upper(),
                interval=interval,
                size=size,
            )

            if candles is None or len(candles) < 120:
                return TriggerResponse(
                    status="ERROR", message="캔들 데이터 부족 (최소 120개 필요)"
                )

            indicators, _ = get_technical_indicators(candles, size)

            if not indicators:
                return TriggerResponse(status="ERROR", message="기술적 지표 계산 오류")

            # 주요 지표 추출 (존재하지 않을 수 있으므로 .get 사용)
            rsi = indicators.get("RSI_14")
            macd = indicators.get("MACD")
            macd_signal = indicators.get("MACD_Signal")
            short_ma = indicators.get("MA_short_9")
            long_ma = indicators.get("MA_long_21")
            boll_upper = indicators.get("BB_Upper")
            boll_lower = indicators.get("BB_Lower")
            current_price = current_info.get("price")
            prev_price = indicators.get("Latest_Close")
            atr = indicators.get("ATR_14")
            adx = indicators.get("ADX")
            high = indicators.get("high")

            target = self.trading_utils.get_target_price(candles)
            signal, _, opinion, score = self.trading_utils._check_triggers(
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal,
                short_ma=short_ma,
                long_ma=long_ma,
                adx=adx,
                bollinger_upper=boll_upper,
                bollinger_lower=boll_lower,
                current_price=current_price,
                atr=atr,
                prev_price=prev_price,
                target=target,
                high=high,
            )

            response = self.trading_utils.predict_direction_using_levels(
                candles, lookback_period=size, volume_threshold=1.2, adx=adx
            )

            combined_opinion = (
                f"{interval} candle indicators >>\n\n{opinion}\n"
                + "\n".join(response.opinions)
            )

            if signal:
                logger.info("Trigger detected: %s for %s", signal, symbol)

            # 신호 점수 합산에 따라 최종 신호 결정
            if response.score + score >= 0.5:
                signal = "BUY"
            elif response.score + score <= 0:
                signal = "SELL"

            return TriggerResponse(
                status=signal, message=combined_opinion, indicators=indicators
            )
        except Exception as exc:
            logger.error("Error in monitor_triggers: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))
