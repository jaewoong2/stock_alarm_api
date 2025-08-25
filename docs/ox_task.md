# 미국주식 O/X 예측 서비스 - 작업 계획

## 1. 프로젝트 개요

### 1.1 목표

미국 주식 O/X 예측 서비스의 MVP 구현 완료

### 1.2 마일스톤

- **Phase 1**: 기본 인프라 및 인증 시스템 (Week 1-2)
- **Phase 2**: 예측 및 정산 핵심 기능 (Week 3-4)  
- **Phase 3**: 포인트 및 리워드 시스템 (Week 5-6)
- **Phase 4**: 모니터링 및 운영 도구 (Week 7-8)
- **Phase 5**: 테스트 및 배포 준비 (Week 9-10)

### 1.3 핵심 원칙

- **신뢰성**: 포인트는 금전적 가치가 있으므로 데이터 정합성 최우선
- **단순성**: MVP에서는 복잡한 패턴보다 검증된 단순한 방식 선택
- **모니터링**: 비즈니스 지표 및 운영 지표 실시간 추적

## 2. Phase 1: 기본 인프라 및 인증 시스템

### 2.1 프로젝트 초기 설정

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 높음

#### 작업 내용

- [ ] **2.1.1** FastAPI 프로젝트 구조 설정

  - `myapi/` 디렉토리 구조 정리
  - `requirements.txt` 업데이트 (FastAPI, SQLAlchemy, psycopg2, boto3, httpx 등)
  - `.env.example` 파일 생성
  - `docker-compose.yaml` PostgreSQL 설정 추가
  - 로컬 개발환경 설정 스크립트

- [ ] **2.1.2** 환경 설정 및 Configuration

  - `myapi/utils/config.py` 개선
  - Pydantic Settings 클래스 구현
  - 환경별 설정 분리 (development, staging, production)
  - OAuth 및 EOD API 설정

- [ ] **2.1.3** 로깅 및 미들웨어 설정
  - 구조화된 로깅 설정 (JSON 포맷)
  - CORS 미들웨어 설정
  - 요청/응답 로깅 미들웨어

#### 완료 기준

- FastAPI 서버가 정상적으로 시작됨
- Health check 엔드포인트 응답
- 환경변수 로딩 확인

### 2.2 데이터베이스 스키마 구축

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **2.2.1** PostgreSQL 스키마 생성 (crypto 스키마만 사용)

  - `crypto` 스키마 생성
  - ENUM 타입 정의 (`phase`, `choice`, `outcome`, `hold_status`, `redemption_status` 등)

- [ ] **2.2.2** 핵심 테이블 생성 (crypto 스키마 내)

  - `crypto.users` - 사용자 정보 (OAuth 지원)
  - `crypto.oauth_states` - OAuth 상태 관리
  - `crypto.session_control` - 세션 관리
  - `crypto.active_universe` - 활성 종목
  - `crypto.predictions` - 예측 데이터
  - `crypto.settlements` - 정산 결과
  - `crypto.eod_prices` - EOD 가격 데이터

- [ ] **2.2.3** 포인트 및 리워드 테이블 (crypto 스키마 내)

  - `crypto.points_ledger` - 포인트 원장
  - `crypto.points_holds` - 포인트 보류
  - `crypto.rewards_inventory` - 리워드 인벤토리
  - `crypto.rewards_redemptions` - 리워드 교환

- [ ] **2.2.4** 보조 테이블 및 인덱스
  - `crypto.user_limits` - 사용자 제한
  - `crypto.ad_unlocks` - 광고 해제 이력
  - `crypto.rate_limits` - 레이트 리밋
  - `crypto.audit_logs` - 감사 로그 (포인트 관련)
  - `crypto.system_health` - 시스템 헬스 체크
  - 성능 최적화 인덱스 생성
  - 데이터 정합성 검증 함수

#### 완료 기준

- 모든 테이블이 정상 생성됨
- 외래키 제약조건 동작 확인
- 인덱스 성능 테스트 통과

