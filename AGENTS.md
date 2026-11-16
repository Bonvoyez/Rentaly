# Rentaly Project AI Agent Rules & Architecture Context

이 문서는 Antigravity, Cursor, Claude Code 등 AI 코딩 에이전트들이 Rentaly 프로젝트의 아키텍처와 규칙을 파악하고 일관성 있는 코드를 작성할 수 있도록 돕는 가이드라인입니다.

---

## 1. 프로젝트 개요 (Overview)
- **프로젝트명**: 공용 장비 AI 반납 검사대 (Rentaly)
- **시스템 목적**: 공용 장비(라즈베리파이 4 단품 보드) 반납 시 카메라 영상 분석을 통해 **전원 상태(PWR LED), 고유 시리얼 번호(OCR), 외관 결함(YOLOv8)**을 자동 검사하여 반납 절차를 무인화/자동화합니다.

---

## 2. 역할 분담 및 디렉토리 구조
```
rentaly/
├── docs/             # [공통] API 및 통신 인터페이스 규격서 (API_CONTRACT.md)
├── mock/             # [백엔드/프론트엔드용] 로컬 연동 테스트용 가짜 엣지 시뮬레이터 (mock_edge.py)
├── src/              # [임베디드/AI] 라즈베리파이 실전 검사 파이프라인 코드
├── sample_data/      # 테스트용 샘플 이미지
└── README.md         # 전체 개발 안내서
```

---

## 3. 핵심 인터페이스 및 데이터 규격 (Contract)
- **실시간 통신 (MQTT)**: 토픽 `inspection/{device_id}/telemetry`
  - 프론트엔드가 구독하여 검사 진행률(`progress_percent`), 현재 단계(`stage`), 사용자 안내 메시지(`message`), 블러 점수(`blur_score`)를 실시간 표시합니다.
- **최종 결과 저장 (REST API)**: `POST /api/v1/inspections` (multipart/form-data)
  - `metadata`: JSON 문자열 (1차 판정 결과 `PASS/FAIL/REPOSITION`, `pwr_led_status: boolean`, `detected_defects: list` 등)
  - `image`: 보드 촬영 사진 바이너리 (`capture.jpg`)
- 상세 스펙은 `docs/API_CONTRACT.md`를 최우선 기준으로 준수합니다.

---

## 4. 임베디드 & AI 파트 실행 원칙 (라즈베리파이 연동)
- **로컬 경로**: `~/3-2/cloudAIoT/rentaly`
- **테스트 및 실행 시 동기화 절차**:
  1. 라즈베리파이 동기화:
     ```bash
     rsync -avz --exclude 'venv' --exclude '__pycache__' ./ pimicro:~/aiot-project/
     ```
  2. 라즈베리파이 원격 실행:
     ```bash
     ssh pimicro '~/aiot-project/venv/bin/python src/<파일명>.py'
     ```
*(백엔드와 프론트엔드 팀원은 라즈베리파이에 접속할 필요 없이 `python mock/mock_edge.py`를 실행하여 로컬에서 바로 개발 및 테스트를 진행합니다.)*
