# services/ai_service.py
import openai
import json

from myapi.domain.ai.ai_schema import AnalyzeResponseModel
from myapi.utils.config import Settings


class AIService:
    def __init__(self, settings: Settings):
        self.open_api_key = settings.OPENAI_API_KEY

    def generate_trade_summary(
        self,
        information_summary: str | None,
        trade_data: dict,
        market_data: dict,
        decision_reason: str,
    ) -> str:
        """
        투자 거래 데이터, 시장 데이터, 투자 결정 근거를 바탕으로
        투자 요약 보고서를 생성합니다.

        보고서에는 아래 항목들이 포함됩니다:
        1. 투자 결정의 근거 (어떤 근거로 했는지)
        2. 왜 해당 투자를 진행했는지
        3. 앞으로의 투자 전략 및 방향
        4. 투자 과정에서의 반성과 회고를 통한 개선 방안

        :param trade_data: 거래 관련 데이터 (예: 주문 내역, 체결 가격 등)
        :param market_data: 해당 시점의 시장 데이터
        :param decision_reason: AI 혹은 사용자가 제공한 투자 결정 이유
        :return: 생성된 투자 요약 보고서 문자열
        """
        client = openai.OpenAI(
            api_key=self.open_api_key  # This is the default and can be omitted
        )

        prompt = f"""
            당신은 투자 전문가입니다.
            아래 정보를 바탕으로 이번 투자에 대한 종합적인 요약 보고서를 작성하세요.
            
            [투자 데이터]
            {json.dumps(trade_data, ensure_ascii=False, indent=2)}
            
            [시장 데이터]
            {json.dumps(market_data, ensure_ascii=False, indent=2)}
            
            [거래요약]
            {information_summary}
            
            보고서에는 반드시 다음 항목들이 포함되어야 합니다:
            1. 투자 결정의 근거 (어떤 데이터를 근거로 했는지)
            2. 왜 해당 투자를 진행했는지에 대한 설명
            3. 앞으로의 투자 전략 및 방향
            4. 투자 과정에서의 반성과 회고를 통한 개선 방안
            
            종합적이고 명확한 보고서를 작성해주세요.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an investment expert."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        summary = response.choices[0].message.content

        if summary:
            return summary

        return ""

    def analyze_market(self, market_data: dict, technical_indicators: dict):
        """
        OpenAI API(Deepseek R1 모델)를 이용해 시장 분석 후 매매 결정을 받아옵니다.
        결과는 아래 JSON 스키마 형식으로 반환됩니다:

            {
                "action": "BUY" 또는 "SELL",
                "reason": "간단한 설명"
            }
        """
        prompt = f"""
            You are an AI financial assistant specialized in cryptocurrency.
            Analyze the following market data and technical indicators, then provide
            a suggested trading plan in JSON format only, with the fields:
            - "action": one of ["BUY", "SELL", "HOLD"]
            - "stop_loss": number
            - "take_profit": number
            - "position_size_ratio": ratio of capital to allocate (0~1)
            - "reason": short explanation

            Only return valid JSON. No additional text.

            Market Data:
            {json.dumps(market_data, indent=2)}

            Technical Indicators:
            {json.dumps(technical_indicators, indent=2)}
        """
        client = openai.OpenAI(
            api_key=self.open_api_key  # This is the default and can be omitted
        )

        try:

            response = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format=AnalyzeResponseModel,
            )

            # response.choices[0].message.content
            result = response.choices[0].message.parsed

            if not result:
                return AnalyzeResponseModel(
                    action="HOLD", reason="응답 스키마가 올바르지 않습니다."
                )

            # 스키마에 action과 reason 키가 있는지 확인
            if result.action and result.reason:
                return result
            else:
                return AnalyzeResponseModel(
                    action="HOLD", reason="응답 스키마가 올바르지 않습니다."
                )
        except Exception as e:
            # 에러 발생 시, JSON 스키마 형식으로 에러 메시지 반환
            return AnalyzeResponseModel(
                action="HOLD", reason=f"Error occurred: {str(e)}"
            )
