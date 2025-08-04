# TQQQ FastAPI Infrastructure

이 디렉토리는 TQQQ FastAPI 애플리케이션을 AWS ECS에 배포하기 위한 Terraform 인프라스트럭처 코드를 포함합니다.

## 🏗️ 인프라스트럭처 구성

- **ECS Fargate Spot**: 비용 효율적인 컨테이너 실행
- **Application Load Balancer**: HTTPS 트래픽 분산
- **ECR**: Docker 이미지 저장소
- **Route 53**: DNS 설정 (ai-api.bamtoly.com)
- **ACM**: SSL/TLS 인증서
- **CloudWatch**: 로그 관리

## 🚀 배포 방법

### 1. 사전 준비

```bash
# AWS CLI 설정 확인
aws configure list --profile lime_admin

# Terraform 초기화
terraform init
```

### 2. 인프라스트럭처 배포

```bash
# terraform.tfvars 파일 생성
cp terraform.tfvars.example terraform.tfvars

# 배포 계획 확인
terraform plan

# 인프라스트럭처 배포
terraform apply
```

### 3. 애플리케이션 배포

```bash
# 루트 디렉토리에서 실행
cd ..
chmod +x deploy-fastapi.sh
./deploy-fastapi.sh
```

## 📁 파일 구조

```
terraform-fastapi/
├── variables.tf      # 변수 정의
├── ecs.tf           # ECS 클러스터, 태스크, 서비스
├── alb.tf           # Application Load Balancer
├── ecr.tf           # Elastic Container Registry
├── iam.tf           # IAM 역할 및 정책
├── ssl-dns.tf       # SSL 인증서 및 DNS 설정
├── outputs.tf       # 출력 값
└── README.md        # 이 파일
```

## 🔧 주요 설정

- **도메인**: ai-api.bamtoly.com
- **포트**: 8000 (FastAPI 기본 포트)
- **헬스체크**: `/health` 엔드포인트
- **리소스**: CPU 512, Memory 1024MB
- **스팟 인스턴스**: 비용 절약을 위해 Fargate Spot 사용

## 🏥 헬스체크

FastAPI 애플리케이션에 다음 헬스체크 엔드포인트가 필요합니다:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

## 🗑️ 리소스 정리

```bash
# 인프라스트럭처 삭제
terraform destroy
```

## 📋 참고사항

- 기존 VPC, Subnet, Security Group을 재사용합니다
- 와일드카드 SSL 인증서 (*.bamtoly.com)를 사용합니다
- Fargate Spot을 사용하여 비용을 절약합니다
- CloudWatch 로그는 7일간 보관됩니다
