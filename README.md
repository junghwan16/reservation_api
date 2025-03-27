# 예약 API

KST(한국 표준시) 기준으로 30분 간격의 타임 슬롯을 사용하여 예약을 관리하는 API 서버입니다. 각 슬롯은 최대 50,000명의 인원을 수용할 수 있으며, 시험 시작 3일 전까지만 예약이 가능합니다.

## 왜 슬롯 기반인가?

- 고객 입장에서 '가능 시간·인원'을 쉽게 확인
  - 타임 슬롯 방식은 "현재 슬롯에 얼마나 남았는지"를 숫자로 바로 보여줄 수 있으므로, UX 측면에서 직관적입니다.
  - 일반적인 "자유로운 시간 선택" 예약 시스템보다 고객이 조회/결정하기가 훨씬 쉽다는 장점이 있습니다.
- 부분 겹침(Partial Overlap) 구현 복잡도 감소
  - 시간이 자유롭다면, "라인 스위핑(Line Sweeping)" 등으로 복잡한 Overlap 계산을 해야 하고, 부분 겹침 시나리오가 증가합니다.
  - 슬롯을 정형화(30분·1시간 등)하면, 예약이 슬롯 경계에 맞춰지므로 O(1) 수준으로 "이 슬롯은 얼마나 찼는지" 확인할 수 있습니다.
  - 물론, 실제 트래픽이나 겹치는 예약이 많지 않으면 병목이 크지 않을 수도 있지만, 슬롯 방식이 Overlap 로직을 단순화한다는 것은 분명합니다.
- 인원 제한 관리가 단순
  - "슬롯"별로 capacity_used와 max_capacity(기본 50000)만 관리하면 됩니다.
  - 추후 최대 인원을 바꿀 때도, DB나 설정값에서 max_capacity만 수정하면 전역적으로 적용 가능(개발·운영이 편리).
  - 라이트한 구현으로도 "동일 시간대 최대 인원 제한"을 안정적으로 유지할 수 있습니다.

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
   - 예약 소유자 권한 관리 (자신의 예약만 조회/수정/삭제 가능)
   - 관리자 권한 (모든 예약 조회, 확정 작업 등)

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

   ```
   python manage.py create_slots --start_date 2025-04-01 --end_date 2025-05-01
   ```

   - 대량의 슬롯을 효율적으로 생성하기 위해 bulk_create를 활용합니다.

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
- `GET /api/slots/?available=true` - 여유 공간이 있는 슬롯만 조회

#### 예약 관련

- `GET /api/reservations/` - 내 예약 목록 조회 (관리자는 모든 예약 조회)
- `POST /api/reservations/` - 새 예약 생성 (현재 로그인한 사용자가 자동으로 예약 소유자가 됨)
- `GET /api/reservations/{id}/` - 특정 예약 조회 (자신의 예약 또는 관리자만 가능)
- `PATCH /api/reservations/{id}/` - 예약 수정 (PENDING 상태의 자신의 예약만 가능)
- `DELETE /api/reservations/{id}/` - 예약 삭제 (자신의 예약 또는 관리자만 가능)
- `POST /api/reservations/{id}/confirm/` - 예약 확정 (관리자만 가능)

## 권한 및 예약 처리 관련

- **사용자 권한**: 일반 사용자는 자신의 예약만 조회, 수정, 삭제할 수 있습니다.
- **관리자 권한**: 관리자는 모든 예약을 조회하고, 확정하거나 삭제할 수 있습니다.
- **예약 소유권**: 예약 생성 시 현재 로그인한 사용자가 자동으로 예약의 소유자로 설정됩니다.
- **트랜잭션 처리**: 모든 데이터 변경 작업은 트랜잭션으로 처리되어 일관성을 보장합니다.
- **동시성 제어**: 예약 확정 및 취소 시 비관적 락(SELECT FOR UPDATE)을 사용하여 동시성 문제를 방지합니다.
