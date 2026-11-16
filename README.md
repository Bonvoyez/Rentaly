# 🔬 공용 장비 AI 반납 검사대 (Edge AI & IoT)

라즈베리파이 4 기반의 온디바이스 비전 검사 시스템으로, 공용 장비(라즈베리파이 보드) 반납 시 **하드웨어 전원 상태(PWR LED), 고유 시리얼 번호(OCR), 외관 결함(YOLOv8)**을 자동으로 검사하는 프로젝트입니다.

---

## 📂 폴더 구조 안내

```
rentaly/
├── docs/
│   └── API_CONTRACT.md    # 📡 프론트/백엔드 연동을 위한 상세 API 및 MQTT 규격서
├── mock/
│   └── mock_edge.py       # 🚀 라즈베리파이 없이 로컬에서 연동 테스트할 수 있는 가짜 검사대
├── src/                   # 🛠️ 실제 라즈베리파이에서 동작할 임베디드 & AI 파이프라인
│   └── test.py
├── sample_data/           # 🖼️ 테스트용 이미지 및 샘플 데이터
└── README.md
```

---

## 👥 프론트엔드 & 백엔드 팀원을 위한 개발 안내

실제 라즈베리파이나 카메라, AI 모델이 없더라도 **`mock/mock_edge.py`**를 사용해 본인 컴퓨터에서 바로 웹 화면과 서버를 만들고 테스트할 수 있습니다!

### 1. 가상환경 생성 및 패키지 설치

파이썬 환경이 꼬이지 않도록 가상환경(`venv`)을 켜고 패키지를 설치하는 것을 권장합니다:

#### 🍎 Mac / Linux 환경:
```bash
# 1. 가상환경 생성 (최초 1회)
python3 -m venv venv

# 2. 가상환경 활성화
source venv/bin/activate

# 3. 패키지 설치
pip install -r requirements.txt
```

#### 🪟 Windows 환경:
```bash
# 1. 가상환경 생성 (최초 1회)
python -m venv venv

# 2. 가상환경 활성화
venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt
```

### 2. 인터페이스 규격 확인하기
- 프론트엔드/백엔드 통신 데이터 포맷은 [docs/API_CONTRACT.md](docs/API_CONTRACT.md)에 상세히 정리되어 있습니다.
  - **실시간 화면 안내 (MQTT)**: `inspection/{device_id}/telemetry` 토픽 구독
  - **검사 결과 저장 (REST API)**: `POST /api/v1/inspections` (멀티파트 폼 데이터)

### 3. 가짜 검사대 시뮬레이터 실행 방법 (로컬 테스트)

본인 컴퓨터 터미널에서 아래 명령어를 실행하면, 실제 검사가 진행되는 것처럼 1초 간격으로 진행률을 쏴주고 백엔드로 가짜 결과와 이미지를 전송합니다:

```bash
# 기본 실행 (대화형으로 시나리오 선택)
python mock/mock_edge.py

# 정상 통과 시나리오 즉시 실행
python mock/mock_edge.py --scenario pass

# 결함 탐지(핀 휨) 시나리오 즉시 실행
python mock/mock_edge.py --scenario fail

# 전원 불량(PWR LED 꺼짐) 시나리오 즉시 실행
python mock/mock_edge.py --scenario fail_led

# 영상 흐림/재배치 안내 시나리오 즉시 실행
python mock/mock_edge.py --scenario reposition
```

#### 옵션 안내:
- `--backend http://localhost:8000`: 본인의 백엔드 FastAPI 서버 주소 지정
- `--mqtt-host localhost`: 본인의 MQTT 브로커 주소 지정

---

## 🛠️ 임베디드 & AI 파트 주요 구현 계획

1. **파이카메라 캡처 & 모션 블러 계측 (`Picamera2`, Laplacian Variance)**
2. **대상 보드 온보드 PWR LED 정상 점등(Solid ON) 감지**
3. **보드 시리얼 번호 광학 인식 (OCR)**
4. **YOLOv8n 기반 외관 결함 탐지 (GPIO 핀 휨, 포트 파손 등)**
5. **실시간 MQTT 발행 및 백엔드 REST API 연동 통합**
