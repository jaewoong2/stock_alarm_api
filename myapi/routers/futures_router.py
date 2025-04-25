from asyncio import futures
from calendar import c
import dis
from heapq import merge
import json
import logging
from math import log
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from dependency_injector.wiring import inject, Provide
from fastapi.responses import PlainTextResponse
from numpy import add
from pandas import DataFrame

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.futures.futures_schema import (
    ExecuteFutureOrderRequest,
    ExecuteFuturesRequest,
    FutureOpenAISuggestion,
    FuturesConfigRequest,
    FuturesResponse,
    IndiCfg,
    QueueMessage,
    ResumptionConfiguration,
    ResumptionRequestData,
    RiskConfiguration,
    TechnicalAnalysis,
    TechnicalAnalysisRequest,
)
from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.ai_service import AIService
from myapi.services.aws_service import AwsService
from myapi.services.discord_service import DiscordService
from myapi.services.futures_service import FuturesService, generate_prompt_for_image
from myapi.utils.resumption_utils import (
    add_indis,
    annotate_with_narrative_dynamic,
    build_explanation,
    build_snapshot,
    signal_logic,
)
from myapi.utils.utils import format_trade_summary

router = APIRouter(prefix="/futures", tags=["futures"])


logger = logging.getLogger(__name__)


