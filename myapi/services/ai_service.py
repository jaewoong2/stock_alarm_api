# services/ai_service.py
from typing import Dict, List, Type, TypeVar
from fastapi import HTTPException
import openai
import json

from pydantic import BaseModel

from myapi.domain.ai.ai_schema import TradingResponse
from myapi.domain.ai.const import generate_prompt
from myapi.domain.trading.coinone_schema import ActiveOrder
from myapi.utils.config import Settings

# T는 BaseModel을 상속하는 타입이어야 합니다.
T = TypeVar("T", bound=BaseModel)


class AIService:
    def __init__(self, settings: Settings):
        self.hyperbolic_api_key = settings.HYPERBOLIC_API_KEY
        self.open_api_key = settings.OPENAI_API_KEY

    def analyze_grid(
        self,
        indicators: Dict,
        interval: str,
        size: int,
        symbol: str,
        market_data: Dict | None,
    ):
        """
        OpenAI API 등으로부터 '최적 그리드 범위, 간격, 매매 시그널, 예측'을 받는다고 가정.
        예: 과거 시세, 기술적 지표 등을 프롬프트로 넣은 뒤
            '95~105만원 구간, 2만원 간격, 매수/매도 분포' 를 받아온다고 생각.
        여기서는 간단한 임의 로직으로 대체.

        :return: dict with recommended lower bound, upper bound, step
        """

        prompt = f"""
        Below is our current market data and technical indicators.
        Based on these, return your answer strictly in JSON format, following these requirements:

        ## technical indicators >> {indicators}
        ## current market data >> {market_data}
        ## ETC Inofrmation >> {interval}, {size}, {symbol}
        
        1. Include the fields grid_lower_bound, grid_upper_bound, and grid_step.
        2. Also provide risk management note (e.g., possible stop-loss area or caution points).
        """

        client = openai.OpenAI(
            api_key=self.open_api_key,  # This is the default and can be omitted
        )

        try:
            response = client.beta.chat.completions.parse(
                model="o3-mini",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                frequency_penalty=0.0,  # 반복 억제 정도
                presence_penalty=0.0,  # 새로운 주제 도입 억제
                # response_format=,
            )
            # response.choices[0].message.content
            content = response.choices[0].message.parsed

            if not content:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )

            if content:
                return content, prompt
            else:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )
        except Exception as e:
            # 에러 발생 시, JSON 스키마 형식으로 에러 메시지 반환
            raise HTTPException(
                status_code=403,
                detail=str(e),
            )

    def analyze_market(
        self,
        market_data: dict,
        technical_indicators: dict,
        previous_trade_info: str,
        balances_data: str,
        orderbook_data: str,
        sentiment_data: str,
        current_active_orders: List[ActiveOrder],
        news_data: dict,
        schema: Type[T] = TradingResponse,
        quote_currency: str = "KRW",
        target_currency: str = "BTC",
        additional_context: str = "",
        interval: str = "1h",
        arbitrage_signal: str = "",
    ):
        """
        OpenAI API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        prompt, system_prompt = generate_prompt(
            market_data=market_data,
            previous_trade_info=previous_trade_info,
            technical_indicators=technical_indicators,
            balances_data=balances_data,
            quote_currency=quote_currency,
            target_currency=target_currency,
            orderbook_data=orderbook_data,
            sentiment_data=sentiment_data,
            news_data=news_data,
            current_active_orders=current_active_orders,
            arbitrage_signal=arbitrage_signal,
            additional_context=additional_context,
            interval=interval,
        )

        client = openai.OpenAI(
            api_key=self.open_api_key,  # This is the default and can be omitted
        )

        try:
            response = client.beta.chat.completions.parse(
                model="o3-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                frequency_penalty=0.0,  # 반복 억제 정도
                presence_penalty=0.0,  # 새로운 주제 도입 억제
                response_format=schema,
            )
            # response.choices[0].message.content
            content = response.choices[0].message.parsed

            if not content:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )

            # result = self.transform_message_to_schema(
            #     message=content, schema=TradingResponse
            # )

            # 스키마에 action과 reason 키가 있는지 확인
            if content:
                return content, prompt
            else:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )
        except Exception as e:
            # 에러 발생 시, JSON 스키마 형식으로 에러 메시지 반환
            raise HTTPException(
                status_code=403,
                detail=str(e),
            )

    def transform_message_to_schema(self, message: str, schema: Type[T]) -> T:
        """
        Transforms a message from the OpenAI API into an instance of the specified BaseModel schema.
        """
        # Pydantic 모델 클래스에서 JSON 스키마 정보를 가져옵니다.
        schema_dict = schema.schema()

        prompt = f"""
        Analyze the message below and restructure it to conform to the provided JSON schema.
        Make sure to include all the fields specified in the schema, converting the values to match the defined types and structure.

        Please adhere to the following rules:
        1. The response must be in pure JSON format only. Do not include any additional text or explanation.
        2. Use the exact field names as specified in the schema.
        3. Each field's value must be converted to the data type defined in the schema.
        4. For any information not present in the message, use null or the default value for that type.
        5. Only JSON Format is allowed. (not use codeblock or something.)

        Message:
        {message}

        Schema:
        {json.dumps(schema_dict, ensure_ascii=False, indent=2)}
        """

        client = openai.OpenAI(
            api_key=self.open_api_key,
        )

        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format=schema,
            temperature=0.2,
            top_p=1.0,
            max_tokens=1024,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

        result_str = response.choices[0].message.parsed

        if not result_str:
            raise ValueError("The response is empty. Please provide a valid response.")

        try:
            return result_str
        except json.JSONDecodeError as e:
            raise ValueError(
                "The response is not in valid JSON format. Response: " + str(result_str)
            ) from e

    def analzye_image(self, prompt: str, image_path: str):
        """ """
        # Pydantic 모델 클래스에서 JSON 스키마 정보를 가져옵니다.

        client = openai.OpenAI(
            api_key=self.open_api_key,
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_path,
                            },
                        },
                    ],
                }
            ],
            temperature=0.2,
            top_p=1.0,
            max_tokens=1024,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

        result_str = response.choices[0].message.content

        if not result_str:
            raise ValueError("The response is empty. Please provide a valid response.")

        try:
            return result_str
        except json.JSONDecodeError as e:
            raise ValueError(
                "The response is not in valid JSON format. Response: " + str(result_str)
            ) from e
