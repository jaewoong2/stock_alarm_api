# ECS Service Auto Scaling Target (비용 최적화)
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 3  # 최대 3개로 제한 (비용 절약)
  min_capacity       = 2  # 최소 2개 유지 (고가용성)
  resource_id        = "service/${aws_ecs_cluster.fastapi.name}/${aws_ecs_service.fastapi.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  tags = local.common_tags
}

# CPU 기반 Auto Scaling 정책
resource "aws_appautoscaling_policy" "ecs_scale_up" {
  name               = "${var.project_name}-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0  # CPU 사용률 70% 초과 시 확장
    scale_in_cooldown  = 300   # 5분
    scale_out_cooldown = 300   # 5분
  }
}

# ALB Request Count 기반 Auto Scaling 정책
resource "aws_appautoscaling_policy" "ecs_scale_requests" {
  name               = "${var.project_name}-scale-requests"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label        = "${data.aws_lb.existing.arn_suffix}/${aws_lb_target_group.fastapi.arn_suffix}"
    }
    target_value       = 1000.0  # 타겟당 1000 요청/분 초과 시 확장
    scale_in_cooldown  = 300
    scale_out_cooldown = 300
  }
}

# 스케줄 기반 Auto Scaling - 비용 최적화 (야간/주말 스케일 다운)
resource "aws_appautoscaling_scheduled_action" "scale_out_business_hours" {
  name               = "${var.project_name}-scale-out-business-hours"
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  schedule           = "cron(0 9 ? * MON-FRI *)"  # 평일 오전 9시 (day-of-month를 ?로 설정)

  scalable_target_action {
    min_capacity = 2  # 평일 업무시간에는 2개 유지
    max_capacity = 3
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_in_off_hours" {
  name               = "${var.project_name}-scale-in-off-hours"
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  schedule           = "cron(0 20 * * ? *)"  # 매일 오후 8시 (day-of-week를 ?로 설정)

  scalable_target_action {
    min_capacity = 1  # 야간/주말에는 1개로 축소 (비용 절약)
    max_capacity = 3
  }
}
