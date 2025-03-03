import os
from fastapi import HTTPException
import boto3
import json

from myapi.utils.config import Settings

# AWS Secrets Manager 설정 (여러분의 환경에 맞게 수정)
SECRET_NAME = "kakao/tokens"  # 예: "kakao/tokens"
REGION_NAME = "ap-northeast-2"  # 예: "ap-northeast-2"
# boto3 클라이언트 생성


class AwsService:
    def __init__(self, settings: Settings):
        self.aws_access_key_id = settings.AWS_S3_ACCESS_KEY_ID
        self.aws_secret_access_key = settings.AWS_S3_SECRET_ACCESS_KEY

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
