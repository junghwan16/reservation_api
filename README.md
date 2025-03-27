# 예약 API

KST(한국 표준시) 기준으로 30분 간격의 타임 슬롯을 사용하여 예약을 관리하는 API 서버입니다. 각 슬롯은 최대 50,000명의 인원을 수용할 수 있으며, 시험 시작 3일 전까지만 예약이 가능합니다.

## 기능 요약

1. **타임 슬롯 기반 시스템**

   - 30분 간격의 슬롯 관리 (00분, 30분으로 끝나도록 설계)
   - 동시간대 최대 인원 50,000명 제한
   - 시험 시작 72시간(3일) 전 제한
   - 타임 슬롯 생성 커맨드 (`create_slots`)

2. **예약 관리**
   - 예약 생성, 조회, 수정, 삭제
   - PENDING/CONFIRMED 상태 관리
   - 예약 확정 시 인원 제한 검증

## 로컬 환경 설정 및 실행 방법

### 환경 설정

1. **가상 환경 설정**

   ```
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows
   ```

2. **의존성 설치**

   ```
   pip install -r requirements.txt
   ```

3. **데이터베이스 설정**

   docker-compose를 사용하여 PostgreSQL 데이터베이스 실행:

   ```
   docker-compose up -d
   ```

   또는 로컬에 설치된 PostgreSQL을 사용하는 경우 `settings.py`의 값을 수정하세요.

### 실행 방법

1. **데이터베이스 마이그레이션**

   ```
   python manage.py migrate
   ```

2. **슬롯 생성 (선택 사항)**

   - bulk create를 쓰지 않고, 일일히 겹치는게 있는지 검색하며 생성합니다.

   ```
   python manage.py create_slots --start_date 2025-04-01 --end_date 2025-05-01
   ```

3. **관리자 계정 생성**

   ```
   python manage.py createsuperuser
   ```

4. **서버 실행**

   ```
   python manage.py runserver
   ```

   - 서버는 기본적으로 http://127.0.0.1:8000/ 에서 실행됩니다.

5. **테스트 실행**

   ```
   python manage.py test
   ```

   - 요구사항에 대한 테스트 코드가 제공됩니다.

## API 문서

API 문서는 Swagger UI를 통해 제공됩니다.

- **Swagger UI**: http://127.0.0.1:8000/api/docs/
- **ReDoc**: http://127.0.0.1:8000/api/redoc/

### 주요 API 엔드포인트

#### 인증 관련

- `POST /api/accounts/register/` - 회원가입
- `POST /api/accounts/login/` - 로그인 (JWT 토큰 발급)
- `POST /api/accounts/token/refresh/` - JWT 토큰 갱신
- `POST /api/accounts/logout/` - 로그아웃
- `GET /api/accounts/profile/` - 사용자 정보 조회
- `PATCH /api/accounts/profile/` - 사용자 정보 수정
- `POST /api/accounts/change-password/` - 비밀번호 변경

#### 슬롯 관련

- `GET /api/slots/` - 모든 슬롯 조회
- `GET /api/slots/?date=YYYY-MM-DD` - 특정 날짜의 슬롯 조회
- `GET /api/slots/?start=YYYY-MM-DDT00:00:00Z&end=YYYY-MM-DDT23:59:59Z` - 특정 기간의 슬롯 조회

#### 예약 관련

- `GET /api/reservations/` - 내 예약 목록 조회 (관리자는 모든 예약 조회)
- `POST /api/reservations/` - 새 예약 생성
- `GET /api/reservations/{id}/` - 특정 예약 조회
- `PATCH /api/reservations/{id}/` - 예약 수정 (PENDING 상태일 때만 가능)
- `DELETE /api/reservations/{id}/` - 예약 삭제
- `POST /api/reservations/{id}/confirm/` - 예약 확정 (관리자만 가능)
