# 기존 ACM 인증서 참조 (wildcard 인증서 사용)
data "aws_acm_certificate" "fastapi" {
  domain = "*.biizbiiz.com"
}

# Route 53 Hosted Zone (기존 호스트 존 사용)
data "aws_route53_zone" "main" {
  name         = "biizbiiz.com"
  private_zone = false
}

# Route 53 Record for ALB (기존 ALB 참조)
resource "aws_route53_record" "fastapi" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = data.aws_lb.existing.dns_name
    zone_id                = data.aws_lb.existing.zone_id
    evaluate_target_health = true
  }
}
