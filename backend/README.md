# Rentaly Backend (Edge Ingestion + Admin Dashboard Integration)

라즈베리 파이(Edge) 검사 결과 수집 및 실시간 중계 파이프라인과 PostgreSQL 데이터베이스 영속화, 관리자 인증·검토 대시보드, 만료 이미지 자동 정리 스케줄러를 하나로 통합한 백엔드 시스템입니다.

---

## 1. 주요 통합 및 변경 사항 (Changelog)

### ① 인프라 및 의존성 통합
- **`docker-compose.yml`**: `db`(PostgreSQL 16), `mqtt`(Eclipse Mosquitto 2), `api`(FastAPI) 3개 서비스 통합 구성 및 `JWT_SECRET_KEY` 환경변수 추가
- **`backend/requirements.txt`**: DB(`sqlalchemy`, `psycopg[binary]`), 관리자 인증(`passlib`, `bcrypt`, `python-jose`), 배치 스케줄러(`apscheduler`) 의존성 병합

### ② 데이터베이스 연동 및 스키마 통일
- **`backend/app/database.py` & `models/`**: `postgresql+psycopg` 드라이버 기반 DB 세션 및 6개 핵심 엔티티(`EQUIPMENT`, `INSPECTION`, `AI_RESULT`, `IMAGE`, `ADMIN_USER`, `AUDIT_LOG`) 구축
- **`backend/app/schemas.py`**: Edge 메타데이터 수신 스키마(`InspectionMetadata`, `Metrics`, `Defect`)와 관리자 인증·대시보드 입출력 스키마를 단일 모듈로 통합
- **`backend/app/main.py`**: 서버 구동(`lifespan`) 시 `Base.metadata.create_all`을 통한 테이블 자동 초기화 및 매일 새벽 03:00 만료 이미지(`PASSED` 후 30일 경과) 자동 삭제 스케줄러 등록

### ③ Edge 검사 결과 DB 영속화 및 상태 전이
- **`backend/app/inspections.py` & `models/enums.py`**:
  - `POST /api/v1/inspections` 수신 시 이미지 파일 저장(`/app/storage/images`)과 함께 DB 4개 테이블(`EQUIPMENT`, `INSPECTION`, `AI_RESULT`, `IMAGE`) 동시 기록
  - 동일한 `inspection_id` 재전송 시 중복 저장을 방지하는 **멱등성(Idempotency)** 처리 적용
  - 1차 판정(`primary_verdict`)에 따른 초기 `final_status` 자동 매핑 및 시스템 오류(`ERROR`) 격리:
    - `PASS` → `PASSED`
    - `FAIL` → `PENDING_REVIEW` (관리자 검토 대기열)
    - `ERROR` → `ERROR` (검토 대기열과 엄격히 격리)
    - `REPOSITION` → `REPOSITION_LOG` (3회 초과 시 `MANUAL_RETURN`)

### ④ 관리자 인증 및 대시보드 API 추가
- **`backend/app/core/security.py`**: 관리자 전용 JWT 발급·검증(RBAC) 및 Bcrypt 비밀번호 해싱
- **`backend/app/routers/admin_auth.py`**: 관리자 로그인(`POST /api/v1/admin/auth/login`) 및 토큰 검증(`GET /api/v1/admin/auth/me`)
- **`backend/app/routers/admin_inspections.py`**:
  - 검토 대기열(`GET /api/v1/admin/inspections/pending`) 및 전체 검사 이력 조회
  - 관리자 최종 판정 확정(`POST /api/v1/admin/inspections/{id}/confirm` → `CONFIRMED_PASS` / `CONFIRMED_REJECT`) 및 감사 로그(`AUDIT_LOG`) 기록
  - 사후 반려 처리(`POST /api/v1/admin/inspections/{id}/retroactive-reject` → `RETROACTIVE_REJECT`)
  - 관리자 권한 인증이 필요한 보호된 검사 이미지 서빙(`GET /api/v1/admin/images/{image_id}`, 상대/절대 경로 양방향 호환)

---

## 2. 디렉터리 구조

```text
프로젝트루트/
 ├── .env                        # 환경변수 설정 (DB 계정, DEVICE_SECRET, JWT_SECRET_KEY)
 ├── docker-compose.yml          # 통합 컨테이너 실행 설정
 ├── infra/mosquitto/            # MQTT 브로커 설정
 └── backend/
      ├── Dockerfile
      ├── requirements.txt       # 통합 Python 패키지 목록
      ├── seed_admin.py          # 초기 관리자 계정 생성 스크립트
      └── app/
           ├── main.py           # FastAPI 엔트리포인트 (라우터 + 스케줄러 + 테이블 자동 생성)
           ├── database.py       # SQLAlchemy DB 연결 설정
           ├── schemas.py        # Edge + Admin 통합 Pydantic 스키마
           ├── inspections.py    # Edge 검사 데이터 수신 및 DB 저장 API
           ├── auth.py           # Edge 디바이스 키 검증
           ├── storage.py        # 검사 이미지 볼륨 저장
           ├── errors.py         # 공통 예외 포맷
           ├── scheduler.py      # 만료 이미지 정리 스케줄러 (매일 03:00)
           ├── core/
           │    └── security.py  # JWT & Bcrypt 보안 모듈
           ├── models/
           │    ├── entities.py  # SQLAlchemy DB 테이블 모델
           │    └── enums.py     # 판정 및 상태 Enum 정의
           ├── routers/
           │    ├── admin_auth.py        # 관리자 인증 라우터
           │    └── admin_inspections.py # 관리자 대시보드 라우터
           └── services/
                └── storage_cleanup.py   # 30일 경과 이미지 정리 서비스
```

---

## 3. 실행 및 초기 세팅 방법

### ① 환경변수(`.env`) 확인
프로젝트 루트 경로의 `.env` 파일에 아래 항목이 설정되어 있어야 합니다.

```env
POSTGRES_USER=rentaly
POSTGRES_PASSWORD=change-me
POSTGRES_DB=rentaly
DEVICE_SECRET=edge-secret-key-1234
JWT_SECRET_KEY=super-secret-jwt-key-change-in-production
```

### ② Docker 컨테이너 실행 및 초기 관리자 생성
```bash
# 1. 통합 컨테이너(db, mqtt, api) 빌드 및 백그라운드 실행 (DB 테이블 자동 생성)
docker compose up -d --build

# 2. 초기 관리자 계정 생성 (ID: admin / PW: admin1234!)
docker exec -it rentaly-api python seed_admin.py
```

### ③ API 문서 및 헬스체크 확인
- **Health Check**: `http://localhost:8000/health`
- **Swagger UI (API 명세 및 테스트)**: `http://localhost:8000/docs`