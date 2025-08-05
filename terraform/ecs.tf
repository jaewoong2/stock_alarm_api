# ECS 클러스터
resource "aws_ecs_cluster" "fastapi" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # 비용 절약을 위해 비활성화
  }

  tags = local.common_tags
}

# ECS 클러스터 Capacity Provider (Spot 전용 - 비용 최적화)
resource "aws_ecs_cluster_capacity_providers" "fastapi" {
  cluster_name = aws_ecs_cluster.fastapi.name

  capacity_providers = ["FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 2    # 기본 2개 Spot 인스턴스
    weight            = 100
    capacity_provider = "FARGATE_SPOT"
  }
}

# CloudWatch 로그 그룹
resource "aws_cloudwatch_log_group" "fastapi" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7 # 비용 절약을 위해 7일만 보관

  tags = local.common_tags
}

# ECS Task Definition
resource "aws_ecs_task_definition" "fastapi" {
  family                   = "${var.project_name}-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"  # FastAPI용 적당한 스펙
  memory                   = "1024" # FastAPI용 적당한 스펙
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-container"
      image     = "${aws_ecr_repository.fastapi.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "PORT"
          value = "8000"
        },
        {
          name  = "HOST"
          value = "0.0.0.0"
        },
        {
          name  = "DEPLOYMENT_TYPE"
          value = "ecs"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.fastapi.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command = [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = local.common_tags
}

# ECS Service
resource "aws_ecs_service" "fastapi" {
  name            = "${var.project_name}-service"
  cluster         = aws_ecs_cluster.fastapi.id
  task_definition = aws_ecs_task_definition.fastapi.arn
  desired_count   = 2 # Spot 2개로 고가용성 확보

  # Spot 전용 전략 (비용 최적화)
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 100
    base              = 2    # 2개 모두 Spot
  }

  # 서비스 재시작 정책
  enable_execute_command = false

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.fastapi.arn
    container_name   = "${var.project_name}-container"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener_rule.fastapi_api]

  tags = local.common_tags
}
