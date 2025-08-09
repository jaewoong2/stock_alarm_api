# Terraform 버전 및 Provider 설정
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS Provider 설정
provider "aws" {
  region  = var.aws_region
  profile = "lime_admin"
}

# 변수 정의
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "tqqq-fastapi"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "prod"
}

variable "vpc_id" {
  description = "Existing VPC ID"
  type        = string
  default     = "vpc-0dd58176a213e3886"
}

variable "public_subnet_ids" {
  description = "Existing public subnet IDs"
  type        = list(string)
  default     = ["subnet-0cd24b3e29f28ed01", "subnet-02314d35d476ded10"]
}

variable "security_group_id" {
  description = "Existing security group ID"
  type        = string
  default     = "sg-0f45e0b0868c2ea7c"
}

variable "domain_name" {
  description = "Domain name for the FastAPI application"
  type        = string
  default     = "ai-api.bamtoly.com"
}

variable "alert_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
  default     = "jwisgenius@naver.com"
}

# 로컬 변수
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Service     = "fastapi"
  }
}
