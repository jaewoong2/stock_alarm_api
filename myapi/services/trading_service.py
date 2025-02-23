from typing import Any, Dict, Union
import json
import logging
from datetime import datetime

from myapi.domain.ai.ai_schema import Action
from myapi.domain.backdata.backdata_schema import Article
from myapi.domain.trading.trading_model import ActionEnum, ExecutionStatus, Trade
from myapi.domain.trading.coinone_schema import (
    CoinoneOrderResponse,
    OrderRequest,
    PlaceOrderResponse,
)
from myapi.repositories.trading_repository import TradingRepository
from myapi.services.backdata_service import BackDataService
from myapi.services.ai_service import AIService
from myapi.services.coinone_service import CoinoneService
from myapi.utils.config import Settings

from myapi.utils.indicators import get_technical_indicators

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

    def get_trading_information(self):
        return self.trading_repository.get_trading_information()

    def execute_trade(self, symbol: str, percentage: Union[int, float]):
        """
        1. 시장 데이터를 조회하고 AI 분석을 수행합니다. (ai_service 로 전달되는 파라미터는 스크립트로 전송됨)
        2. AI 분석 결과(BUY, SELL, HOLD)에 따라 주문을 실행합니다.
           - BUY  : 계좌 KRW 잔고의 percentage 비율만큼 사용
           - SELL : 해당 코인 잔고 전체(또는 percentage 비율)만큼 판매
           - HOLD : 아무런 주문 없이 DB에 기록만 남김
        3. 주문 결과와 관련 정보를 Trade 모델을 통해 DB에 기록합니다.

        Returns:
            Dict[str, Any]: 주문 결과 또는 HOLD 상태 등의 처리 결과를 반환합니다.
        """

        # 0. 이전 거래 정보 조회
        trading_information = self.trading_repository.get_trading_information()
        # 1. 시장 데이터 조회
        market_data = self.backdata_service.get_market_data(symbol)
        # 2. 캔들 데이터 조회
        candles_info = self._fetch_candle_data()

        # 3. Order 데이터 조회
        orderbook_data = self.coinone_service.get_orderbook(
            quote_currency="KRW", target_currency=symbol
        )

        balances_data = self.coinone_service.get_balance(["KRW", symbol.upper()])
        news_data = self.backdata_service.get_btc_news()
        sentiment_data = self.backdata_service.get_sentiment_data()
        current_active_orders = self.coinone_service.get_active_orders(symbol.upper())

        # 3. AI 분석을 위한 공통 데이터 구성
        #    - ai_service로 보내는 스크립트형 데이터(여기서는 market_data, 캔들 정보 등)
        common_ai_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
            "symbol": symbol.upper(),
        }

        technical_indicators = get_technical_indicators(candles_info["15m"])
        # AI로부터 매매 의사결정 결과 받기
        decision, prompt = self.ai_service.analyze_market(
            market_data=market_data,
            technical_indicators=technical_indicators,
            previous_trade_info=trading_information.action,
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
        )

        action = decision.action.action

        # 4. 공통적으로 DB에 기록할 기본 정보
        base_trade_data = {
            "timestamp": common_ai_data["timestamp"],
            "symbol": symbol.upper(),
            "reason": getattr(decision, "reason", None),
            "openai_prompt": prompt,
        }

        if action == "CANCEL":
            if decision.action.order.order_id:
                cancel_result = self.coinone_service.cancel_order(
                    order_id=decision.action.order.order_id,
                    target_currency=symbol.upper(),
                )

                return cancel_result.model_dump()
            else:
                return {"status": "ERROR", "message": "취소할 주문 ID가 없습니다."}

        # 5. 액션 유형별 처리
        if action == "BUY":
            transaction_result = self._handle_buy(
                symbol,
                percentage,
                market_data,
                trading_information,
                base_trade_data,
                decision.action,
            )
        elif action == "SELL":
            transaction_result = self._handle_sell(
                symbol,
                percentage,
                market_data,
                trading_information,
                base_trade_data,
                decision.action,
            )
        else:  # HOLD 등 그 외
            transaction_result = self._handle_hold(
                market_data, trading_information, base_trade_data, decision.action
            )

        print(decision)
        print(transaction_result)
        logger.info("%s", transaction_result, exc_info=True)

        return decision

    def _handle_buy(
        self,
        symbol: str,
        percentage: float,
        market_data: Dict[str, Any],
        trading_information: Any,
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
        order_result = self.place_order(decision.order)
        # order_result = self.place_order(symbol=symbol, amount=used_amount, side="BUY")

        # 주문 실행 결과에 따른 상태 설정
        status_enum = (
            ExecutionStatus.SUCCESS
            if order_result.result == "success"
            else ExecutionStatus.FAILURE
        )

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

        # summary = self.ai_service.generate_trade_summary(
        #     information_summary=trading_information.summary,
        #     trade_data=buy_trade_data,  # 스크립트로 전송
        #     market_data=market_data,
        #     decision_reason=decision.reason,
        # )

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
        trading_information: Any,
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
        order_result = self.place_order(decision.order)
        # order_result = self.place_order(symbol=symbol, amount=sell_amount, side="SELL")

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
            action_string=f"{base_trade_data["symbol"]} 구매 및 판매를 하지 않았습니다. 지켜보는중",
            reason=base_trade_data["reason"],
            openai_prompt=base_trade_data["openai_prompt"],
        )

        self._record_trade(trade)
        return {"status": "HOLD", "message": "No action taken"}

    def _fetch_candle_data(self, size: int = 200) -> Dict[str, Any]:
        """
        다양한 간격(1m, 5m, 1h)의 캔들 데이터를 Fetch하여 Dict 형태로 반환
        """
        return {
            "15m": self.backdata_service.get_coinone_candles(interval="15m", size=size),
        }

    def _record_trade(self, trade: Trade) -> None:
        """
        Trade 정보를 DB에 기록하는 기능.
        """
        try:
            self.trading_repository.insert_trading_information(trade)
        except Exception as e:
            logger.error("Error inserting trade record: %s", e)

    def place_order(self, payload: OrderRequest):
        """
        코인원 주문 API (v2.1)를 호출하여 시장가 주문을 실행합니다.

        - side: "BUY" 또는 "SELL"
        - 매수 주문은 'amount' (주문 총액, KRW)를, 매도 주문은 'qty' (주문 수량)를 전달합니다.
        """
        response = self.coinone_service.place_order(payload=payload)
        try:
            order_response = CoinoneOrderResponse.model_validate(response)

        except Exception as e:
            logger.error("Failed to parse order response: %s", e)
            return PlaceOrderResponse(
                result="failure", krw_balance="0", btc_balance="0", error_code="None"
            )

        if order_response.result != "success":
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
