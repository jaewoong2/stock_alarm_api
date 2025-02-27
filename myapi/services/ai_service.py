# services/ai_service.py
from typing import Type, TypeVar
from fastapi import HTTPException
import openai
import json

from pydantic import BaseModel

from myapi.domain.ai.ai_schema import TradingResponse
from myapi.domain.ai.const import generate_prompt
from myapi.utils.config import Settings

# T는 BaseModel을 상속하는 타입이어야 합니다.
T = TypeVar("T", bound=BaseModel)


class AIService:
    def __init__(self, settings: Settings):
        self.hyperbolic_api_key = settings.HYPERBOLIC_API_KEY
        self.open_api_key = settings.OPENAI_API_KEY

    def analyze_market(
        self,
        market_data: dict,
        technical_indicators: dict,
        previous_trade_info: str,
        balances_data: dict,
        orderbook_data: dict,
        sentiment_data: dict,
        current_active_orders: dict,
        news_data: dict,
        quote_currency: str = "KRW",
        target_currency: str = "BTC",
        additional_context: str = "",
    ):
        """
        OpenAI API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        prompt = generate_prompt(
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
            additional_context=additional_context,
        )

        client = openai.OpenAI(
            base_url="https://api.hyperbolic.xyz/v1",
            api_key=self.hyperbolic_api_key,  # This is the default and can be omitted
        )

        try:
            response = client.chat.completions.create(
                model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # 창의성과 응답의 다양성 조절 (0~1)
                top_p=0.5,  # nucleus sampling 조절
                frequency_penalty=0.0,  # 반복 억제 정도
                presence_penalty=0.0,  # 새로운 주제 도입 억제
                max_tokens=1024,  # 최대 토큰 길이
            )
            # response.choices[0].message.content
            content = response.choices[0].message.content

            if not content:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )

            result = self.transform_message_to_schema(
                message=content, schema=TradingResponse
            )

            if not result:
                raise HTTPException(
                    status_code=403,
                    detail="응답 스키마가 올바르지 않습니다.",
                )

            # 스키마에 action과 reason 키가 있는지 확인
            if result.action:
                return result, prompt
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
        6. If Action Is Cancel, Order_id Is Required, (If order_id is not existed, Cancle Actions is not allowed)

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
            temperature=0.2,
            response_format=schema,
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