### 2.3 SQLAlchemy 모델 정의

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 높음

#### 작업 내용

- [ ] **2.3.1** 기본 모델 클래스 구현 (crypto 스키마 기반)

  - `myapi/domain/user/user_models.py` (OAuth 지원)
  - `myapi/domain/session/session_models.py`
  - `myapi/domain/prediction/prediction_models.py`

- [ ] **2.3.2** 포인트 및 리워드 모델 (crypto 스키마 내)

  - `myapi/domain/points/points_models.py`
  - `myapi/domain/rewards/rewards_models.py`

- [ ] **2.3.3** 데이터베이스 연결 설정
  - `myapi/database.py` 개선
  - Connection Pool 설정
  - 트랜잭션 관리 유틸리티

#### 완료 기준

- 모든 모델이 정의됨
- 관계(Relationship) 매핑 정상 동작
- CRUD 기본 테스트 통과

### 2.4 인증 시스템 구현 (OAuth 지원)

**담당자**: Backend Developer  
**예상 시간**: 3일  
**우선순위**: 높음

#### 작업 내용

- [ ] **2.4.1** JWT 토큰 관리

  - RS256 알고리즘 키 페어 생성
  - JWT 토큰 생성/검증 함수
  - 토큰 만료 처리

- [ ] **2.4.2** 일반 인증 라우터 구현

  - `myapi/routers/auth_router.py` 개선
  - 회원가입 API (`POST /v1/auth/signup`)
  - 로그인 API (`POST /v1/auth/login`)

- [ ] **2.4.3** OAuth 인증 구현

  - Google OAuth 설정
  - OAuth state 관리 (`crypto.oauth_states`)
  - OAuth 로그인 API (`GET /v1/auth/oauth/google`)
  - OAuth 콜백 API (`POST /v1/auth/oauth/callback`)
  - 사용자 정보 연동 및 자동 회원가입

- [ ] **2.4.4** 사용자 관리 라우터

  - `myapi/routers/user_router.py` 신규 생성
  - 사용자 정보 조회 (`GET /v1/users/me`)
  - OAuth 제공업체 정보 포함

- [ ] **2.4.5** 인증 미들웨어
  - JWT 토큰 검증 의존성
  - 현재 사용자 정보 추출
  - OAuth/일반 사용자 구분 처리

#### 완료 기준

- 일반 회원가입/로그인 정상 동작
- Google OAuth 로그인 정상 동작
- JWT 토큰 검증 정상 동작
- 인증이 필요한 API 보호 확인

## 3. Phase 2: 예측 및 정산 핵심 기능

### 3.1 세션 관리 시스템 (단순화)

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 높음

#### 작업 내용

- [ ] **3.1.1** 단순화된 세션 서비스 구현

  - `myapi/services/session_service.py` 생성
  - 3단계 세션 상태 관리 (OPEN/CLOSED/SETTLING)
  - UTC 기반 시간 처리, API 응답시에만 KST 변환
  - 복잡한 2-Phase 로직 제거

- [ ] **3.1.2** 세션 라우터 구현

  - `myapi/routers/session_router.py` 생성
  - `GET /v1/session/today` - 단순한 세션 상태 조회
  - `POST /internal/session/transition` - 세션 전환 (통합 API)

- [ ] **3.1.3** 단순화된 배치 스케줄러
  - 3개 배치로 통합 (종목선정+세션전환, 예측마감, EOD+정산)
  - 복잡한 의존성 제거

#### 완료 기준

- 세션 상태 조회 API 정상 동작
- 단순화된 세션 전환 로직 정상 동작
- UTC/KST 시간 변환 정확성 확인

### 3.2 종목 유니버스 관리

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 높음

#### 작업 내용

- [ ] **3.2.1** 유니버스 서비스 구현

  - `myapi/services/universe_service.py` 생성
  - 오늘의 종목 목록 조회
  - 종목 목록 업데이트 (관리자)

