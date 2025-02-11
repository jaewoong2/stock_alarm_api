#!/bin/bash

# 필요한 변수 설정
AWS_REGION="ap-northeast-2"  # 예: ap-northeast-2
AWS_PROFILE="lime_admin"
ECR_REPOSITORY="849441246713.dkr.ecr.ap-northeast-2.amazonaws.com/stock_alarm"  # 예: 373752144847.dkr.ecr.ap-northeast-2.amazonaws.com/knowlegebase-bedrock-test
LAMBDA_FUNCTION_NAME="stock_alarm_lambda"
# LAMBDA_FUNCTION_URL="https://guqx2yonk5wzcrkzlp2yfp77pm0rdmqx.lambda-url.ap-northeast-2.on.aws"

# AWS ECR 로그인
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | docker login --username AWS --password-stdin $ECR_REPOSITORY

# Docker Compose로 빌드
docker-compose build

# ECR로 푸쉬
docker-compose push

IMAGE_NAME="$ECR_REPOSITORY:latest"


aws lambda update-function-code --function-name $LAMBDA_FUNCTION_NAME --image-uri $IMAGE_NAME --region $AWS_REGION

echo "Docker image $IMAGE_NAME has been pushed to ECR and Lambda function $LAMBDA_FUNCTION_NAME has been updated"
echo "Lambda function URL: $LAMBDA_FUNCTION_URL"

