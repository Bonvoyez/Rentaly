# 📡 공용 장비 AI 반납 검사대 - 통신 인터페이스 규격서 (API Contract)

> **작성 파트**: AI & 임베디드 (Edge Controller)  
> **대상 독자**: 백엔드(Backend) 및 프론트엔드(Frontend) 개발 팀원  
> **목적**: 실제 라즈베리파이 하드웨어 없이도 프론트엔드와 백엔드가 원활하게 연동 및 개발을 진행할 수 있도록 데이터 형식과 통신 규격을 정의합니다.

---

## 1. 통신 구조 요약

검사대 시스템은 **이원화 통신 구조**를 사용합니다:
1. **실시간 텔레메트리 (MQTT over WebSocket)**: 
   - 엣지 검사대 → 프론트엔드 (Mosquitto 브로커 경유)
   - 검사 진행률, 카메라 블러 점수, 실시간 단계 안내 등을 1초 단위로 빠르게 전송합니다.
2. **최종 검사 결과 저장 (HTTPS REST API)**:
   - 엣지 검사대 → 백엔드 FastAPI
   - 검사가 끝난 후 최종 판정 결과, 결함 목록, 촬영된 고해상도 이미지를 전송하여 DB에 영속 저장합니다.

---

## 2. 실시간 텔레메트리 규격 (MQTT)

### 검사 시작 명령 (프론트엔드 → 검사대)

“검사 시작” 버튼을 누르면 프론트엔드는 연결된 MQTT 브로커에 다음 명령을 발행합니다. `{device_id}`에는 키오스크의 `VITE_DEVICE_ID`를 사용합니다.

```text
Topic: inspection/{device_id}/command
Payload: {"action":"START"}
```

발행 후 검사 진행 상태는 아래 텔레메트리 토픽에서 받습니다.

### 📌 토픽 (Topic)
```text
inspection/{device_id}/telemetry
```
- 예시: `inspection/station-01/telemetry`

### 📦 발행 주기 및 시점
- 장비 거치 감지 시점부터 검사 종료 시점까지 약 **0.5초 ~ 1초 간격**으로 각 검사 단계(Stage)마다 발행됩니다.

### 📝 페이로드 (JSON 형식)
```json
{
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "device_id": "station-01",
  "stage": "AI_INFERENCE",
  "progress_percent": 75,
  "blur_score": 182.4,
  "stabilization_ms": 320,
  "message": "AI 외관 결함 분석을 진행 중입니다...",
  "capture_image_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
}
```

### 📋 필드 상세 설명
| 필드명 | 타입 | 설명 | 값 예시 |
| :--- | :--- | :--- | :--- |
| `inspection_id` | string (UUID) | 해당 검사 세션의 고유 식별자 | `"c9a1b8e4-..."` |
| `device_id` | string | 검사대 장비 고유 ID | `"station-01"` |
| `stage` | string (Enum) | 현재 진행 중인 검사 단계 | 아래 `stage 목록` 참조 |
| `progress_percent`| int | 전체 검사 진행률 (0 ~ 100) | `0` ~ `100` |
| `blur_score` | float | 카메라 영상의 선명도 점수 (라플라시안 분산) | `150.2` (높을수록 선명함) |
| `stabilization_ms`| int | 모션 흔들림 안정화까지 걸린 시간 (ms) | `320` |
| `message` | string | 사용자 화면(UI)에 띄울 한글 안내 메시지 | `"장비가 거치되었습니다."` |
| `capture_image_url` | string (선택) | 촬영 직후 키오스크에 표시할 JPEG Base64 Data URL. 이후 단계에서 생략해도 키오스크는 해당 검사 중 이미지를 유지합니다. | `"data:image/jpeg;base64,..."` |

#### `stage` (검사 단계) 구분:
1. `MOUNTED`: 보드가 거치대 스위치에 정상 안착됨 감지
2. `STABILIZING`: 카메라 노출/초점 및 모션 안정화 진행 중
3. `BLUR_CHECK`: 영상 품질 및 흐림(블러) 평가 중
4. `OCR`: 보드 표면 시리얼 번호 광학 인식 중
5. `LED_CHECK`: 대상 보드의 온보드 PWR LED 점등 확인 중
6. `AI_INFERENCE`: YOLOv8 기반 외관 결함(핀 휨, 포트 파손 등) 추론 중
7. `COMPLETED`: 검사 완료 (최종 결과 전송 단계)
8. `REPOSITION`: 영상 흐림/위치 이탈로 인한 재거치 안내 상태

---

## 3. 최종 검사 결과 전송 규격 (REST API)

검사가 모두 완료되면 엣지 검사대가 백엔드 서버로 촬영된 사진과 상세 메타데이터를 전송합니다.

### 📌 엔드포인트
```http
POST /api/v1/inspections
Content-Type: multipart/form-data
```

