# Application Load Balancer
resource "aws_lb" "fastapi" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false # 개발/테스트 환경이므로 false

  tags = local.common_tags
}

# ALB Target Group
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

# ALB Listener (HTTP) - HTTPS로 리다이렉트
resource "aws_lb_listener" "fastapi_http" {
  load_balancer_arn = aws_lb.fastapi.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = local.common_tags
}

# ALB Listener (HTTPS)
resource "aws_lb_listener" "fastapi_https" {
  load_balancer_arn = aws_lb.fastapi.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = data.aws_acm_certificate.fastapi.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi.arn
  }

  tags = local.common_tags
}
