## 신호 생성/저장 흐름 이중 검증 체크리스트

- [ ] `/signals/` 배치 엔드포인트 동작 확인
  - `myapi/routers/signal_router.py`에서 `/signals/` 요청이 어떤 객체를 생성하고 어떤 서비스로 전달되는지 흐름을 정리
  - `SignalService.generate_prompt`, `llm_query` → `/signals/generate-signal-reult` 호출 구조를 파악

- [ ] LLM 호출 및 결과 큐잉 로직 검토
  - 같은 파일의 `llm_query`에서 `AwsService.generate_queue_message_http`와 `send_sqs_fifo_message` 호출 파라미터 점검
  - `myapi/services/aws_service.py`(사용 시)에서 HTTP 요청과 SQS 메시지 구성 로직 확인

- [ ] 생성 결과 DB 적재 경로 추적
  - `myapi/routers/signal_router.py`의 `/signals/generate-signal-reult`에서 `SignalsRepository.create_signal` 호출 방식 확인
  - `myapi/services/db_signal_service.py`의 `create_signal`, `get_today_signals` 등 서비스 계층을 통해 레포지토리가 어떻게 사용되는지 정리

- [ ] 레포지토리 계층 시간대 처리 재확인
  - `myapi/repositories/signals_repository.py` 전반에서 timestamp를 KST 기준으로 변환하는 `_normalize_to_kst_naive` 사용 여부 검토
  - `get_ticker`, `get_today_tickers`, `get_signals_by_date_range` 등 날짜 필터가 KST 날짜를 기준으로 작동하는지 확인

- [ ] ORM/Pydantic 모델 기본값 일치 여부 확인
  - `myapi/domain/signal/signal_models.py`에서 SQLAlchemy 모델의 기본 timestamp가 `_now_kst_naive`로 설정되어 있는지 체크
  - `myapi/domain/signal/signal_schema.py`에서 `SignalBase`, `SignalValueObject` 등의 기본 timestamp가 KST로 맞춰졌는지 검토하고 `to_orm` 변환 시 타임존 제거 로직 확인

- [ ] 날짜 유틸리티와 배치 스케줄 검증
  - `myapi/utils/date_utils.py`의 `get_current_kst_datetime`, `get_latest_market_date` 등 헬퍼가 올바른지 재검토
  - `myapi/routers/batch_router.py` 및 관련 스케줄러(예: 크론/서버리스 설정)에서 07:00 KST 실행 시 참조 날짜가 전일(미국 장)로 잡히는지 확인

- [ ] 티커/시그널 조회 API 영향 확인
  - `myapi/routers/ticker_router.py`, `myapi/repositories/ticker_repository.py` 등 조회용 엔드포인트가 새 시간대 정책에 의해 영향받는 부분이 있는지 점검
  - 신호 요약/분석을 사용하는 다른 서비스(`myapi/services/signal_service.py`)의 날짜 계산이 일관된지 확인

- [ ] 설정 및 외부 의존성 재확인
  - `.env` 및 `myapi/utils/config.py`(사용 시)에서 Auth 토큰, 타임존 관련 설정 값 확인
  - `requirements.txt`에 포함된 시간대/시장 캘린더 관련 라이브러리 버전이 최신 정책을 지원하는지 점검