### 🔑 헤더 (Headers)
| 헤더명 | 필수 여부 | 설명 |
| :--- | :--- | :--- |
| `X-Device-Secret` | 필수 | 검사대 장비 인증용 시크릿 키 (예: `edge-secret-key-1234`) |
| `X-Inspection-ID` | 선택 | 검사 고유 세션 UUID (추적 로그용) |

### 📦 요청 본문 (Form Data)
1. **`metadata`** (Text / JSON String, 필수): 검사 결과 상세 메타데이터
2. **`image`** (File / Binary, 필수): 검사 시 촬영된 보드 원본 사진 (`.jpg`)

---

### 📝 `metadata` JSON 상세 규격

```json
{
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "equipment_id": "RPI4-001",
  "recognized_serial_number": "10000000a1b2c3d4",
  "primary_verdict": "PASS",
  "reposition_count": 0,
  "pwr_led_status": true,
  "detected_defects": [],
  "metrics": {
    "blur_score": 182.4,
    "stabilization_ms": 320,
    "serial_recognition_ms": 410,
    "visual_inspection_ms": 350,
    "inference_ms": 185,
    "total_duration_ms": 2265
  }
}
```

#### 📋 `metadata` 필드 상세 설명:
- `inspection_id` (string): 검사 UUID
- `equipment_id` (string): 검사 대상 장비 모델 ID (기본: `"RPI4-001"`)
- `recognized_serial_number` (string | null): OCR로 인식된 보드 고유번호 (인식 실패 시 `null`)
- `primary_verdict` (string, Enum): 1차 검사 판정 결과
  - **`PASS`**: 모든 외관 및 LED 점등 검사 통과 (정상 반납 처리)
  - **`REPOSITION`**: 영상 흐림/손가림 등으로 재배치 필요 (3회 초과 시 수동 반납)
  - **`FAIL`**: 외관 결함 탐지 또는 LED 미점등 (관리자 검토 대기열 `PENDING_REVIEW`로 전이)
  - **`ERROR`**: 카메라 오류, 센서 고장 등 시스템 장애 (`SYSTEM_FAULT`)
- `reposition_count` (int): 재거치 요청이 발생했던 횟수 (0 ~ 3)
- `pwr_led_status` (boolean): 대상 라즈베리파이의 빨간색 PWR LED가 켜졌는지 여부 (`true`: 정상 점등, `false`: 미점등/전원 불량)
- `detected_defects` (Array): 감지된 결함 목록 (결함 없을 시 빈 배열 `[]`)
  ```json
  [
    {
      "class": "bent_pin",
      "confidence": 0.89,
      "bbox": [120, 45, 160, 85]
    }
  ]
  ```
  - `class`: `"bent_pin"`(핀 휨), `"damaged_port"`(포트 파손), `"missing_sd"`(SD 미장착) 등
  - `confidence`: 0.0 ~ 1.0 (탐지 신뢰도)
  - `bbox`: `[x_min, y_min, x_max, y_max]` (이미지 상의 결함 박스 좌표)
- `metrics` (Object): 성능 및 지연시간 계측 데이터 (ms 단위)

---

### 📥 백엔드 응답 규격

#### 성공 시 (`201 Created` 또는 `200 OK`)
```json
{
  "status": "SUCCESS",
  "inspection_id": "c9a1b8e4-7d2f-4a3e-b819-123456789abc",
  "final_status": "PASSED",
  "created_at": "2026-11-16T17:30:00Z"
}
```
*(결함 발생 시 `final_status`는 `"PENDING_REVIEW"`로 저장되어 관리자 검토를 기다립니다.)*

#### 검증 실패 시 (`422 Unprocessable Entity` 또는 `400 Bad Request`)
```json
{
  "status": "ERROR",
  "error_code": "INVALID_METADATA",
  "message": "pwr_led_status 필드가 누락되었습니다."
}
```

---

## 4. 백엔드 & 프론트엔드 연동 팁

1. **프론트엔드 개발자**:
   - `inspection/{device_id}/telemetry` MQTT 토픽을 구독하여 화면의 진행 프로그레스 바(`progress_percent`)와 현재 단계(`stage`), 사용자 안내 메시지(`message`)를 반응형으로 렌더링하세요.
   - `stage == "REPOSITION"`이면 "보드를 다시 놓아주세요" 안내 모달을 띄우면 됩니다.
2. **백엔드 개발자**:
   - FastAPI에서 `Form(...)`으로 `metadata`를 받고 Pydantic 모델로 파싱한 뒤, `UploadFile`로 넘어온 이미지를 영속 디렉토리(`/app/storage/images/{inspection_id}.jpg`)에 저장하세요.
   - DB 테이블(`INSPECTION`, `AI_RESULT`, `IMAGE`)에 분할 적재하면 명세서 구조와 완벽히 맞아떨어집니다.
3. **가짜 검사기(Mock) 사용**:
   - 하드웨어 없이 개발할 수 있도록 `mock/mock_edge.py`를 제공합니다. 자세한 사용법은 [README.md](../README.md)를 참고하세요.
