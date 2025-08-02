# services/ai_service.py
from typing import Any, Dict, Optional, Type, TypeVar
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
import openai
import json

from pydantic import BaseModel

from myapi.domain.ai.ai_schema import ChatModel
from myapi.utils.config import Settings
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

T = TypeVar("T", bound=BaseModel)


class AIService:
    def __init__(self, settings: Settings):
        self.hyperbolic_api_key = settings.HYPERBOLIC_API_KEY
        self.open_api_key = settings.OPENAI_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.huggingface_api_key = settings.HUGGINGFACE_API_KEY
        self.perplexity_api_key = settings.PERPLEXITY_API_KEY
        self.bedrock_api_key = settings.BEDROCK_API_KEY
        self.bedrock_base_url = settings.BEDROCK_BASE_URL

    def perplexity_completion(
        self,
        prompt: str,
        schema: Type[T],
    ):
        client = openai.OpenAI(
            base_url="https://api.perplexity.ai", api_key=self.perplexity_api_key
        )
        response = client.chat.completions.create(
            model="sonar-pro",
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.choices[0].message

        response = self.completions_parse(
            prompt=f"{result.content}\n\nPlease return the result in JSON format.",
            schema=schema,
            system_prompt="You are a helpful assistant Return the result in JSON format.",
            chat_model=ChatModel.GPT_4O_MINI,
            image_url=None,  # 이미지 URL이 필요하지 않다면 None으로 설정
        )

        return response

    def hyperbolic_completion(
        self,
        prompt: str,
    ):
        """
        Hyperbolic API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        client = openai.OpenAI(
            base_url="https://api.hyperbolic.xyz/v1",
            api_key=self.hyperbolic_api_key,
        )

        response = client.chat.completions.create(
            model="meta-llama/Meta-Llama-3-70B-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message

    def hugging_face_completion(self, prompt: str):
        """
        Hugging Face API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        client = openai.OpenAI(
            base_url="https://router.huggingface.co/hf-inference/models/meta-llama/Llama-3.3-70B-Instruct/v1",
            api_key=self.huggingface_api_key,
        )

        completion = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return completion.choices[0].message

    def nova_lite(self, prompt: str):
        """Call AWS Bedrock Nova Lite model using AWS Boto3 Bedrock client."""
        # 프롬프트 길이에 따른 동적 max_tokens 계산
        prompt_length = len(prompt)
        max_tokens = max(512, min(5120, prompt_length * 4))
        return self.nova_lite_with_tokens(prompt, max_tokens)

    def nova_lite_with_tokens(self, prompt: str, max_tokens: int = 5120):
        """Call AWS Bedrock Nova Lite model with custom max_tokens."""
        try:
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name="ap-northeast-2",
            )
            model_id = "apac.amazon.nova-lite-v1:0"

            conversation = [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]

            try:
                # Bedrock 모델 호출
                response = client.converse(
                    modelId=model_id,
                    messages=conversation,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": 0.2,
                    },
                )
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "ValidationException":
                    # 모델 ID가 잘못된 경우 대체 모델 시도
                    try:
                        response = client.converse(
                            modelId=model_id,
                            messages=conversation,
                            inferenceConfig={
                                "maxTokens": max_tokens,
                                "temperature": 0.2,
                            },
                        )
                    except Exception:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Nova model not available: {e}",
                        )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"AWS Bedrock error: {e}",
                    )

            if not response or "output" not in response:
                raise HTTPException(
                    status_code=404,
                    detail="No response body found from Bedrock model.",
                )

            # 응답 파싱 - 안전한 접근
            try:
                completion_content = response["output"]["message"]["content"][0]["text"]
            except (KeyError, IndexError, TypeError) as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Invalid response structure from Bedrock: {e}",
                )

            return completion_content

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Bedrock service error: {str(e)}"
            )

    def nova_lite_completion(self, prompt: str, schema: Type[T]):
        """Call AWS Bedrock Nova Lite model using AWS Boto3 Bedrock client."""
        try:
            # Bedrock Runtime 클라이언트 생성
            client = boto3.client(
                service_name="bedrock-runtime",
                region_name="ap-northeast-2",  # AWS 리전을 적절히 설정하세요
            )
            model_id = "apac.amazon.nova-lite-v1:0"

            prompt = (
                prompt
                + f"\n\n You Need to Response Like Response JSON Format: {json.dumps(schema.model_json_schema())}"
            )

            conversation = [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]

            try:
                # Bedrock 모델 호출
                response = client.converse(
                    modelId=model_id,
                    messages=conversation,
                    inferenceConfig={"maxTokens": 8192},
                )
            except (ClientError, Exception) as e:
                raise HTTPException(
                    status_code=404,
                    detail=f"Model not found: {e}",
                )

            if not response:
                raise HTTPException(
                    status_code=404,
                    detail="No response body found from Bedrock model.",
                )
            # 응답 파싱
            completion_content = response["output"]["message"]["content"][0]["text"]

            if not completion_content:
                raise HTTPException(
                    status_code=404,
                    detail="No content found in the Bedrock model response.",
                )

            # 결과 처리
            result = self.completions_parse(
                prompt=f"{completion_content}",
                schema=schema,
                system_prompt="You are a helpful assistant. Return the result in JSON format.",
                chat_model=ChatModel.GPT_4O_MINI,
                image_url=None,  # 이미지 URL이 필요하지 않다면 None으로 설정
            )

            return result
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Bedrock service error: {e}")

    def gemini_search_grounding(
        self,
        prompt: str,
        schema: Type[T],
    ):
        try:
            client = genai.Client(api_key=self.gemini_api_key)

            google_search_tool = Tool(google_search=GoogleSearch())
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt,
                config=GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                ),
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini service error: {e}")

        result = ""

        if (
            response.candidates
            and response.candidates[0].content
            and hasattr(response.candidates[0].content, "parts")
        ):
            if response.candidates[0].content.parts:
                for each in response.candidates[0].content.parts:
                    if each.text is not None:
                        result += each.text

        result = self.completions_parse(
            prompt="" + result + "\n\nPlease return the result in JSON format.",
            schema=schema,
            system_prompt="You are a helpful assistant. Return the result in JSON format.",
            chat_model=ChatModel.O4_MINI,
            image_url=None,  # 이미지 URL이 필요하지 않다면 None으로 설정
        )

        # Return Type Only Schema
        if not isinstance(result, schema):
            return ""

        return result

    def gemini_completion(
        self,
        prompt: str,
        schema: Type[T],
    ):
        """
        OpenAI API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        try:
            client = genai.Client(api_key=self.gemini_api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            return response.parsed
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini service error: {e}")

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

    def completions_parse(
        self,
        system_prompt: str,
        prompt: str,
        image_url: Optional[str],
        schema: Type[T],
        chat_model: ChatModel = ChatModel.O3_MINI,
    ) -> T:
        """
        Transforms a message from the OpenAI API into an instance of the specified BaseModel schema.
        """

        client = openai.OpenAI(
            api_key=self.open_api_key,
        )

        user_content: Any = [
            {
                "type": "text",
                "text": prompt,
            }
        ]

        if image_url:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                },
            )

        response = client.beta.chat.completions.parse(
            model=chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            response_format=schema,
            frequency_penalty=0.0,  # 반복 억제 정도
            presence_penalty=0.0,  # 새로운 주제 도입 억제
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

    def completion(
        self,
        system_prompt: str,
        prompt: str,
        chat_model: ChatModel = ChatModel.O3_MINI,
    ):
        """
        OpenAI API를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:
        """
        client = openai.OpenAI(
            api_key=self.open_api_key,  # This is the default and can be omitted
        )

        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            top_p=1.0,
        )

        return response.choices[0].message.content
