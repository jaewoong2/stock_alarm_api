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

            btc_candles = self.backdata_service.get_coinone_candles(
                quote_currency="KRW",
                target_currency="BTC",
                interval=interval,
                size=size,
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

            indicators, candles, _ = get_technical_indicators(candles, size)

            if not indicators:
                return TriggerResponse(status="ERROR", message="기술적 지표 계산 오류")

            target = self.trading_utils.get_target_price(candles)
            signal, _, opinion, score = self.trading_utils._check_triggers(
                rsi=indicators.RSI_14,
                macd=indicators.MACD,
                macd_signal=indicators.MACD_Signal,
                short_ma=indicators.MA_short_9,
                long_ma=indicators.MA_long_21,
                adx=indicators.ADX,
                bollinger_upper=indicators.BB_Upper,
                bollinger_lower=indicators.BB_Lower,
                current_price=current_info.get("price"),
                atr=indicators.ATR_14,
                prev_price=indicators.Latest_Close,
                target=target,
                high=indicators.high,
                btc_candles=btc_candles,
            )

            if btc_candles is not None:
                # (1) df를 시간순(옛날→최)으로 뒤집기
                btc_candles = btc_candles.iloc[::-1].copy()
                # btc_candles.reset_index(drop=True, inplace=True)
                btc_candles = btc_candles.reset_index()

                arbitrage_signal = self.trading_utils.get_arbitrage_signal(
                    target_df=candles, btc_df=btc_candles, symbol=symbol
                )

            response = self.trading_utils.predict_direction_using_levels(
                df=candles,
                current_price=current_info.get("price") or 0.0,
                lookback_period=size,
                volume_threshold=1.2,
                adx=indicators.ADX,
            )

            combined_opinion = (
                f"{interval} candle indicators >>\n\n{opinion}\n"
                + "\n".join(response.opinions)
                + f"\n {arbitrage_signal.description} \n"
            )

            if signal:
                logger.info("Trigger detected: %s for %s", signal, symbol)

            # 신호 점수 합산에 따라 최종 신호 결정
            if response.score + score >= 0.5:
                signal = "BUY"
            elif response.score + score <= 0:
                signal = "SELL"

            return TriggerResponse(
                status=signal,
                message=combined_opinion,
                indicators=indicators.model_dump(),
            )
        except Exception as exc:
            logger.error("Error in monitor_triggers: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))
