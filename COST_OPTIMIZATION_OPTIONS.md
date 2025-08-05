# 비용 최적화된 대안 구성 (Smart Spot Strategy)

## 옵션 A: 하이브리드 Spot 전략 (추천)
```terraform
# ECS 서비스에서 더 많은 Spot 비중
capacity_provider_strategy {
  capacity_provider = "FARGATE"      # On-Demand 최소 보장
  weight            = 1
  base              = 1              # 최소 1개만 On-Demand
}

capacity_provider_strategy {
  capacity_provider = "FARGATE_SPOT" # 나머지는 모두 Spot
  weight            = 4              # Spot 비중 높임
  base              = 0
}

# 스케줄링으로 야간에는 Spot만 사용
# 오전 9시-오후 8시: On-Demand 1개 + Spot 1개
# 오후 8시-오전 9시: Spot 1개만 (위험 감수)
```

## 옵션 B: 풀 Spot + Circuit Breaker (저비용 고위험)
```terraform
# 모든 태스크를 Spot으로 실행하되 장애 대응 강화
capacity_provider_strategy {
  capacity_provider = "FARGATE_SPOT"
  weight            = 100
  base              = 2
}

# 강화된 헬스체크와 자동 복구
deployment_configuration {
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  maximum_percent         = 300  # 빠른 복구를 위해 높게 설정
  minimum_healthy_percent = 0    # 긴급 시 모든 태스크 교체 허용
}
```

## 월별 비용 비교:

### 기존 (1개 Spot):
- **$6.22/월**

### 새로운 구성 (하이브리드):
- **주간 (평일 9-20시):** On-Demand 1개 + Spot 1개 = $26.95/월
- **야간/주말 (80% 시간):** Spot 1개 = $6.22/월
- **가중 평균:** 약 **$12-15/월**

### Smart Spot 구성:
- **주간:** On-Demand 1개 + Spot 1개 = 20% 시간
- **야간:** Spot 1개 = 80% 시간  
- **월 예상 비용:** 약 **$8-10/월**

## 위험 vs 비용 매트릭스:

| 구성 | 월 비용 | 가용성 위험 | 권장도 |
|------|---------|-------------|--------|
| 기존 (1 Spot) | $6 | 높음 | ❌ |
| 풀 Spot (2개) | $12 | 중간 | ⚠️ |
| 하이브리드 | $15 | 낮음 | ✅ |
| 풀 On-Demand | $41 | 매우 낮음 | 💰 |
