TODO 1. 컨테이너에서 세션 생성 방식을 점검

myapi/containers.py:30의 providers.Resource(get_db)는 애플리케이션 전역에서 하나의 SQLAlchemy Session을 재사용합니다. 이 세션이 여러 요청/스레드에서 동시에 사용되면서 This session is provisioning a new connection 오류가 발생합니다.
TODO 2. 요청마다 독립적인 세션을 공급하도록 DI를 수정

SessionLocal()을 반환하는 팩토리/컨텍스트를 만들고, 요청 처리 후 반드시 close()가 호출되도록 구조를 바꿉니다.
예: providers.Factory(SessionLocal) + FastAPI dependency/middleware로 with SessionLocal() as session: 패턴 적용.
또는 FastAPI 라우터에서 Depends(get_db)로 직접 세션을 주입하고, 서비스/리포지토리에 세션을 전달하도록 서명 수정을 전파합니다.
TODO 3. 리포지토리/서비스가 세션 생명주기에 의존하지 않도록 리팩터링

생성자에서 세션 인스턴스를 보관하던 방식을 변경해, 호출 시점마다 컨텍스트에서 받은 세션을 사용하게끔 조정합니다.
세션을 공유하지 않는 구조가 되면 self.db_session.close() 같은 직접 호출은 제거하고, 상위 컨텍스트에서 정리하도록 맡깁니다. (web_search_repository.py:56-58 등)
TODO 4. 불필요한 연결 체크·롤백 루프 제거

pool_pre_ping=True가 이미 설정되어 있으므로 SELECT 1 수동 실행/재시도 (web_search_repository.py:50-118, :220-305 등)를 없애고, 실제로 필요한 예외(OperationalError)만 캐치하여 재시도하도록 단순화합니다. 중복 롤백 호출이 줄어들면 세션 상태 오류도 완화됩니다.
TODO 5. 변경 후 동시 요청 시나리오 재현 테스트

/news/market-forecast와 /signals/date를 동시에 호출하는 통합 테스트나 간단한 스크립트로 다중 요청을 보내 세션 공유 오류가 재발하지 않는지 확인합니다.
필요하면 SQLAlchemy 로깅(echo=True)을 잠시 켜서 각 요청이 별도 커넥션을 쓰는지 검증하세요.
