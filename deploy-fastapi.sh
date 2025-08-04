#!/bin/bash

# 색깔 설정
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# 필요한 변수 설정
AWS_REGION="ap-northeast-2"
AWS_PROFILE="lime_admin"
PROJECT_NAME="tqqq-fastapi"
ECR_REPOSITORY_NAME="tqqq-fastapi-app"
ECS_CLUSTER_NAME="tqqq-fastapi-cluster"
ECS_SERVICE_NAME="tqqq-fastapi-service"

# AWS 계정 ID 가져오기
log "Getting AWS Account ID..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)
if [ $? -ne 0 ]; then
    error "Failed to get AWS Account ID"
    exit 1
fi

ECR_REPOSITORY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME"

log "Starting FastAPI deployment process..."
log "AWS Region: $AWS_REGION"
log "AWS Profile: $AWS_PROFILE"
log "ECR Repository: $ECR_REPOSITORY"
log "ECS Cluster: $ECS_CLUSTER_NAME"
log "ECS Service: $ECS_SERVICE_NAME"

# AWS ECR 로그인
log "Logging in to AWS ECR..."
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | docker login --username AWS --password-stdin $ECR_REPOSITORY
if [ $? -ne 0 ]; then
    error "Failed to login to ECR"
    exit 1
fi

# Docker Compose로 빌드
log "Building Docker image with Docker Compose..."
docker-compose -f docker-compose.fastapi.yaml build
if [ $? -ne 0 ]; then
    error "Failed to build Docker image"
    exit 1
fi

# ECR로 푸쉬
log "Pushing Docker image to ECR..."
docker-compose -f docker-compose.fastapi.yaml push
if [ $? -ne 0 ]; then
    error "Failed to push Docker image to ECR"
    exit 1
fi

# ECS 서비스 업데이트 (서비스가 존재하는 경우)
log "Checking if ECS service exists..."
aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1
if [ $? -eq 0 ]; then
    log "Updating ECS service..."
    aws ecs update-service --cluster $ECS_CLUSTER_NAME --service $ECS_SERVICE_NAME --force-new-deployment --region $AWS_REGION --profile $AWS_PROFILE
    if [ $? -eq 0 ]; then
        log "ECS service update initiated successfully"
        
        # 배포 상태 확인
        log "Waiting for deployment to complete..."
        aws ecs wait services-stable --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION --profile $AWS_PROFILE
        if [ $? -eq 0 ]; then
            log "Deployment completed successfully!"
        else
            warn "Deployment may still be in progress. Check AWS console for details."
        fi
    else
        error "Failed to update ECS service"
        exit 1
    fi
else
    warn "ECS service $ECS_SERVICE_NAME not found in cluster $ECS_CLUSTER_NAME"
    warn "Please deploy the infrastructure first using Terraform"
fi

log "Docker image $ECR_REPOSITORY:latest has been pushed to ECR"
log "FastAPI application should be available at: https://ai-api.bamtoly.com"
log "Deployment process completed!"

# 서비스 상태 확인
log "Checking service status..."
aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' --output table 2>/dev/null || warn "Could not retrieve service status"
