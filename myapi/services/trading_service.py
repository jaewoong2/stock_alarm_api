from typing import List
import requests
import hmac
import hashlib
import json
import uuid
import base64
import logging
from datetime import datetime

from myapi.domain.trading.trading_model import ActionEnum, ExecutionStatus, Trade
from myapi.domain.trading.coinone_schema import (
    Balance,
    CoinoneBalanceResponse,
    CoinoneOrderResponse,
    GetTradingInformationResponseModel,
    PlaceOrderResponse,
)
from myapi.services.backdata_service import BackDataService
from myapi.services.ai_service import AIService
from myapi.utils.config import Settings, row_to_dict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class TradingService:
    BASE_URL = "https://api.coinone.co.kr"

    def __init__(
        self,
        settings: Settings,
        backdata_service: BackDataService,
        ai_service: AIService,
        db_session: Session,
    ):
        self.access_token = settings.COIN_ACCESS_TOKEN
        self.secret_key = settings.COIN_SECRET_KEY
        self.backdata_service = backdata_service
        self.ai_service = ai_service
        self.db_session = db_session

    def insert_trading_information(self, trading: Trade) -> Trade:
        """
        거래 정보를 DB에 추가합니다.
        """
        try:
            with self.db_session.begin():
                self.db_session.add(trading)
                self.db_session.flush()  # Flush if you need to assign an ID or similar
            return trading
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close()

    def get_trading_information(
        self,
    ):
        """
        DB에서 모든 거래 정보를 조회합니다.
        """
        try:
            trade = (
                self.db_session.query(Trade).order_by(Trade.timestamp.desc()).first()
            )

            return GetTradingInformationResponseModel(**row_to_dict(trade))
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise
        finally:
            self.db_session.close()

    def _get_encoded_payload(self, payload: dict) -> bytes:
        """
        페이로드에 nonce를 추가하고 base64로 인코딩합니다.
        """
        payload["nonce"] = str(uuid.uuid4())
        dumped_json = json.dumps(payload)
        return base64.b64encode(dumped_json.encode("utf-8"))

    def _get_signature(self, encoded_payload: bytes) -> str:
        """
        인코딩된 페이로드로 HMAC-SHA512 서명을 생성합니다.
        """
        signature = hmac.new(
            self.secret_key.encode("utf-8"), encoded_payload, hashlib.sha512
        )
        return signature.hexdigest()

    def _create_headers(self, encoded_payload: bytes) -> dict:
        """
        API 호출에 필요한 헤더를 생성합니다.
        """
        return {
            "Content-type": "application/json",
            "X-COINONE-PAYLOAD": encoded_payload,
            "X-COINONE-SIGNATURE": self._get_signature(encoded_payload),
        }

    def get_balance_coinone(self, currency: str | List[str]):
        """
        코인원 API를 호출하여 지정한 통화(currency)의 잔고를 조회합니다.
        """
        endpoint = "/v2.1/account/balance"
        url = f"{self.BASE_URL}{endpoint}"
        payload = {
            "access_token": self.access_token,
            "currencies": ["KRW", "BTC", "ETH"],
        }

        encoded_payload = self._get_encoded_payload(payload)
        headers = self._create_headers(encoded_payload)

        response = requests.post(url, headers=headers)
        try:
            balance_response = CoinoneBalanceResponse.model_validate(response.json())
        except Exception as e:
            logger.error("Failed to parse balance response: %s", e)
            raise Exception("잔고 응답 파싱 실패") from e

        if balance_response.result != "success":
            raise Exception(f"잔고 조회 실패: {balance_response.error_code}")

        results: List[Balance] = []
        # currency와 일치하는 항목의 available 값을 float으로 반환
        for balance in balance_response.balances:

            if isinstance(currency, list):
                if balance.currency in currency:
                    results.append(balance)
                continue

            if balance.currency == currency:
                return balance

        if len(results) > 0:
            return results

        return Balance(available="0", limit="0", average_price="0", currency="KRW")

    def execute_trade(self, symbol: str, percentage: int | float):
        """
        1. 시장 데이터를 조회하고 AI 분석을 수행합니다.
        2. AI 분석 결과에 따라 주문을 실행합니다.
           - BUY의 경우, 계좌의 KRW 잔고의 일정 비율(percentage)을 주문 총액(amount)으로 사용합니다.
           - SELL의 경우, 해당 코인의 잔고 전체를 주문 수량(qty)으로 사용합니다.
        3. 주문 결과와 관련 정보를 Trade 모델을 통해 DB에 기록합니다.
        """

        trading_information = self.get_trading_information()
        market_data = self.backdata_service.get_market_data(symbol)
        decision = self.ai_service.analyze_market(market_data)
        action = decision.action.upper()

        # 아래에서 사용될 trade 기록에 공통으로 들어갈 항목
        common_trade_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d, %H:%M:%S"),
            "symbol": symbol.upper(),
            "reason": getattr(decision, "reason", None),
            "openai_prompt": json.dumps(market_data),
        }

        if action == "BUY":
            try:
                krw_balance = self.get_balance_coinone("KRW")
            except Exception as e:
                logger.error("Error fetching KRW balance: %s", e)
                return {"status": "ERROR", "message": f"잔고 조회 실패: {e}"}

            if not krw_balance or isinstance(krw_balance, list):
                return {"status": "ERROR", "message": f"잔고 조회 실패"}

            if float(krw_balance.available) < 5000:
                return {
                    "status": "ERROR",
                    "message": "주문 금액이 최소 주문 금액에 미달합니다.",
                }

            used_amount = float(krw_balance.available) * percentage
            order_result = self.place_order(
                symbol=symbol, amount=used_amount, side="BUY"
            )

            common_trade_data["action_string"] = (
                f"{str(used_amount)}원 으로 [{symbol}가격]: {market_data['price']}원에 구매 하였습니다."
            )

            status_enum = (
                ExecutionStatus.SUCCESS
                if order_result.result == "success"
                else ExecutionStatus.FAILURE
            )

            summary = self.ai_service.generate_trade_summary(
                information_summary=trading_information.summary,
                trade_data=common_trade_data,
                market_data=market_data,
                decision_reason=decision.reason,
            )

            trade = Trade(
                **common_trade_data,
                action=ActionEnum.BUY,
                amount=used_amount,
                summary=summary,
                execution_krw=order_result.krw_balance,  # 실제 체결 KRW 가격 정보가 있다면 수정 필요
                execution_crypto=order_result.btc_balance,  # 예시 키
                status=status_enum,
            )
            try:
                self.insert_trading_information(trade)
            except Exception as e:
                logger.error("Error inserting trade record: %s", e)

            return order_result

        elif action == "SELL":
            try:
                coin_balance = self.get_balance_coinone(symbol.upper())
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

            order_result = self.place_order(
                symbol=symbol,
                amount=float(coin_balance.available) * percentage,
                side="SELL",
            )

            status_enum = (
                ExecutionStatus.SUCCESS
                if order_result.result == "success"
                else ExecutionStatus.FAILURE
            )

            common_trade_data["action_string"] = (
                f"{str(float(coin_balance.available) * percentage)}개의 [{symbol}가격]: {market_data['price']}원에 판매 하였습니다."
            )

            summary = self.ai_service.generate_trade_summary(
                information_summary=trading_information.summary,
                trade_data=common_trade_data,
                market_data=market_data,
                decision_reason=decision.reason,
            )

            trade = Trade(
                **common_trade_data,
                action=ActionEnum.SELL,
                amount=float(coin_balance.average_price)
                * float(coin_balance.available)
                * percentage,
                summary=summary,
                execution_krw=order_result.krw_balance,
                execution_crypto=order_result.btc_balance,
                status=status_enum,
            )

            try:
                self.insert_trading_information(trade)
            except Exception as e:
                logger.error("Error inserting trade record: %s", e)

            return order_result

        else:
            # HOLD 또는 그 외의 경우에도 DB 기록을 남깁니다.

            summary = self.ai_service.generate_trade_summary(
                information_summary=trading_information.summary,
                trade_data=common_trade_data,
                market_data=market_data,
                decision_reason=decision.reason,
            )
            trade = Trade(
                **common_trade_data,
                action=ActionEnum.HOLD,
                amount=0.0,
                summary=summary,
                execution_krw=None,
                execution_crypto=None,
                status=ExecutionStatus.SUCCESS,
            )
            try:
                self.insert_trading_information(trade)
            except Exception as e:
                logger.error("Error inserting trade record: %s", e)
            return {"status": "HOLD", "message": "No action taken"}

    def place_order(self, symbol: str, amount: int | float, side: str):
        """
        코인원 주문 API (v2.1)를 호출하여 시장가 주문을 실행합니다.

        - side: "BUY" 또는 "SELL"
        - 매수 주문은 'amount' (주문 총액, KRW)를, 매도 주문은 'qty' (주문 수량)를 전달합니다.
        """
        endpoint = "/v2.1/order"
        url = f"{self.BASE_URL}{endpoint}"
        payload = {
            "access_token": self.access_token,
            "quote_currency": "KRW",
            "target_currency": symbol.upper(),
            "side": side,
            "type": "MARKET",
            "post_only": False,
        }

        if side == "BUY":
            payload["amount"] = str(amount)
        elif side == "SELL":
            payload["qty"] = str(amount)

        encoded_payload = self._get_encoded_payload(payload)
        headers = self._create_headers(encoded_payload)
        response = requests.post(url, json=payload, headers=headers)
        try:
            order_response = CoinoneOrderResponse.model_validate(response.json())

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

        balances = self.get_balance_coinone(["KRW", "BTC"])

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
        )