- [ ] **3.2.2** 유니버스 라우터 구현

  - `myapi/routers/universe_router.py` 생성
  - `GET /v1/universe/today` - 오늘의 종목
  - `POST /internal/universe/upsert` - 종목 업데이트

- [ ] **3.2.3** 기본 종목 데이터 시드
  - 인기 미국 주식 10개 선정 (AAPL, MSFT, GOOGL 등)
  - 테스트용 종목 데이터 삽입

#### 완료 기준

- 종목 목록 조회 API 정상 동작
- 종목 업데이트 API 정상 동작
- 시드 데이터 삽입 확인

### 3.3 예측 제출 시스템 (단순화)

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **3.3.1** 단순화된 예측 검증 로직

  - 세션 상태 확인 (OPEN 상태만 허용)
  - 종목 유니버스 포함 여부 확인
  - 중복 예측 방지

- [ ] **3.3.2** 단순화된 사용자 제한 관리

  - 일일 예측 횟수만 체크 (기본 3회)
  - 복잡한 슬롯/쿨다운 시스템 제거
  - `crypto.user_daily_stats` 테이블 활용

- [ ] **3.3.3** 예측 서비스 구현

  - `myapi/services/prediction_service.py` 생성
  - 단순화된 예측 제출 로직
  - 기본적인 제약 조건 검증만

- [ ] **3.3.4** 예측 라우터 구현
  - `myapi/routers/prediction_router.py` 생성
  - `POST /v1/predictions/{symbol}` - 예측 제출
  - 멱등성 키 지원
  - 에러 처리 및 응답

#### 완료 기준

- 예측 제출 API 정상 동작
- 단순화된 제약 조건 검증 통과
- 에러 케이스 적절히 처리

### 3.4 메시지 큐 및 배치 워커 (단순화)

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 높음

#### 작업 내용

- [ ] **3.4.1** 필수 SQS 큐 생성 (최소화)

  - `q.eod.fetch` - EOD 데이터 수집
  - `q.settlement.compute` - 정산 컴퓨트
  - `q.points.award` - 포인트 지급 (Standard 큐로 단순화)

- [ ] **3.4.2** SQS 클라이언트 구현

  - `myapi/services/aws_service.py` 개선
  - 메시지 발행 유틸리티 (직접 발행, 아웃박스 패턴 제거)
  - 메시지 수신 유틸리티
  - DLQ 설정 및 재시도 로직

- [ ] **3.4.3** 기본 워커 구현
  - EOD 데이터 수집 워커
  - 정산 워커
  - 포인트 지급 워커
  - 워커 헬스 체크

#### 완료 기준

- SQS 큐 정상 생성 및 설정
- 메시지 발행/수신 정상 동작
- 워커 실행 및 처리 확인

### 3.5 EOD 데이터 수집 및 정산 (배치 방식)

**담당자**: Backend Developer  
**예상 시간**: 4일  
**우선순위**: 높음

#### 작업 내용

- [ ] **3.5.1** EOD 데이터 수집 서비스

  - `myapi/services/eod_service.py` 생성
  - Alpha Vantage API 클라이언트
  - Yahoo Finance API 클라이언트 (백업)
  - `crypto.eod_prices` 테이블 저장
  - `crypto.eod_fetch_logs` 로깅

- [ ] **3.5.2** EOD 배치 라우터

  - `myapi/routers/internal_router.py` 업데이트
  - `POST /internal/eod/fetch` - EOD 데이터 수집 트리거
  - 배치 상태 조회 API

- [ ] **3.5.3** EOD 배치 워커 구현

  - SQS `q.eod.fetch` 처리
  - 재시도 로직 및 실패 처리
  - 성공시 정산 컴퓨트 트리거

- [ ] **3.5.4** 단순화된 정산 서비스 구현

  - `myapi/services/settlement_service.py` 생성
  - 명확한 상승/하락/무효 판정 로직 (±0.01% 기준)
  - 정산 결과 저장 (멱등성 보장)
  - 데이터 정합성 검증 (예측 vs 정산)
  - 직접 포인트 지급 (즉시 처리)

