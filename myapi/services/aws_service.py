import os
from fastapi import HTTPException
import boto3
import json

# AWS Secrets Manager 설정 (여러분의 환경에 맞게 수정)
SECRET_NAME = "kakao/tokens"  # 예: "kakao/tokens"
REGION_NAME = "ap-northeast-2"  # 예: "ap-northeast-2"
# boto3 클라이언트 생성


class AwsService:
    @classmethod
    def get_secret(cls) -> dict:
        """
        AWS Secrets Manager에서 secret 값을 읽어와 dict 형태로 반환합니다.
        """
        aws_access_key_id = os.getenv("AWS_S3_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_S3_SECRET_ACCESS_KEY")

        if aws_access_key_id and aws_secret_access_key:
            client = boto3.client(
                "secretsmanager",
                region_name=REGION_NAME,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
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

    @classmethod
    def update_secret(cls, updated_data: dict) -> dict:
        """
        AWS Secrets Manager의 secret 값을 수정(업데이트)합니다.
        """
        try:
            aws_access_key_id = os.getenv("AWS_S3_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_S3_SECRET_ACCESS_KEY")

            if aws_access_key_id and aws_secret_access_key:
                client = boto3.client(
                    "secretsmanager",
                    region_name=REGION_NAME,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
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
