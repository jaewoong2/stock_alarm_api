# 기존 ALB 참조 (stock-predict-alb)
data "aws_lb" "existing" {
  arn = "arn:aws:elasticloadbalancing:ap-northeast-2:849441246713:loadbalancer/app/stock-predict-alb/1cb0a5b73300b7aa"
}

# 기존 HTTPS 리스너 참조
data "aws_lb_listener" "existing_https" {
  load_balancer_arn = data.aws_lb.existing.arn
  port              = 443
}

# FastAPI용 Target Group (기존에 생성된 것 재사용)
resource "aws_lb_target_group" "fastapi" {
  name        = "${var.project_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  tags = local.common_tags
}

# 기존 HTTP 리스너 참조
data "aws_lb_listener" "existing_http" {
  load_balancer_arn = data.aws_lb.existing.arn
  port              = 80
}

# 기존 HTTPS 리스너에 ai-api.bamtoly.com 규칙 추가
resource "aws_lb_listener_rule" "fastapi_api" {
  listener_arn = data.aws_lb_listener.existing_https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi.arn
  }

  condition {
    host_header {
      values = ["ai-api.bamtoly.com"]
    }
  }

  tags = local.common_tags
}

# HTTP 리스너에 ai-api.bamtoly.com용 HTTPS 리다이렉션 규칙 추가
resource "aws_lb_listener_rule" "fastapi_http_redirect" {
  listener_arn = data.aws_lb_listener.existing_http.arn
  priority     = 100

  action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  condition {
    host_header {
      values = ["ai-api.bamtoly.com"]
    }
  }

  tags = local.common_tags
}