- [ ] **3.5.5** 정산 워커 구현

  - 정산 컴퓨트 워커
  - 트랜잭션 격리 수준 관리
  - 동시성 제어 (FOR UPDATE)

- [ ] **3.5.6** 정산 라우터 구현
  - `myapi/routers/settlement_router.py` 생성
  - `GET /v1/settlements/{trading_day}` - 정산 결과 조회
  - `POST /internal/settlement/run` - 수동 정산 실행

#### 완료 기준

- EOD 데이터 수집 배치 정상 동작
- 정산 로직 정확성 검증
- 정산 결과 API 정상 응답

### 3.6 배치 스케줄링 설정

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 중간

#### 작업 내용

- [ ] **3.6.1** EventBridge 스케줄 설정

  - 일일 배치 스케줄 설정 (KST 기준)
  - EOD 데이터 수집 (06:15)
  - 정산 실행 (06:30)
  - 세션 전환 (06:00, 22:25)

- [ ] **3.6.2** 배치 모니터링
  - 배치 실행 상태 추적
  - 실패시 알림 설정

#### 완료 기준

- 스케줄링 정상 동작
- 배치 모니터링 확인

## 4. Phase 3: 포인트 및 리워드 시스템

### 4.1 포인트 시스템 구현

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **4.1.1** 단순화된 포인트 서비스 구현

  - `myapi/services/points_service.py` 생성
  - 포인트 잔액 조회 (`crypto.points_ledger` 기반)
  - 포인트 원장 조회 (페이징)
  - 즉시 포인트 지급/차감 (보류 시스템 제거)
  - 포인트 총합 검증 함수 (데이터 정합성)
  - 감사 로그 기록 (`crypto.audit_logs`)

- [ ] **4.1.2** 포인트 지급 워커

  - 정산 결과 기반 포인트 계산
  - 승리시 포인트 지급
  - 패배/무효시 처리
  - Advisory Lock 동시성 제어

- [ ] **4.1.3** 포인트 라우터 구현
  - `myapi/routers/points_router.py` 생성
  - `GET /v1/points/balance` - 잔액 조회
  - `GET /v1/points/ledger` - 내역 조회

#### 완료 기준

- 포인트 잔액 조회 정상 동작
- 포인트 지급 로직 정확성 검증
- 멱등성 보장 확인

### 4.2 리워드 시스템 구현 (단순화)

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 중간

#### 작업 내용

- [ ] **4.2.1** 리워드 인벤토리 관리

  - `myapi/services/rewards_service.py` 생성
  - 리워드 카탈로그 조회 (`crypto.rewards_inventory`)
  - 재고 관리 (reserved 필드)

- [ ] **4.2.2** 단순화된 리워드 교환

  - 즉시 포인트 차감 + 리워드 발급 요청
  - 실패시 즉시 포인트 환불 (복잡한 보류 시스템 제거)
  - 외부 벤더 발급 요청 (모의)
  - 트랜잭션 기반 롤백 처리

- [ ] **4.2.3** 리워드 라우터 구현
  - `myapi/routers/rewards_router.py` 생성
  - `GET /v1/rewards/catalog` - 카탈로그 조회
  - `POST /v1/rewards/redeem` - 리워드 교환

#### 완료 기준

- 리워드 카탈로그 조회 정상 동작
- 리워드 교환 정상 처리
- 트랜잭션 롤백 테스트 통과

### 4.3 데이터 정합성 및 백업 시스템

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **4.3.1** 데이터 정합성 검증

  - 포인트 총합 검증 스크립트
  - 예측 vs 정산 데이터 일치성 검증
  - 일일 정합성 체크 배치
  - 이상 감지시 알람 발송

- [ ] **4.3.2** 데이터베이스 백업 전략

  - PostgreSQL WAL 백업 설정
  - Point-in-time recovery 설정
  - 일일/주간 백업 스케줄
  - 백업 복구 테스트 절차

