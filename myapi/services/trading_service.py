from typing import Any, Dict, Optional
import logging
from datetime import datetime

from fastapi import HTTPException

from myapi.domain.ai.ai_schema import Action, ActionType, TradingResponse
from myapi.domain.backdata.backdata_schema import Article
from myapi.domain.trading.trading_model import ActionEnum, ExecutionStatus, Trade
from myapi.domain.trading.coinone_schema import (
    CoinoneOrderResponse,
    OrderRequest,
    PlaceOrderResponse,
    TriggerResponse,
)
from myapi.repositories.trading_repository import TradingRepository
from myapi.services.backdata_service import BackDataService
from myapi.services.ai_service import AIService
from myapi.services.coinone_service import CoinoneService
from myapi.utils.config import Settings

from myapi.utils.indicators import get_technical_indicators
from myapi.utils.trading_utils import TradingUtils

logger = logging.getLogger(__name__)


class TradingService:
    BASE_URL = "https://api.coinone.co.kr"

    def __init__(
        self,
        settings: Settings,
        ai_service: AIService,
        backdata_service: BackDataService,
        coinone_service: CoinoneService,
        trading_repository: TradingRepository,
    ):
        self.access_token = settings.COIN_ACCESS_TOKEN
        self.secret_key = settings.COIN_SECRET_KEY
        self.ai_service = ai_service
        self.backdata_service = backdata_service
        self.coinone_service = coinone_service
        self.trading_repository = trading_repository

        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.short_ma_period = 50
        self.long_ma_period = 200

        self.trading_utils = TradingUtils(
            rsi_overbought=self.rsi_overbought,
            rsi_oversold=self.rsi_oversold,
            macd_tolerance=0.01,
            ma_tolerance=0.01,
        )

    def monitor_triggers(self, symbol: str, interval: str = "15m", size: int = 200):
        """
        기술적 지표를 모니터링하여 트리거 발생 시 execute_trade를 호출합니다.
        """
        try:
            current_information = self.backdata_service.get_market_data(symbol.upper())
            candles = self.backdata_service.get_coinone_candles(
                interval=interval, size=size
            )

            if (
                candles is None or len(candles) < 120
            ):  # get_technical_indicators 요구사항
                return TriggerResponse(
                    status="ERROR", message="캔들 데이터 부족 (최소 120개 필요)"
                )

            indicators = get_technical_indicators(candles, size)
            if not indicators:
                return TriggerResponse(status="ERROR", message="ERROR")

            rsi = indicators["RSI_14"]
            macd = indicators["MACD"]
            macd_signal_value = indicators["MACD_Signal"]
            short_ma = indicators["MA_short_9"]
            long_ma = indicators["MA_long_21"]
            bollinger_upper = indicators["BB_Upper"]
            bollinger_lower = indicators["BB_Lower"]
            current_price = current_information["price"]
            prev_price = indicators["Latest_Close"]
            atr = indicators["ATR_14"]
            adx = indicators["ADX"]
            high = indicators["high"]

            target = self.trading_utils.get_target_price(candles)

            signal, _, opinion, score = self.trading_utils._check_triggers(
                rsi=rsi,
                macd=macd,
                macd_signal=macd_signal_value,
                short_ma=short_ma,
                long_ma=long_ma,
                adx=adx,
                bollinger_upper=bollinger_upper,
                bollinger_lower=bollinger_lower,
                current_price=current_price,
                atr=atr,
                prev_price=prev_price,
                target=target,
                high=high,
            )

            response = self.trading_utils.predict_direction_using_levels(
                candles, lookback_period=size, volume_threshold=1.2, adx=adx
            )

            opinion += "\n" + "\n".join(response.opinions)
            opinion = f"{interval} candle indicators >> \n\n" + opinion

            if signal:
                logger.info(f"Trigger detected: {signal} for {symbol}")

            if response.score + score >= 0.5:
                signal = "BUY"

            if response.score + score <= 0:
                signal = "SELL"

            return TriggerResponse(status=signal, message=opinion)

        except Exception as e:
            logger.error(f"Error in monitor_triggers: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_trading_information(self):
        return self.trading_repository.get_trading_information()

    def execute_trade(
        self,
        symbol: str,
        percentage: float = 0.01,
        interval: str = "1h",
        opinion: Optional[str] = None,
        size: int = 500,
    ):
        """ """

        try:
            # 시장 데이터 수집
            trading_information = self.get_trading_information()
            market_data = self.backdata_service.get_market_data(symbol)
            candles_info = self._fetch_candle_data(interval=interval, size=size)
            orderbook_data = self.coinone_service.get_orderbook(
                quote_currency="KRW", target_currency=symbol
            )
            balances_data = self.coinone_service.get_balance(["KRW", symbol.upper()])
            news_data = self.backdata_service.get_btc_news()
            sentiment_data = self.backdata_service.get_sentiment_data()
            current_active_orders = self.coinone_service.get_active_orders(
                symbol.upper()
            )

            # AI 분석용 데이터 준비
            current_time = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

            technical_indicators = get_technical_indicators(candles_info, size)

            # AI 검증 요청
            decision, prompt = self.ai_service.analyze_market(
                market_data=market_data,
                technical_indicators=technical_indicators,
                previous_trade_info=trading_information.action_string,
                balances_data=(
                    balances_data.model_dump()
                    if not isinstance(balances_data, list)
                    else {data.currency: data.model_dump() for data in balances_data}
                ),
                target_currency=symbol.upper(),
                quote_currency="KRW",
                orderbook_data=orderbook_data.model_dump(),
                sentiment_data=sentiment_data.model_dump(),
                news_data={
                    news.title: news.model_dump()
                    for news in news_data
                    if isinstance(news, Article)  # Ensure url exists
                },
                current_active_orders=current_active_orders.model_dump(),
                additional_context=f"Trigger detected: {opinion}. Validate this action based on current market conditions and technical indicators.",
            )

            ai_action = decision.action.action
            base_trade_data = {
                "timestamp": current_time,
                "symbol": symbol.upper(),
                "reason": f"Trigger: {opinion}, AI decision: {ai_action} - {decision.action.reason}",
                "openai_prompt": prompt,
            }
            if ai_action == "CANCEL" and decision.action.order:
                if decision.action.order.order_id:
                    cancel_result = self.coinone_service.cancel_order(
                        order_id=decision.action.order.order_id,
                        target_currency=symbol.upper(),
                    )

                    return TradingResponse(
                        action=Action(
                            action=ActionType.CANCLE,
                            market_outlook="",
                            order=None,
                            reason=f"{cancel_result.model_dump_json()}",
                            prediction="",
                            priority=0,
                        )
                    )
                else:
                    return TradingResponse(
                        action=Action(
                            action=ActionType.CANCLE,
                            market_outlook="",
                            order=None,
                            reason="",
                            prediction="",
                            priority=0,
                        )
                    )
            # AI 검증 결과에 따라 처리
            if ai_action in ["BUY", "SELL"]:
                if ai_action == "BUY":
                    result = self._handle_buy(
                        symbol,
                        percentage,
                        market_data,
                        base_trade_data,
                        decision.action,
                    )
                else:  # SELL
                    result = self._handle_sell(
                        symbol=symbol,
                        percentage=percentage,
                        market_data=market_data,
                        base_trade_data=base_trade_data,
                        decision=decision.action,
                    )
            else:
                result = self._handle_hold(
                    market_data, trading_information, base_trade_data, decision.action
                )

            logger.info(f"Executed trade: {result}")
            logger.info(f"Executed trade: {decision}")

            return decision

        except Exception as e:
            logger.error(f"Error in execute_trade: {e}")
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCLE,
                    market_outlook="",
                    order=None,
                    reason="Error",
                    prediction="",
                    priority=0,
                )
            )

    def _handle_buy(
        self,
        symbol: str,
        percentage: float,
        market_data: Dict[str, Any],
        base_trade_data: Dict[str, Any],
        decision: Action,
    ):
        """
        BUY 액션 처리 로직
        """
        try:
            krw_balance = self.coinone_service.get_balance(["KRW"])[0]
        except Exception as e:
            logger.error("Error fetching KRW balance: %s", e)
            return {"status": "ERROR", "message": f"잔고 조회 실패: {e}"}

        if not krw_balance or isinstance(krw_balance, list):
            return {"status": "ERROR", "message": "잔고 조회 실패"}

        if float(krw_balance.available) < 5000:
            return {
                "status": "ERROR",
                "message": "주문 금액이 최소 주문 금액에 미달합니다.",
            }

        used_amount = float(krw_balance.available) * percentage

        # 실제 매수 주문 실행
        if decision.order:
            logger.info(decision.order.model_dump_json())
            order_result = self.place_order(decision.order)
            logger.info(order_result)

        # order_result = self.place_order(symbol=symbol, amount=used_amount, side="BUY")

        # 주문 실행 결과에 따른 상태 설정
        status_enum = (
            ExecutionStatus.SUCCESS
            if order_result.result == "success"
            else ExecutionStatus.FAILURE
        )

        if decision.order:
            price = decision.order.price or 0
            qty = decision.order.qty or 0

        # 요약 및 기록
        buy_trade_data = {
            **base_trade_data,
            "action_string": (
                f"[현재 총자산 {krw_balance.available}원] ->"
                f"{float(price) * float(qty)}원으로"
                f"[{symbol}]을(를) "
                f"{market_data['price']}원에 매수하였습니다."
            ),
        }

        trade = Trade(
            action=ActionEnum.BUY,
            amount=used_amount,
            summary=decision.reason,
            execution_krw=order_result.krw_balance,  # 실제 체결 KRW 데이터
            execution_crypto=order_result.btc_balance,  # 실제 체결 코인 데이터
            status=status_enum,
            timestamp=buy_trade_data["timestamp"],
            symbol=buy_trade_data["symbol"],
            action_string=buy_trade_data["action_string"],
            reason=decision.reason,
            openai_prompt=buy_trade_data["openai_prompt"],
        )

        # DB 저장
        self._record_trade(trade)
        return order_result

    def _handle_sell(
        self,
        symbol: str,
        percentage: float,
        market_data: Dict[str, Any],
        base_trade_data: Dict[str, Any],
        decision: Action,
    ):
        """
        SELL 액션 처리 로직
        """
        try:
            coin_balance = self.coinone_service.get_balance([symbol.upper()])[0]
        except Exception as e:
            logger.error("Error fetching %s balance: %s", symbol.upper(), e)
            return {"status": "ERROR", "message": f"잔고 조회 실패: {e}"}

        if not coin_balance or isinstance(coin_balance, list):
            return {
                "status": "ERROR",
                "message": f"{symbol.upper()} 잔고가 부족합니다.",
            }

        if float(coin_balance.average_price) <= 0:
            return {
                "status": "ERROR",
                "message": f"{symbol.upper()} 잔고가 부족합니다.",
            }

        sell_amount = float(coin_balance.available)

        # 실제 매도 주문 실행
        if decision.order:
            logger.info(decision.order.model_dump_json())
            order_result = self.place_order(decision.order)
            logger.info(order_result)

        status_enum = (
            ExecutionStatus.SUCCESS
            if order_result.result == "success"
            else ExecutionStatus.FAILURE
        )

        sell_trade_data = {
            **base_trade_data,
            "action_string": f"[현재 총자산 {coin_balance.available}개] ->"
            f"{sell_amount}개의"
            f"[{symbol}]을(를) "
            f"{market_data['price']}원에 매도하였습니다.",
        }

        # summary = self.ai_service.generate_trade_summary(
        #     information_summary=trading_information.summary,
        #     trade_data=sell_trade_data,  # 스크립트로 전송
        #     market_data=market_data,
        #     decision_reason=decision.reason,
        # )

        # 금액 환산 (예: 코인 보유수량 * 평균 단가)
        approximate_amount_krw = (
            float(coin_balance.average_price)
            * float(coin_balance.available)
            * percentage
        )

        trade = Trade(
            action=ActionEnum.SELL,
            amount=approximate_amount_krw,
            summary=decision.reason,
            execution_krw=order_result.krw_balance,
            execution_crypto=order_result.btc_balance,
            status=status_enum,
            timestamp=sell_trade_data["timestamp"],
            symbol=sell_trade_data["symbol"],
            action_string=sell_trade_data["action_string"],
            reason=sell_trade_data["reason"],
            openai_prompt=sell_trade_data["openai_prompt"],
        )

        self._record_trade(trade)
        return order_result

    def _handle_hold(
        self,
        market_data: Dict[str, Any],
        trading_information: Any,
        base_trade_data: Dict[str, Any],
        decision: Action,
    ) -> Dict[str, Any]:
        """
        HOLD 액션 처리 로직
        """

        trade = Trade(
            action=ActionEnum.HOLD,
            amount=0.0,
            summary=decision.reason,
            execution_krw=None,
            execution_crypto=None,
            status=ExecutionStatus.SUCCESS,
            timestamp=base_trade_data["timestamp"],
            symbol=base_trade_data["symbol"],
            action_string=f"{decision.order.target_currency if decision.order else "None"} 구매 및 판매를 하지 않았습니다. 지켜보는중",
            reason=decision.reason,
            openai_prompt=base_trade_data["openai_prompt"],
        )

        self._record_trade(trade)
        return {"status": "HOLD", "message": "No action taken"}

    def _fetch_candle_data(self, interval: str = "1h", size: int = 200):
        """
        다양한 간격(1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 1d, 1w, 1mon)의 캔들 데이터를 Fetch하여 Dict 형태로 반환
        """
        return self.backdata_service.get_coinone_candles(interval=interval, size=size)

    def _record_trade(self, trade: Trade) -> None:
        """
        Trade 정보를 DB에 기록하는 기능.
        """
        try:
            self.trading_repository.insert_trading_information(trade)
        except Exception as e:
            logger.error("Error inserting trade record: %s", e)

    def place_order(self, payload: OrderRequest | None):
        """
        코인원 주문 API (v2.1)를 호출하여 시장가 주문을 실행합니다.

        - side: "BUY" 또는 "SELL"
        - 매수 주문은 'amount' (주문 총액, KRW)를, 매도 주문은 'qty' (주문 수량)를 전달합니다.
        """
        if payload is None:
            return PlaceOrderResponse(
                result="OrderRequest 가 없습니다.",
                krw_balance="0",
                btc_balance="0",
                error_code="None",
            )

        response = self.coinone_service.place_order(payload=payload)

        logger.info(response)

        try:
            order_response = CoinoneOrderResponse.model_validate(response)

        except Exception as e:
            logger.error("Failed to parse order response: %s", e)

            return PlaceOrderResponse(
                result="failure", krw_balance="0", btc_balance="0", error_code="None"
            )

        if order_response.result != "success":
            logger.error(
                "Failed to parse order response: %s", order_response.model_dump_json()
            )

            return PlaceOrderResponse(
                result="failure",
                krw_balance="0",
                btc_balance="0",
                error_code=order_response.error_code,
            )

        balances = self.coinone_service.get_balance(
            ["KRW", "BTC", payload.target_currency.upper()]
        )

        if not isinstance(balances, list):
            logger.error(
                "Failed to parse order response: %s", order_response.model_dump_json()
            )
            return PlaceOrderResponse(
                result="failure",
                krw_balance="0",
                btc_balance="0",
                error_code="잔고 조회 실패",
            )

        balance_object = {balance.currency: balance for balance in balances}

        return PlaceOrderResponse(
            result=order_response.result,
            error_code=order_response.error_code,
            krw_balance=balance_object["KRW"].available,
            btc_balance=balance_object["BTC"].available,
            **balance_object,
        )
