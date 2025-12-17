# 환경 변수 설정 가이드

## psycopg2 → psycopg3 마이그레이션

이 프로젝트는 PostgreSQL 드라이버로 **psycopg3**를 사용합니다.

### 주요 변경사항

1. **패키지 변경**
   - 기존: `psycopg2-binary==2.9.9`
   - 신규: `psycopg[binary]==3.2.3`

2. **SQLAlchemy 드라이버 문자열 변경**
   - 기존: `postgresql+psycopg2`
   - 신규: `postgresql+psycopg`

3. **connect_args 설정 변경**
   - psycopg3에서는 `application_name`을 `options` 파라미터로 전달해야 합니다.
   ```python
   connect_args={
       "connect_timeout": 60,
       "options": "-c application_name=tqqq_api"
   }
   ```

## 필수 환경 변수

### 데이터베이스 설정
```bash
database_engine=postgresql+psycopg  # ⚠️ 중요: psycopg3 사용을 위해 반드시 이 값으로 설정
database_username=your_username
database_password=your_password
database_host=localhost
database_port=5432
database_dbname=your_database
database_schema=crypto
database_pool_size=20
database_max_overflow=10
```

### JWT 인증
```bash
AUTH_USERNAME=your_admin_username
AUTH_PASSWORD=your_admin_password
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

### AI 서비스 API 키
```bash
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
PERPLEXITY_API_KEY=your_perplexity_key
BEDROCK_API_KEY=your_bedrock_key
BEDROCK_BASE_URL=your_bedrock_url
```

### AWS 인증
```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

## 마이그레이션 체크리스트

기존 프로젝트를 psycopg3로 마이그레이션할 때:

- [x] `requirements.txt`에서 `psycopg2-binary` → `psycopg[binary]==3.2.3` 변경
- [x] `database.py`의 `connect_args` 수정 (`application_name` → `options`)
- [x] 환경 변수 `database_engine`을 `postgresql+psycopg`로 설정
- [ ] 실제 `.env` 파일에서 `database_engine` 값 확인 및 수정
- [ ] 기존 컨테이너/서비스 재빌드 및 재배포

## 호환성 참고사항

- psycopg3는 psycopg2와 API가 다르므로, 직접 psycopg2를 import하는 코드가 있다면 수정이 필요합니다.
- 이 프로젝트는 SQLAlchemy를 통해서만 데이터베이스에 접근하므로 추가 코드 변경은 필요 없습니다.
- psycopg3는 더 나은 성능과 async 지원을 제공합니다.

## Docker 빌드 시 주의사항

`Dockerfile.lambda`는 `--only-binary=:all:` 플래그를 사용하므로 `psycopg[binary]` 패키지가 정상적으로 설치됩니다. 추가 시스템 패키지 설치는 필요하지 않습니다.

`Dockerfile.fastapi`는 gcc, g++ 등 빌드 도구가 이미 포함되어 있어 문제없습니다.