- [ ] **4.3.3** 감사 로그 시스템
  - 모든 포인트 관련 작업 로깅
  - 관리자 작업 로깅
  - 로그 검색 및 분석 도구

#### 완료 기준

- 정합성 검증 스크립트 정상 동작
- 백업/복구 테스트 통과
- 감사 로그 정상 기록

## 5. Phase 4: 모니터링 및 운영 도구

### 5.1 비즈니스 메트릭 모니터링

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **5.1.1** 비즈니스 지표 수집

  - 일일 활성 사용자 (DAU)
  - 예측 참여율 및 승률
  - 포인트 지급/사용 통계
  - 리워드 교환 통계

- [ ] **5.1.2** 메트릭 대시보드 API

  - `myapi/routers/metrics_router.py` 생성
  - `GET /v1/metrics/daily` - 일일 지표
  - `GET /v1/metrics/predictions` - 예측 관련 지표
  - `GET /v1/metrics/points` - 포인트 관련 지표

- [ ] **5.1.3** 알람 설정
  - 예측 참여율 급락 알람
  - 포인트 지급 이상 감지
  - 시스템 오류율 임계치 알람
  - 배치 작업 실패 알람

#### 완료 기준

- 비즈니스 지표 정상 수집
- 대시보드 API 정상 응답
- 알람 정책 정상 동작

### 5.2 레이트 리밋 시스템

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 중간

#### 작업 내용

- [ ] **5.2.1** 기본 레이트 리밋 정책

  - 예측 제출: 분당 5회, 시간당 30회
  - 포인트 조회: 분당 20회
  - 전체 API: IP당 분당 100회

- [ ] **5.2.2** 레이트 리밋 서비스

  - `myapi/services/rate_limit_service.py` 생성
  - 슬라이딩 윈도우 알고리즘
  - IP/사용자별 제한

- [ ] **5.2.3** 레이트 리밋 미들웨어
  - FastAPI 미들웨어 구현
  - 429 응답 처리
  - 헤더 정보 제공

#### 완료 기준

- 레이트 리밋 정상 동작
- 429 응답 적절히 반환
- 성능 영향 최소화 확인

### 5.3 관리자 도구

**담당자**: Backend Developer  
**예상 시간**: 3일  
**우선순위**: 중간

#### 작업 내용

- [ ] **5.3.1** 관리자 인증

  - 관리자 권한 모델
  - 관리자 JWT 토큰 (별도 시크릿)

- [ ] **5.3.2** 관리자 대시보드 API

  - `myapi/routers/admin_router.py` 생성
  - `GET /admin/dashboard` - 주요 지표 요약
  - `GET /admin/health` - 시스템 헬스 체크
  - `GET /admin/audit` - 감사 로그 조회

- [ ] **5.3.3** 관리자 운영 도구
  - `POST /admin/universe/upsert` - 종목 관리
  - `POST /admin/rewards/inventory` - 리워드 관리  
  - `POST /admin/users/adjust-points` - 포인트 조정
  - `POST /admin/settlement/manual` - 수동 정산
  - `POST /admin/eod/trigger` - EOD 수집 수동 실행
  - `POST /admin/maintenance/integrity-check` - 정합성 검증

#### 완료 기준

- 관리자 인증 정상 동작
- 대시보드 API 정상 응답
- 운영 도구 정상 동작

### 5.4 광고 시청 시스템

**담당자**: Backend Developer  
**예상 시간**: 1일  
**우선순위**: 매우 낮음 (MVP에서 제거 고려)

#### 작업 내용
- [ ] **5.4.1** 
  - 광고 시청시 +1 예측 기회 (일일 최대 1회)
  - 복잡한 쿨다운 제거
  - 서버 검증 최소화

#### 완료 기준

- **권장**: 이 기능 자체를 Phase 2로 연기

## 6. Phase 5: 테스트 및 배포 준비

### 6.1 단위 테스트

**담당자**: Backend Developer  
**예상 시간**: 3일  
**우선순위**: 높음

