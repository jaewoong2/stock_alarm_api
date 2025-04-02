import dis
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.ai.ai_schema import ChatModel
from myapi.domain.futures.futures_schema import (
    ExecuteFuturesRequest,
    FutureOpenAISuggestion,
    FuturesConfigRequest,
    FuturesResponse,
    TechnicalAnalysis,
    TechnicalAnalysisRequest,
)
from myapi.repositories.futures_repository import FuturesRepository
from myapi.services.ai_service import AIService
from myapi.services.discord_service import DiscordService
from myapi.services.futures_service import FuturesService, generate_prompt_for_image

router = APIRouter(prefix="/futures", tags=["futures"])


logger = logging.getLogger(__name__)


@router.get("/balance", tags=["futures"])
@inject
async def get_futures_balance(
    futures_service: FuturesService = Depends(
        Provide[Container.services.futures_service]
    ),
):
    return futures_service.fetch_balnce()


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
        balance_position = futures_service.fetch_balnce()
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
    try:
        # 선물 거래 대상 통화
        target_currency = data.symbol.split("USDT")[0]
        # 현재 선물 계좌 정보
        balance_position = futures_service.fetch_balnce(
            is_future=True, symbols=[target_currency, "USDT"]
        )

        target_balance = None

        target_balances = [
            balance
            for balance in balance_position.balances
            if balance.symbol == target_currency
        ]

        if len(target_balances) > 0:
            target_balance = target_balances[0]

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

        _, _, base64_image_url = futures_service.generate_technical_prompts(
            symbol=data.symbol,
            timeframe=data.image_timeframe,
            limit=data.limit,
            target_currency=target_currency,
            balances=balance_position,
            target_position=(target_balance.positions if target_balance else None),
        )

        image_suggestion = ai_service.completions_parse(
            system_prompt="You are an AI specializing in short-term futures Crypto Trading",
            prompt=generate_prompt_for_image(
                interval=data.image_timeframe, symbol=data.symbol, length=data.limit
            ),
            schema=FutureOpenAISuggestion,
            chat_model=ChatModel.GPT_4O_MINI,
            image_url=f"data:image/jpeg;base64,{base64_image_url}",
        )

        # AI 분석 요청을 위한 프롬프트 생성
        prompt, system_prompt, _ = futures_service.generate_technical_prompts(
            symbol=data.symbol,
            timeframe=data.timeframe,
            limit=data.limit,
            target_currency=target_currency,
            balances=balance_position,
            target_position=(target_balance.positions if target_balance else None),
            addtion_context=f"It is {data.image_timeframe}'s plot chart summary: {image_suggestion.detaild_summary}",
        )

        # AI 분석 요청
        technical_suggestion = ai_service.completions_parse(
            system_prompt=system_prompt,
            prompt=prompt,
            schema=FutureOpenAISuggestion,
            chat_model=ChatModel.O3_MINI,
            image_url=None,
        )

        # 분석 결과 Logging / Discode 전송
        discord_service.send_message(technical_suggestion.model_dump_json())
        discord_service.send_message(image_suggestion.model_dump_json())

        # AI 분석 결과를 바탕으로 선물 거래 실행
        # - 기존 거래
        #   - 같은 포지션 일 경우, (TP/SL) 수정
        #   - 다른 포지션 일 경우, 전체 주문 취소, 포지션 종료 및 새롭게 시작
        #   - 취소 일 경우, 전체 주문 취소, 포지션 종료
        result = futures_service.execute_futures_with_suggestion(
            symbol=data.symbol,
            suggestion=technical_suggestion,
            target_balance=target_balance,
        )
        # result = None

        if result == None:
            return {"message": "No action taken."}

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


# Client_order_id -> Order_id 로 수정