@router.get("/balance", tags=["futures"])
@inject
async def get_futures_balance(
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    return futures_service.fetch_balance()


@router.get("/{symbol}", tags=["futures"], response_model=List[FuturesResponse])
@inject
async def get_futures(
    symbol: str,
    repo: FuturesRepository = Depends(
        Provide[Container.repositories.futures_repository]
    ),
):
    futures = repo.get_futures_by_symbol(symbol)
    if not futures:
        raise HTTPException(status_code=404, detail="No futures found")
    return futures


@router.get("/ticker/{symbol}")
@inject
async def get_ticker(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        ticker = futures_service.fetch_ticker(symbol)
        return {"symbol": f"{symbol}/USDT", "price": ticker.last}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{symbol}", tags=["futures"], response_model=TechnicalAnalysis)
@inject
async def get_technical_analysis(
    symbol: str,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        df = futures_service.fetch_ohlcv(symbol)
        return futures_service.perform_technical_analysis(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/openai-analysis")
@inject
async def get_openai_analysis(
    data: TechnicalAnalysisRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        balance_position = futures_service.fetch_balance()
        target_currency = data.symbol.split("USDT")[0]
        return futures_service.generate_technical_prompts(
            symbol=data.symbol,
            timeframe=data.interval,
            limit=data.size,
            target_currency=target_currency,
            balances=balance_position,
            target_position=(
                balance_position.balances[0].positions
                if balance_position.balances and len(balance_position.balances) > 0
                else None
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI analysis failed: {str(e)}")


@router.post("/execute_futures", tags=["futures"])
@inject
async def excute_order():
    print("hello world")


@router.post("/execute", tags=["futures"])
@inject
async def execute_futures_with_ai(
    data: ExecuteFuturesRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
):
    logger.info(f"Received data: {data.model_dump_json()}")
    try:
        # 선물 거래 대상 통화
        target_currency = data.symbol.split("USDT")[0]
        # 현재 선물 계좌 정보
        balance_position = futures_service.fetch_balance(
            is_future=True, symbols=[target_currency, "USDT"]
        )

        target_balance = futures_service.get_target_balance(
            target_currency=target_currency
        )

        if (
            target_balance
            and target_balance.positions
            and target_balance.positions.position_amt == 0
        ):
            futures_service.cancle_order(data.symbol)

        if not target_balance:
            futures_service.cancle_order(data.symbol)

        futures_service.cancel_sibling_order_by_active_order(symbol=data.symbol)

        logger.info(f"balance_position: {balance_position.model_dump()}")
        logger.info(
            f"target_balance: {target_balance.model_dump() if target_balance else None}"
        )

        # _, _, base64_image_url = futures_service.generate_technical_prompts(
        #     symbol=data.symbol,
        #     timeframe=data.image_timeframe,
        #     limit=data.limit,
        #     target_currency=target_currency,
        #     balances=balance_position,
        #     target_position=(target_balance.positions if target_balance else None),
        # )

        # image_suggestion = ai_service.completions_parse(
        #     system_prompt="You are an AI specializing in short-term futures Crypto Trading",
        #     prompt=generate_prompt_for_image(
        #         interval=data.image_timeframe, symbol=data.symbol, length=data.limit
        #     ),
        #     schema=FutureOpenAISuggestion,
        #     chat_model=ChatModel.GPT_4O_MINI,
        #     image_url=f"data:image/jpeg;base64,{base64_image_url}",
        # )

        # AI 분석 요청을 위한 프롬프트 생성
        prompt, system_prompt, _ = futures_service.generate_technical_prompts(
            symbol=data.symbol,
            # 단기 Timeframe
            timeframe=data.timeframe,
            limit=data.limit,
            # 장기 Timeframe
            longterm_timeframe=data.longterm_timeframe,
            # 공통
            target_currency=target_currency,
            balances=balance_position,
            target_position=(target_balance.positions if target_balance else None),
            # 추가 Context
            addtion_context=data.additional_context if data.additional_context else "",
            # addtion_context=f"It is {data.image_timeframe}'s plot chart summary: {image_suggestion.detaild_summary}",
        )

        # AI 분석 요청
        technical_suggestion = ai_service.completions_parse(
            system_prompt=system_prompt,
            prompt=prompt,
            schema=FutureOpenAISuggestion,
            chat_model=ChatModel.O4_MINI,
            image_url=None,
        )

        # 분석 결과 Logging / Discode 전송
        discord_service.send_message(
            format_trade_summary(technical_suggestion.model_dump())
        )
        # discord_service.send_message(image_suggestion.model_dump_json())

        # AI 분석 결과를 바탕으로 선물 거래 실행
        # - 기존 거래
        #   - 같은 포지션 일 경우, (TP/SL) 수정
        #   - 다른 포지션 일 경우, 전체 주문 취소, 포지션 종료 및 새롭게 시작
        #   - 취소 일 경우, 전체 주문 취소, 포지션 종료

        suggetions = [
            technical_suggestion.first_order,
            technical_suggestion.second_order,
            technical_suggestion.third_order,
        ]

        total_result = []
        for suggetion in suggetions:
            if suggetion == None:
                continue

            # 주문 실행
            result = futures_service.execute_futures_with_suggestion(
                symbol=data.symbol,
                suggestion=suggetion,
                target_balance=target_balance,
            )

            if result == None:
                continue

            response, error_message = result

            total_result.append(response)

            # # 선물 거래 결과 Logging / Discode 전송
            if response:
                discord_service.send_message(response.model_dump_json())
                logger.info(f"Futures execution result: {response.model_dump_json()}")

            if error_message:
                discord_service.send_message(error_message)
                logger.info(f"Futures execution result: {error_message}")

        return total_result

    except Exception as e:
        logging.error(f"Error in execute_futures_with_ai: {e}")
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )


@router.get("/futures/signal", tags=["futures"])
@inject
async def get_signal(
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    limit: int = 500,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
):
    try:
        candles_info = futures_service.fetch_ohlcv(
            symbol=symbol, timeframe=timeframe, limit=limit
        )
        # AI 분석 요청을 위한 프롬프트 생성
        indicators = futures_service.get_technical_indicators(
            candles_info=candles_info, limit=limit
        )

        if not indicators:
            raise HTTPException(status_code=404, detail="No indicators found")

        if not indicators.analysis:
            raise HTTPException(status_code=404, detail="No analysis found")

        if not indicators.analysis.signals:
            raise HTTPException(status_code=404, detail="No signals found")

        context = ""

        total_signal = indicators.analysis.total_signal

        if total_signal:
            if not total_signal.signal:
                raise HTTPException(status_code=404, detail="No total signal found")

            if total_signal.signal.upper() == "LONG":
                context += f"[Signal-{0}]_{total_signal.signal.upper()}"
                context += f"[Description-{0}]_{total_signal.explanation}"

            if total_signal.signal.upper() == "SHORT":
                context += f"[Signal-{0}]_{total_signal.signal.upper()}"
                context += f"[Description-{0}]_{total_signal.explanation}"

        for index, indicator in enumerate(indicators.analysis.signals):
            if not indicator.signal:
                continue

            if indicator.signal.upper() == "LONG":
                context += f"[Signal_{index}]_{indicator.signal.upper()}"
                context += f"[Description_{index}]_{indicator.explanation}"

            if indicator.signal.upper() == "SHORT":
                context += f"[Signal_{index}]_{indicator.signal.upper()}"
                context += f"[Description_{index}]_{indicator.explanation}"

        if context != "":
            data: ExecuteFuturesRequest = ExecuteFuturesRequest(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                additional_context=context,
                longterm_timeframe="1h",
            )

            message = {
                "body": data.model_dump_json(),
                "resource": "/{proxy+}",
                "path": "/futures/execute",
                "httpMethod": "POST",
                "isBase64Encoded": False,
                "pathParameters": {"proxy": "futures/execute"},
                "queryStringParameters": {},
                "headers": {
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate, sdch",
                    "Accept-Language": "ko",
                    "Accept-Charset": "utf-8",
                },
                "requestContext": {
                    "path": "/futures/execute",
                    "resourcePath": "/{proxy+}",
                    "httpMethod": "POST",
                },
            }

            response = aws_service.send_sqs_message(
                queue_url="https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto",
                message_body=json.dumps(message),
            )

            return {
                "status": "success",
                "message": "Futures execution request queued successfully",
                "sqs_message_id": response.get("MessageId", ""),
                "data": message,
            }

        return {
            "status": "success",
            "message": "No signals found",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Signal generation failed: {str(e)}"
        )


@router.post("/excute_order", tags=["futures"])
@inject
async def execute_futures_order(
    data: ExecuteFutureOrderRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
):
    try:
        # 선물 거래 대상 통화
        target_currency = data.symbol.split("USDT")[0]
        # 현재 선물 계좌 정보
        balance_position = futures_service.fetch_balance(
            is_future=True, symbols=[target_currency, "USDT"]
        )

        target_balance = futures_service.get_target_balance(
            target_currency=target_currency
        )

        result = futures_service.execute_futures_with_suggestion(
            symbol=data.symbol,
            suggestion=data.suggestion,
            target_balance=target_balance,
        )

        if result == None:
            return None

        response, error_message = result

        # # 선물 거래 결과 Logging / Discode 전송
        if response:
            discord_service.send_message(response.model_dump_json())

        if error_message:
            discord_service.send_message(error_message)

        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )


@router.post("/config", tags=["futures"])
@inject
async def set_futures_config(
    data: FuturesConfigRequest,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    try:
        return futures_service.set_position(data)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Futures execution failed: {str(e)}"
        )


@router.post("/futures/resumption", tags=["futures"])
@inject
async def get_resumption(
    data: ResumptionRequestData,
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
    discord_service: DiscordService = Depends(
        Provide[Container.services.discord_service]
    ),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
):
    try:
        configuration = ResumptionConfiguration(
            symbol="BTC/USDT",
            indi=IndiCfg(
                ema_fast=50,
                ema_slow=200,
                ema_minor=20,
                rsi_len=14,
                atr_len=14,
                adx_len=14,
                bb_len=20,
                bb_std=2.0,
            ),
            risk=RiskConfiguration(atr_sl_mult=1.0, atr_tp_mult=1.8),
        )

        for timeframe in data.timeframes:
            dataframe = futures_service.fetch_ohlcv(
                symbol=data.symbol, timeframe=timeframe.timeframe, limit=data.limit
            )

            added_dataframe = futures_service.add_resumption_indicators(
                dataframe=dataframe, resumption_configuration=configuration
            )

            timeframe.data = added_dataframe.to_dict()

        if data.use_llm:
            # explanation = build_explanation(
            #     dM1, dM2, dB, dS, "side.final_side", configuration
            # )
            snapshot = ""
            CORE_COLS = [
                # OHLCV
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                # 파생 가격
                "hlc3",
                "oc2",
                # 추세
                "ema_fast",
                "ema_slow",
                "ema_minor",
                "ema_fast_slope",
                # 모멘텀
                "rsi",
                "rsi_change",
                "stoch_k",
                "stoch_d",
                "macd",
                "macd_signal",
                "roc",
                # 변동성
                "atr",
                "atr_percent",
                "natr",
                "atr_slope",
                # 추세 강도
                "adx",
                "lrs",
                # 볼밴·돈채널
                f"BBL_{configuration.indi.bb_len}_{configuration.indi.bb_std}",
                f"BBU_{configuration.indi.bb_len}_{configuration.indi.bb_std}",
                f"DONCH_L_{configuration.indi.don_len}",
                f"DONCH_U_{configuration.indi.don_len}",
                # 피봇 예시
                "P",
                "S1",
                "R1",
                "S2",
                "R2",
                # 프라이스 액션
                "candle_body",
                "upper_wick",
                "lower_wick",
                # VWAP
                "vwap",
                # HA / Ichimoku
                "HA_open",
                "HA_close",
                "ISA_9",
                "ISB_26",
                "ITS_9",
                "IKS_26",
                "ICS_26",
            ]

            for timeframe in data.timeframes:
                columns = [
                    column
                    for column in CORE_COLS
                    if column in timeframe.dataframe.columns
                ]

                snapshot += (
                    f"<Candle Dataframe TimeFrame {timeframe.timeframe} Start> \n"
                )
                snapshot += f"{timeframe.dataframe.tail(timeframe.snapshot_length).to_csv(columns=columns)}\n"
                snapshot += (
                    f"</Candle Dataframe TimeFrame {timeframe.timeframe} End> \n"
                )

        balance_position = futures_service.fetch_balance()
        target_currency = data.symbol.split("USDT")[0]

        # return PlainTextResponse(snapshot)

        target_balance = futures_service.get_target_balance(
            target_currency=target_currency
        )

        if (
            target_balance
            and target_balance.positions
            and target_balance.positions.position_amt == 0
        ):
            futures_service.cancle_order(data.symbol)

        if not target_balance:
            futures_service.cancle_order(data.symbol)

        futures_service.cancel_sibling_order_by_active_order(symbol=data.symbol)

        logger.info(f"balance_position: {balance_position.model_dump()}")
        logger.info(
            f"target_balance: {target_balance.model_dump() if target_balance else None}"
        )

        prompt, system_prompt = futures_service.generate_resumption_technical_prompts(
            data=snapshot,
            symbol=data.symbol,
            target_currency=target_currency,
            balances=balance_position,
            target_position=target_balance.positions if target_balance else None,
            addtion_context="",
        )

        # AI 분석 요청
        technical_suggestion = ai_service.completions_parse(
            system_prompt=system_prompt,
            prompt=prompt,
            schema=FutureOpenAISuggestion,
            chat_model=ChatModel.O4_MINI,
            image_url=None,
        )

        # 분석 결과 Logging / Discode 전송
        discord_service.send_message(
            format_trade_summary(technical_suggestion.model_dump())
        )
        # discord_service.send_message(image_suggestion.model_dump_json())

        # AI 분석 결과를 바탕으로 선물 거래 실행
        # - 기존 거래
        #   - 같은 포지션 일 경우, (TP/SL) 수정
        #   - 다른 포지션 일 경우, 전체 주문 취소, 포지션 종료 및 새롭게 시작
        #   - 취소 일 경우, 전체 주문 취소, 포지션 종료

        suggetions = [
            technical_suggestion.first_order,
            technical_suggestion.second_order,
            technical_suggestion.third_order,
        ]

        total_result = []
        for suggetion in suggetions:
            if suggetion == None:
                continue

            # 주문 실행
            result = futures_service.execute_futures_with_suggestion(
                symbol=data.symbol,
                suggestion=suggetion,
                target_balance=target_balance,
            )

            if result == None:
                continue

            response, error_message = result

            total_result.append(response)

            # # 선물 거래 결과 Logging / Discode 전송
            if response:
                discord_service.send_message(response.model_dump_json())
                logger.info(f"Futures execution result: {response.model_dump_json()}")

            if error_message:
                discord_service.send_message(error_message)
                logger.info(f"Futures execution result: {error_message}")

        return total_result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Signal generation failed: {str(e)}"
        )