#### 작업 내용

- [ ] **6.1.1** 서비스 레이어 테스트

  - 예측 서비스 테스트
  - 정산 서비스 테스트  
  - 포인트 서비스 테스트 (정합성 검증 포함)
  - 리워드 서비스 테스트
  - EOD 서비스 테스트

- [ ] **6.1.2** API 레이어 테스트

  - 인증 API 테스트 (OAuth 포함)
  - 예측 API 테스트
  - 포인트 API 테스트
  - 강화된 레이트 리밋 테스트
  - 에러 케이스 테스트

- [ ] **6.1.3** 데이터베이스 테스트
  - 멱등성 테스트
  - 트랜잭션 격리 테스트
  - 동시성 테스트
  - 데이터 정합성 테스트

#### 완료 기준

- 테스트 커버리지 85% 이상
- 모든 핵심 로직 테스트 통과
- 정합성 검증 테스트 통과
- CI/CD 파이프라인 통합

### 6.2 통합 테스트

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **6.2.1** End-to-End 시나리오 테스트

  - 사용자 가입(OAuth) → 예측 → 정산 → 포인트 지급
  - 리워드 교환 플로우
  - 광고 시청 플로우 (선택사항)
  - EOD 배치 → 정산 플로우
  - 데이터 정합성 검증 플로우

- [ ] **6.2.2** 부하 테스트
  - 예측 제출 부하 테스트 (강화된 레이트 리밋)
  - 동시 사용자 처리 테스트
  - 데이터베이스 성능 테스트
  - DDoS 공격 시뮬레이션

- [ ] **6.2.3** 장애 복구 테스트
  - 데이터베이스 장애 복구
  - SQS 메시지 손실 시나리오
  - 외부 API 장애 시나리오

#### 완료 기준

- E2E 시나리오 테스트 통과
- 부하 테스트 통과 (강화된 레이트 리밋)
- 장애 복구 테스트 통과
- 성능 요구사항 충족

### 6.3 보안 검증

**담당자**: Backend Developer  
**예상 시간**: 2일  
**우선순위**: 높음

#### 작업 내용

- [ ] **6.3.1** 인증/인가 보안 테스트

  - JWT 토큰 위조 시도
  - OAuth 플로우 보안 테스트
  - 권한 상승 시도
  - 세션 하이재킹 방지

- [ ] **6.3.2** API 보안 테스트

  - SQL 인젝션 방지
  - XSS 방지
  - CSRF 방지
  - 레이트 리밋 우회 시도
  - 포인트 조작 시도

- [ ] **6.3.3** 데이터 보안 검증
  - 개인정보 암호화
  - 비밀번호 해시 검증
  - OAuth 토큰 보안
  - 감사 로그 무결성

#### 완료 기준

- 보안 테스트 통과
- 취약점 스캔 통과
- 보안 가이드라인 준수
- 포인트 조작 방지 확인

### 6.4 배포 준비

**담당자**: DevOps Engineer  
**예상 시간**: 3일  
**우선순위**: 높음

#### 작업 내용

- [ ] **6.4.1** Docker 이미지 최적화

  - Dockerfile 최적화
  - 멀티스테이지 빌드
  - 이미지 크기 최소화
  - 보안 스캔 통과

- [ ] **6.4.2** 인프라 코드 (Terraform)

  - ECS 서비스 정의
  - RDS 설정 (백업 포함)
  - SQS 큐 설정
  - ALB 설정
  - EventBridge 스케줄
  - CloudWatch 알람

- [ ] **6.4.3** CI/CD 파이프라인

  - GitHub Actions 워크플로우
  - 자동 테스트 실행
  - 자동 배포 설정
  - 롤백 전략

- [ ] **6.4.4** 모니터링 설정
  - CloudWatch 대시보드 (비즈니스 지표 포함)
  - 알람 설정 (시스템 + 비즈니스)
  - 로그 수집 설정
  - 배치 모니터링
  - 정합성 검증 알람

#### 완료 기준

