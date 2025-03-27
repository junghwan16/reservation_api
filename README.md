# 예약 API

이 API 서버는 KST(한국 표준시)를 기준으로 30분 간격의 타임 슬롯을 활용하여 예약을 관리합니다.  
각 슬롯은 최대 50,000명의 인원을 수용할 수 있으며, 시험 시작 72시간(3일) 전까지만 예약이 가능합니다.

## 왜 슬롯 기반인가?

- **직관적 UX**  
  타임 슬롯 방식은 각 슬롯의 남은 용량(예약 가능 인원)을 바로 숫자로 보여주어, 고객이 예약 가능한 시간과 인원을 쉽게 확인할 수 있습니다.
- **부분 겹침(Partial Overlap) 단순화**  
  슬롯을 정형화(예: 30분 단위)하면 예약 시각 계산이나 겹침 처리 로직이 단순해져, 복잡한 "라인 스위핑(Line Sweeping)" 계산 없이 빠르게 처리할 수 있습니다.
- **인원 제한 관리 용이**  
  각 슬롯별로 `capacity_used`와 `MAX_CAPACITY` (기본 50,000)만 관리하면 되어, 추후 최대 인원 변경 시 설정만 수정하면 전역적으로 적용할 수 있습니다.

## 기능 요약

1. **타임 슬롯 기반 시스템**

   - 30분 간격의 슬롯 관리 (00분, 30분으로 정렬)
   - 동시간대 최대 인원 50,000명 제한
   - 시험 시작 72시간(3일) 전까지만 예약 가능
   - 타임 슬롯 생성 커맨드 (`create_slots`) – 대량 생성을 위해 bulk_create 활용

2. **예약 관리**

   - 예약 생성, 조회, 수정, 삭제
   - 예약 상태(PENDING/CONFIRMED) 관리
   - 예약 확정 시 슬롯 용량(예약 인원) 검증
   - 예약 소유자 권한 관리 (자신의 예약만 조회/수정/삭제 가능)
   - 관리자 권한: 모든 예약 조회, 확정 작업, 삭제 등

3. **슬롯 API 개선 (리팩토링)**
   - 기존 전체 슬롯 조회 외에도 **예약 가능한 날짜**와 **특정 날짜의 슬롯 목록**을 제공하는 별도 엔드포인트 추가

## 로컬 환경 설정 및 실행 방법

### 환경 설정

1. **가상 환경 설정**

   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows
   ```

2. **의존성 설치**

   ```bash
   pip install -r requirements.txt
   ```

3. **데이터베이스 설정**

   docker-compose를 사용하여 PostgreSQL 데이터베이스 실행:

   ```bash
   docker-compose up -d
   ```

   또는 로컬에 설치된 PostgreSQL을 사용하는 경우, `settings.py`의 DATABASES 설정을 수정하세요.

### 실행 방법

1. **데이터베이스 마이그레이션**

   ```bash
   python manage.py migrate
   ```

2. **슬롯 생성 (선택 사항)**

   ```bash
   python manage.py create_slots --start_date 2025-04-01 --end_date 2025-05-01
   ```

   - 대량 슬롯 생성은 bulk_create를 활용하여 효율적으로 처리합니다.

3. **관리자 계정 생성**

   ```bash
   python manage.py createsuperuser
   ```

4. **서버 실행**

   ```bash
   python manage.py runserver
   ```

   - 기본 서버 주소: http://127.0.0.1:8000/

5. **테스트 실행**

   ```bash
   python manage.py test
   ```

   - 요구사항에 대한 테스트 코드가 제공됩니다.

## API 문서

API 문서는 Swagger UI 및 ReDoc을 통해 제공됩니다.

- **Swagger UI**: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **ReDoc**: [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)

## 주요 API 엔드포인트

### 인증 관련 (accounts 앱)

- `POST /api/accounts/register/` – 회원가입
- `POST /api/accounts/login/` – 로그인 (JWT 토큰 발급)
- `POST /api/accounts/token/refresh/` – JWT 토큰 갱신
- `POST /api/accounts/logout/` – 로그아웃
- `GET /api/accounts/profile/` – 사용자 정보 조회
- `PATCH /api/accounts/profile/` – 사용자 정보 수정
- `POST /api/accounts/change-password/` – 비밀번호 변경

### 슬롯 관련 (slots 앱)

- `GET /api/slots/available-dates/?year=YYYY&month=MM` – 해당 월의 예약 가능한 날짜와 각 날짜별 슬롯 수 집계
  - 쿼리 파라미터는 별도의 query serializer로 검증합니다.
- `GET /api/slots/day-slots/?date=YYYY-MM-DD` – 특정 날짜의 예약 가능한 슬롯 목록 조회
  - 추가로 `available=true`를 지정하면, 여유 슬롯만 필터링합니다.

### 예약 관련 (reservations 앱)

- `GET /api/reservations/` – 내 예약 목록 조회 (관리자는 모든 예약 조회)
- `POST /api/reservations/` – 새 예약 생성 (현재 로그인한 사용자가 예약 소유자로 자동 설정됨)
- `GET /api/reservations/{id}/` – 특정 예약 조회 (자신의 예약 또는 관리자만 가능)
- `PATCH /api/reservations/{id}/` – 예약 수정 (PENDING 상태의 자신의 예약만 가능)
- `DELETE /api/reservations/{id}/` – 예약 삭제 (자신의 예약 또는 관리자만 가능)
- `POST /api/reservations/{id}/confirm/` – 예약 확정 (관리자만 가능)

## 권한 및 예약 처리

- **사용자 권한**: 일반 사용자는 자신의 예약만 조회, 수정, 삭제할 수 있습니다.
- **관리자 권한**: 관리자는 모든 예약을 조회하고, 확정 및 삭제 등의 작업을 수행할 수 있습니다.
- **예약 소유권**: 예약 생성 시 현재 로그인한 사용자가 자동으로 예약 소유자로 설정됩니다.
- **트랜잭션 처리 및 동시성 제어**: 모든 데이터 변경 작업은 트랜잭션 내에서 처리되며, 예약 확정 및 취소 시 비관적 락(SELECT FOR UPDATE)을 사용하여 동시성 문제를 방지합니다.
