import os
from typing import Any, Optional
from fastapi import HTTPException
import boto3
import json

from myapi.utils.config import Settings
from myapi.utils.indicators import plot_with_indicators

# AWS Secrets Manager 설정 (여러분의 환경에 맞게 수정)
SECRET_NAME = "kakao/tokens"  # 예: "kakao/tokens"
REGION_NAME = "ap-northeast-2"  # 예: "ap-northeast-2"
# boto3 클라이언트 생성


class AwsService:
    def __init__(self, settings: Settings):
        self.aws_access_key_id = settings.AWS_S3_ACCESS_KEY_ID
        self.aws_secret_access_key = settings.AWS_S3_SECRET_ACCESS_KEY
        self.cloudfront_url = "https://d3u9eh8c3uxxfx.cloudfront.net"

    def get_secret(self) -> dict:
        """
        AWS Secrets Manager에서 secret 값을 읽어와 dict 형태로 반환합니다.
        """

        if self.aws_access_key_id and self.aws_secret_access_key:
            client = boto3.client(
                "secretsmanager",
                region_name=REGION_NAME,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        else:
            client = boto3.client(
                "secretsmanager",
                region_name=REGION_NAME,
            )

        try:
            response = client.get_secret_value(SecretId=SECRET_NAME)
            secret_string = response.get("SecretString")

            if secret_string:
                return json.loads(secret_string)

            return {}
        except client.exceptions.ResourceNotFoundException:
            raise HTTPException(status_code=404, detail="Secret not found")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error retrieving secret: {str(e)}"
            )

    def update_secret(self, updated_data: dict) -> dict:
        """
        AWS Secrets Manager의 secret 값을 수정(업데이트)합니다.
        """
        try:

            if self.aws_access_key_id and self.aws_secret_access_key:
                client = boto3.client(
                    "secretsmanager",
                    region_name=REGION_NAME,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                )
            else:
                client = boto3.client(
                    "secretsmanager",
                    region_name=REGION_NAME,
                )

            response = client.put_secret_value(
                SecretId=SECRET_NAME, SecretString=json.dumps(updated_data)
            )
            return response
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error updating secret: {str(e)}"
            )

    def upload_s3(
        self, bucket_name: str, object_key: str, fileobj: Any, content_type: str
    ):
        s3 = boto3.client(
            "s3",
            region_name=REGION_NAME,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

        return s3.upload_fileobj(
            fileobj, bucket_name, object_key, ExtraArgs={"ContentType": content_type}
        )

    def send_sqs_message(
        self,
        queue_url: str,
        message_body: str,
        delay_seconds: int = 0,
    ) -> dict:
        """
        AWS SQS 큐에 메시지를 전송합니다.

        Args:
            queue_url (str): SQS 큐의 URL
            message_body (str): 전송할 메시지 본문
            message_attributes (dict, optional): 메시지 속성. 기본값은 None
            delay_seconds (int, optional): 메시지 전송 지연 시간(초). 기본값은 0

        Returns:
            dict: SQS 서비스의 응답 데이터

        Raises:
            HTTPException: SQS 메시지 전송 중 오류 발생 시
        """
        try:
            sqs = boto3.client(
                "sqs",
                region_name=REGION_NAME,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )

            params = {"QueueUrl": queue_url, "MessageBody": message_body}

            if delay_seconds > 0:
                params["DelaySeconds"] = str(delay_seconds)

            response = sqs.send_message(**params)
            return response

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error sending message to SQS: {str(e)}"
            )
