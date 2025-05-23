import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from myapi.domain.ai.ai_schema import Action, ActionType, TradingResponse
from myapi.domain.backdata.backdata_schema import Article
from myapi.domain.trading.trading_model import (
    ActionEnum,
    ExecutionStatus,
    Trade,
)
from myapi.domain.trading.coinone_schema import (
    ActiveOrder,
    CoinoneOrderResponse,
    OrderRequest,
    PlaceOrderResponse,
)
from myapi.domain.trading.trading_schema import BackdataInformations, TransactionCreate
from myapi.repositories.trading_repository import TradingRepository
from myapi.services.ai_service import AIService
from myapi.services.backdata_service import BackDataService
from myapi.services.coinone_service import CoinoneService
from myapi.utils.indicators import get_technical_indicators
from myapi.utils.trading_utils import TradingUtils

logger = logging.getLogger(__name__)

MIN_ORDER_AMOUNT = 5000  # 최소 주문 금액 (설정파일 등으로 분리 가능)


class TradeExecutor:

    def __init__(
        self,
        ai_service: AIService,
        backdata_service: BackDataService,
        coinone_service: CoinoneService,
        trading_repository: TradingRepository,
        trading_utils: TradingUtils,
    ) -> None:
        self.ai_service = ai_service
        self.backdata_service = backdata_service
        self.coinone_service = coinone_service
        self.trading_repository = trading_repository
        self.trading_utils = trading_utils

    def execute_trade(
        self,
        symbol: str,
        interval: str = "1h",
        opinion: Optional[str] = None,
        size: int = 500,
    ) -> TradingResponse:
        try:
            transaction_data = self.coinone_service.get_completed_order(
                target_currency=symbol.upper(),
                quote_currency="KRW",
                size=100,
                minutes=60 * 24 * 7,
            )

            self.trading_repository.insert_transactions_if_not_exist(
                [
                    TransactionCreate(
                        id=None,
                        currency=symbol.upper(),
                        qty=float(order.qty),
                        avarage_price=float(order.price),
                        total_price=float(order.price) * float(order.qty),
                        fee=float(order.fee),
                        timestamp=datetime.fromtimestamp(order.timestamp / 1e3),
                        trade_id=order.trade_id,
                        order_id=order.order_id,
                        action=ActionEnum.SELL if order.is_ask else ActionEnum.BUY,
                    )
                    for order in transaction_data.completed_orders
                ]
            )

            backdata_information = self._get_information(
                symbol=symbol, interval=interval, size=size
            )

            decision, prompt = self.ai_service.analyze_market(
                market_data=backdata_information.market_data,
                technical_indicators=(
                    backdata_information.technical_indicators.model_dump()
                ),
                previous_trade_info=backdata_information.trading_info.action_string,
                balances_data=backdata_information.balances.description,
                target_currency=symbol.upper(),
                quote_currency="KRW",
                orderbook_data=backdata_information.orderbook.description,
                sentiment_data=backdata_information.sentiment.description,
                news_data={
                    n.title: n.description
                    for n in backdata_information.news
                    if isinstance(n, Article)
                },
                arbitrage_signal=backdata_information.arbitrage_signal.description,
                current_active_orders=backdata_information.active_orders.active_orders,
                additional_context=(
                    f"Trigger detected: {opinion}. "
                    "Validate this action based on current market conditions and technical indicators."
                ),
                interval=interval,
            )

            ai_action = (
                decision.action.action.upper() if decision and decision.action else None
            )

            base_trade_data = {
                "timestamp": backdata_information.current_time,
                "symbol": symbol.upper(),
                "reason": (
                    f"Trigger: {opinion}, AI decision: {ai_action} - "
                    f"{decision.action.reason if decision and decision.action else 'No reason provided'}"
                ),
                "openai_prompt": prompt,
            }

            if ai_action == "CANCEL":
                response = self._handle_cancel(
                    symbol=symbol,
                    decision=decision.action,
                    orders=backdata_information.active_orders.active_orders,
                    trade_data=base_trade_data,
                )

            elif ai_action == "BUY":
                response = self._handle_buy(
                    symbol,
                    backdata_information.market_data,
                    base_trade_data,
                    decision.action,
                )
            elif ai_action == "SELL":
                response = self._handle_sell(
                    symbol,
                    backdata_information.market_data,
                    base_trade_data,
                    decision.action,
                )
            else:
                response = self._handle_hold(
                    base_trade_data=base_trade_data,
                    decision=decision.action,
                )

            logger.info("Executed trade response: %s", response)
            return response

        except Exception as exc:
            logger.error("Error in execute_trade: %s", exc, exc_info=True)
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason="Error occurred during trade execution: " + str(exc),
                    prediction="",
                    priority=0,
                )
            )

    def _handle_cancel(
        self, symbol: str, decision: Action, orders: List[ActiveOrder], trade_data: dict
    ) -> TradingResponse:
        reason = ""
        if decision and decision.order and decision.order.order_id:
            if decision.order.order_id not in [order.order_id for order in orders]:
                reason = f"존재 하지 않는 Order_Id {decision.order.order_id} 입니다"
                return TradingResponse(
                    action=Action(
                        action=ActionType.CANCEL,
                        market_outlook="",
                        order=None,
                        reason=reason,
                        prediction="",
                        priority=0,
                    )
                )

        if decision and decision.order and decision.order.order_id:
            try:
                cancel_result = self.coinone_service.cancel_order(
                    order_id=decision.order.order_id,
                    target_currency=symbol.upper(),
                )
                reason = cancel_result.model_dump_json()
            except Exception as exc:
                logger.error("Error canceling order: %s", exc, exc_info=True)
                reason = "Cancel order failed: " + str(exc)

        trade = Trade(
            action=ActionEnum.CANCLE,
            amount=0,
            summary=decision.reason,
            execution_krw=(0),
            execution_crypto=(0),
            status=ExecutionStatus.SUCCESS,
            timestamp=trade_data.get("timestamp", trade_data.get("timestamp")),
            symbol=trade_data.get("symbol", trade_data.get("symbol")),
            action_string=trade_data["action_string"],
            reason=decision.reason,
            openai_prompt=trade_data["openai_prompt"],
        )

        self._record_trade(trade)

        return TradingResponse(
            action=Action(
                action=ActionType.CANCEL,
                market_outlook="",
                order=None,
                reason=reason,
                prediction="",
                priority=0,
            )
        )

    def _handle_buy(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        base_trade_data: Dict[str, Any],
        decision: Action,
    ) -> TradingResponse:
        try:
            krw_balances = self.coinone_service.get_balance(["KRW"])
            if not isinstance(krw_balances.balances, list) or not krw_balances:
                raise ValueError("Invalid KRW balance data")
            krw_balance = krw_balances.balances[0]
        except Exception as exc:
            logger.error("Error fetching KRW balance: %s", exc, exc_info=True)
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason=f"잔고 조회 실패: {exc}",
                    prediction="",
                    priority=0,
                )
            )

        try:
            available_amount = float(krw_balance.available)
        except Exception as exc:
            logger.error("Error parsing available KRW balance: %s", exc, exc_info=True)
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason="잔고 데이터 파싱 실패",
                    prediction="",
                    priority=0,
                )
            )

        if available_amount < MIN_ORDER_AMOUNT:
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason="주문 금액이 최소 주문 금액에 미달합니다.",
                    prediction="",
                    priority=0,
                )
            )

        # 의도적으로 전액 사용한다면 그대로 두고, 일부만 주문할 경우는 별도의 로직 필요
        used_amount = available_amount

        order_result = None
        if decision and decision.order:
            try:
                logger.info("Placing buy order for %s", symbol)
                order_result = self.place_order(decision.order)
            except Exception as exc:
                logger.error("Error placing order: %s", exc, exc_info=True)
                return TradingResponse(
                    action=Action(
                        action=ActionType.CANCEL,
                        market_outlook="",
                        order=None,
                        reason="주문 실행 중 오류 발생: " + str(exc),
                        prediction="",
                        priority=0,
                    )
                )

        status_enum = (
            ExecutionStatus.SUCCESS
            if order_result and getattr(order_result, "result", None) == "success"
            else ExecutionStatus.FAILURE
        )

        price = (
            decision.order.price
            if (decision and decision.order and decision.order.price)
            else 0
        )
        qty = (
            decision.order.qty
            if (decision and decision.order and decision.order.qty)
            else 0
        )

        action_str = (
            f"[총자산 {krw_balance.available}원] -> {float(price) * float(qty)}원으로 "
            f"[{symbol}]을(를) {market_data.get('price')}원에 매수"
        )
        buy_trade_data = {**base_trade_data, "action_string": action_str}

        trade = Trade(
            action=ActionEnum.BUY,
            amount=used_amount,
            summary=decision.reason,
            execution_krw=(
                getattr(order_result, "krw_balance", "0") if order_result else "0"
            ),
            execution_crypto=(
                getattr(order_result, "btc_balance", "0") if order_result else "0"
            ),
            status=status_enum,
            timestamp=buy_trade_data.get("timestamp", base_trade_data.get("timestamp")),
            symbol=buy_trade_data.get("symbol", base_trade_data.get("symbol")),
            action_string=buy_trade_data["action_string"],
            reason=decision.reason,
            openai_prompt=buy_trade_data["openai_prompt"],
        )

        self._record_trade(trade)

        return TradingResponse(
            action=Action(
                action=ActionType.BUY,
                market_outlook=f"매수 주문이 실행되었습니다 at {market_data.get('price')}",
                order=decision.order,
                reason=decision.reason,
                prediction="",
                priority=1,
            )
        )

    def _handle_sell(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        base_trade_data: Dict[str, Any],
        decision: Action,
    ) -> TradingResponse:
        try:
            coin_balances = self.coinone_service.get_balance([symbol.upper()])
            if not isinstance(coin_balances.balances, list) or not coin_balances:
                raise ValueError("코인 잔고 데이터가 유효하지 않습니다.")
            coin_balance = coin_balances.balances[0]
        except Exception as exc:
            logger.error(
                "Error fetching %s balance: %s", symbol.upper(), exc, exc_info=True
            )
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason=f"{symbol.upper()} 잔고 조회 실패: {exc}",
                    prediction="",
                    priority=0,
                )
            )

        try:
            if float(coin_balance.available) <= 0:
                return TradingResponse(
                    action=Action(
                        action=ActionType.CANCEL,
                        market_outlook="",
                        order=None,
                        reason=f"{symbol.upper()} 잔고가 부족합니다.",
                        prediction="",
                        priority=0,
                    )
                )
        except Exception as exc:
            logger.error("Error parsing coin balance: %s", exc, exc_info=True)
            return TradingResponse(
                action=Action(
                    action=ActionType.CANCEL,
                    market_outlook="",
                    order=None,
                    reason="잔고 데이터 파싱 실패",
                    prediction="",
                    priority=0,
                )
            )

        sell_amount = float(coin_balance.available)

        order_result = None
        if decision and decision.order:
            try:
                logger.info("Placing sell order for %s", symbol)
                order_result = self.place_order(decision.order)
            except Exception as exc:
                logger.error("Error placing sell order: %s", exc, exc_info=True)
                return TradingResponse(
                    action=Action(
                        action=ActionType.CANCEL,
                        market_outlook="",
                        order=None,
                        reason="주문 실행 중 오류 발생: " + str(exc),
                        prediction="",
                        priority=0,
                    )
                )

        status_enum = (
            ExecutionStatus.SUCCESS
            if order_result and getattr(order_result, "result", None) == "success"
            else ExecutionStatus.FAILURE
        )

        action_str = (
            f"[총자산 {coin_balance.available}개] -> {sell_amount}개를 "
            f"[{symbol}]을(를) {market_data.get('price')}원에 매도"
        )
        sell_trade_data = {**base_trade_data, "action_string": action_str}

        # 실제 매도 가격이 아니라, 단순히 '평단 * 수량'으로 대략적 원화 환산
        approximate_amount_krw = float(coin_balance.average_price) * sell_amount

        trade = Trade(
            action=ActionEnum.SELL,
            amount=approximate_amount_krw,
            summary=decision.reason,
            execution_krw=(
                getattr(order_result, "krw_balance", "0") if order_result else "0"
            ),
            execution_crypto=(
                getattr(order_result, "btc_balance", "0") if order_result else "0"
            ),
            status=status_enum,
            timestamp=sell_trade_data.get(
                "timestamp", base_trade_data.get("timestamp")
            ),
            symbol=sell_trade_data.get("symbol", base_trade_data.get("symbol")),
            action_string=sell_trade_data["action_string"],
            reason=decision.reason,
            openai_prompt=sell_trade_data["openai_prompt"],
        )
        self._record_trade(trade)

        return TradingResponse(
            action=Action(
                action=ActionType.SELL,
                market_outlook=f"매도 주문이 실행되었습니다 at {market_data.get('price')}",
                order=decision.order,
                reason=decision.reason,
                prediction="",
                priority=1,
            )
        )

    def _handle_hold(
        self,
        base_trade_data: Dict[str, Any],
        decision: Action,
    ) -> TradingResponse:
        hold_action_string = (
            f"{decision.order.target_currency if decision and decision.order else 'None'} "
            "매수/매도 없이 관망 중"
        )

        trade = Trade(
            action=ActionEnum.HOLD,
            amount=0.0,
            summary=decision.reason,
            execution_krw=None,
            execution_crypto=None,
            status=ExecutionStatus.SUCCESS,
            timestamp=base_trade_data.get("timestamp"),
            symbol=base_trade_data.get("symbol"),
            action_string=hold_action_string,
            reason=decision.reason,
            openai_prompt=base_trade_data.get("openai_prompt"),
        )

        self._record_trade(trade)

        return TradingResponse(
            action=Action(
                action=ActionType.HOLD,
                market_outlook="관망 중입니다.",
                order=None,
                reason=decision.reason,
                prediction="",
                priority=0,
            )
        )

    def _record_trade(self, trade: Trade):
        try:
            return self.trading_repository.insert_trading_information(trade)
        except Exception as exc:
            logger.error("Error recording trade: %s", exc, exc_info=True)

    def place_order(self, payload: Optional[OrderRequest]) -> PlaceOrderResponse:
        if payload is None:
            return PlaceOrderResponse(
                result="OrderRequest not provided",
                krw_balance="0",
                crypto_balance="0",
                error_code="None",
            )

        try:
            response = self.coinone_service.place_order(payload=payload)
            logger.info("Place order response received: %s", response)
        except Exception as exc:
            logger.error(
                "Error placing order with coinone_service: %s", exc, exc_info=True
            )
            raise

        try:
            order_response = CoinoneOrderResponse.model_validate(response)
        except Exception as exc:
            logger.error("Failed to parse order response: %s", exc, exc_info=True)
            return PlaceOrderResponse(
                result="failure",
                krw_balance="0",
                crypto_balance="0",
                error_code="Response parsing failed",
            )

        if order_response.result != "success":
            logger.error("Order response error encountered")
            return PlaceOrderResponse(
                result="failure",
                krw_balance="0",
                crypto_balance="0",
                error_code=order_response.error_code,
            )

        ### 수정됨: balances 가져온 뒤 dict로 매핑
        balances = self.coinone_service.get_balance(
            ["KRW", "BTC", payload.target_currency.upper()]
        )

        if not isinstance(balances.balances, list):
            logger.error("Failed to fetch balances after order execution")
            return PlaceOrderResponse(
                result="failure",
                krw_balance="0",
                crypto_balance="0",
                error_code="잔고 조회 실패",
            )

        balance_object = {
            b.currency.upper(): b for b in balances.balances
        }  # 딕셔너리화

        # 필요하다면 여기서부터는 원하는 필드만 추출하여 PlaceOrderResponse에 넣는다.
        krw_balance = balance_object.get("KRW")
        crypto_balance = balance_object.get(payload.target_currency.upper())

        return PlaceOrderResponse(
            result=order_response.result,
            error_code=order_response.error_code,
            krw_balance=(krw_balance.available if krw_balance else "0"),
            crypto_balance=(crypto_balance.available if crypto_balance else "0"),
        )

    def _get_information(
        self, symbol: str, interval: str, size: int, is_plot_use: bool = False
    ):
        trading_info = self.trading_repository.get_trading_information()
        market_data = self.backdata_service.get_market_data(symbol)
        candles_info = self.backdata_service.get_coinone_candles(
            quote_currency="KRW", target_currency=symbol, interval=interval, size=size
        )
        btc_candles_info = self.backdata_service.get_coinone_candles(
            quote_currency="KRW", target_currency="BTC", interval=interval, size=size
        )
        arbitrage_signal = self.trading_utils.get_arbitrage_signal(
            target_df=candles_info, btc_df=btc_candles_info, symbol=symbol
        )
        news = self.backdata_service.get_btc_news(symbol=symbol.upper())
        sentiment = self.backdata_service.get_sentiment_data()

        orderbook = self.coinone_service.get_orderbook(
            quote_currency="KRW", target_currency=symbol
        )

        balances = self.coinone_service.get_balance(["KRW", symbol.upper()])
        active_orders = self.coinone_service.get_active_orders(symbol.upper())
        current_time = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
        technical_indicators, df, _ = get_technical_indicators(candles_info, size)
        plot_image_path = None

        if is_plot_use:
            plot_image_path = self.backdata_service.upload_plot_image(
                df=df, length=200, path=f"{symbol}_{current_time}.png"
            )

        return BackdataInformations(
            trading_info=trading_info,
            market_data=market_data,
            candles_info=candles_info,
            orderbook=orderbook,
            balances=balances,
            news=news,
            sentiment=sentiment,
            active_orders=active_orders,
            current_time=current_time,
            technical_indicators=technical_indicators,
            plot_image_path=plot_image_path,
            arbitrage_signal=arbitrage_signal,
        )
