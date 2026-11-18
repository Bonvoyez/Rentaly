# Rentaly Frontend

React + TypeScript + Vite + Tailwind CSS v4로 구성된 검사대·관리자 프론트엔드입니다.

## 로컬 실행

```bash
cd frontend
npm install
npm run dev
```

- 관리자: `http://localhost:5173/admin/login` (`admin` / `admin`, Mock 인증)
- 검사대: `http://localhost:5173/kiosk`

## 가짜 검사대 연동

브라우저는 MQTT over WebSocket을 사용하고 `mock/mock_edge.py`는 일반 MQTT를 사용합니다. 두 클라이언트가 같은 Mosquitto 인스턴스를 사용하도록 프로젝트의 `mosquitto.conf`가 MQTT `1883`과 WebSocket `9001`을 함께 엽니다. Windows Mosquitto 서비스가 이미 1883을 사용 중이면 먼저 해당 서비스를 중지한 뒤 아래 개발 브로커를 실행하세요.

터미널 1:

```bash
cd frontend
npm run dev:broker
```

터미널 2:

```bash
cd frontend
npm run dev
```

터미널 3:

```bash
cd frontend
cd ..
source venv/Scripts/activate
python mock/mock_edge.py --scenario pass
# 또는 python mock/mock_edge.py --scenario fail
# 또는 python mock/mock_edge.py --scenario fail_led
# 또는 python mock/mock_edge.py --scenario reposition
```

기본 연결은 `.env.example`의 `ws://localhost:9001`, 장비 ID `station-01`입니다. Mock Edge의 기본 MQTT 주소는 문서 명세 그대로 `localhost:1883`입니다. 시뮬레이터의 REST 결과 전송은 백엔드용이며 프론트엔드는 `POST /api/v1/inspections`를 호출하지 않습니다.

> `mosquitto.conf`의 anonymous 설정은 로컬 개발 전용입니다.
