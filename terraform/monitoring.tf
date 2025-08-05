# CloudWatch 알람 - ECS 서비스 실행 중인 태스크 수 모니터링 (Spot 전용 강화)
resource "aws_cloudwatch_metric_alarm" "ecs_running_task_count" {
  alarm_name          = "${var.project_name}-ecs-running-tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"  # Spot 종료 시 빠른 감지를 위해 1분으로 단축
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"  # 1개 미만 시 즉시 알람
  alarm_description   = "ECS running task count below 1 - Spot interruption detected"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "breaching"  # 데이터 없으면 장애로 간주

  dimensions = {
    ServiceName = aws_ecs_service.fastapi.name
    ClusterName = aws_ecs_cluster.fastapi.name
  }

  tags = local.common_tags
}

# CloudWatch 알람 - 두 태스크 모두 종료 시 긴급 알람
resource "aws_cloudwatch_metric_alarm" "ecs_no_running_tasks" {
  alarm_name          = "${var.project_name}-ecs-no-tasks-critical"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "CRITICAL: No running tasks - Service completely down"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "breaching"

  dimensions = {
    ServiceName = aws_ecs_service.fastapi.name
    ClusterName = aws_ecs_cluster.fastapi.name
  }

  tags = local.common_tags
}

# CloudWatch 알람 - ALB 타겟 헬스 상태 모니터링
resource "aws_cloudwatch_metric_alarm" "alb_target_health" {
  alarm_name          = "${var.project_name}-alb-unhealthy-targets"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors ALB healthy target count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    TargetGroup  = aws_lb_target_group.fastapi.arn_suffix
    LoadBalancer = data.aws_lb.existing.arn_suffix
  }

  tags = local.common_tags
}

# SNS 토픽 - 알람 알림용
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  
  tags = local.common_tags
}

# SNS 토픽 구독 (이메일 알림)
resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # variables.tf에 추가 필요
}

# CloudWatch 대시보드
resource "aws_cloudwatch_dashboard" "fastapi" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "RunningTaskCount", "ServiceName", aws_ecs_service.fastapi.name, "ClusterName", aws_ecs_cluster.fastapi.name],
            [".", "PendingTaskCount", ".", ".", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Task Count"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", aws_lb_target_group.fastapi.arn_suffix, "LoadBalancer", data.aws_lb.existing.arn_suffix],
            [".", "UnHealthyHostCount", ".", ".", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB Target Health"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", data.aws_lb.existing.arn_suffix],
            [".", "ResponseTime", ".", "."],
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB Performance"
          period  = 300
        }
      }
    ]
  })
}