- 배포 자동화 완료
- 모니터링 대시보드 구성
- 알람 정책 설정
- 백업/복구 절차 검증

## 7. 위험 요소 및 대응 방안

### 7.1 기술적 위험

- **데이터베이스 성능**: 인덱스 최적화, 쿼리 튜닝, 연결 풀 설정
- **동시성 문제**: Advisory Lock, 트랜잭션 격리 수준
- **SQS 메시지 유실**: DLQ 설정, 재시도 로직, 멱등성 보장
- **외부 API 의존성**: Alpha Vantage/Yahoo Finance API 장애 대응
- **포인트 데이터 정합성**: 실시간 검증, 감사 로그, 백업 전략

### 7.2 일정 위험

- **OAuth 연동 복잡성**: 테스트 환경 구축, 다양한 브라우저 테스트
- **데이터 정합성 시스템**: 검증 로직 복잡도, 성능 영향
- **배치 시스템 안정성**: EOD API 의존성, 시간대 처리
- **테스트 시간 부족**: 핵심 기능 우선 테스트, 자동화

### 7.3 대응 방안

- **주간 진행 상황 리뷰**: 매주 금요일 진행률 점검
- **위험 요소 조기 식별**: 일일 스탠드업에서 블로커 공유
- **외부 API 백업**: Yahoo Finance API를 Alpha Vantage 백업으로 활용
- **데이터 백업**: 일일 백업, 주간 복구 테스트 실시

## 8. 성공 기준

### 8.1 기능적 요구사항

- [ ] 사용자 가입/로그인 정상 동작 (OAuth 포함)
- [ ] 예측 제출 및 제약 조건 검증
- [ ] EOD 배치 수집 및 정산 정확성
- [ ] 포인트 지급 정확성 및 데이터 정합성
- [ ] 리워드 교환 완전성
- [ ] 관리자 도구 정상 동작 (MFA 포함)
- [ ] 비즈니스 메트릭 모니터링

### 8.2 비기능적 요구사항

- [ ] API 응답 시간 < 300ms (p99)
- [ ] 데이터베이스 연결 안정성 99.9%
- [ ] 메시지 큐 처리 지연 < 30초
- [ ] 배치 작업 정시 실행 99%
- [ ] 보안 요구사항 충족
- [ ] 데이터 정합성 검증 통과
- [ ] DDoS 공격 방어 능력

### 8.3 운영 요구사항

- [ ] 배포 자동화 완료
- [ ] 모니터링 및 알람 설정 (시스템 + 비즈니스)
- [ ] 장애 대응 절차 문서화
- [ ] 데이터 백업 및 복구 절차 (일일/주간)
- [ ] 배치 작업 모니터링
- [ ] 포인트 정합성 검증 자동화
- [ ] 감사 로그 시스템 운영

### 8.4 보안 요구사항

- [ ] OAuth 인증 구현 완료
- [ ] 기본 레이트 리밋
- [ ] 포인트 조작 방지
- [ ] 감사 로그 무결성 보장

이 작업 계획을 바탕으로 순차적으로 개발을 진행하면 됩니다. 각 작업의 우선순위와 의존성을 고려하여 팀 상황에 맞게 조정하시기 바랍니다.

## 9. 추가 개선 권장사항

### 9.1 Phase 1 완료 후 검토사항

- OAuth 구현 완료 여부
- 레이트 리밋 정책 효과성 검증
- 데이터베이스 인덱스 성능 측정

### 9.2 Phase 2 완료 후 검토사항

- EOD 배치 안정성 검증
- 정산 로직 정확성 검증
- SQS 큐 처리량 모니터링

### 9.3 Phase 3 완료 후 검토사항

- 포인트 정합성 검증 결과
- 리워드 교환 성공률
- 데이터베이스 백업/복구 테스트

### 9.4 MVP 이후 고려사항

- 모바일 앱 개발
- 소셜 기능 (친구, 순위)
- AI 기반 예측 도우미
- 고급 차트 및 분석 도구
