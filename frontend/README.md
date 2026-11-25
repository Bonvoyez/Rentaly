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
# 또는 python mock/mock_edge.py --scenario error
# 또는 python mock/mock_edge.py --scenario manual_return
```

기본 연결은 `.env.example`의 `ws://localhost:9001`, 장비 ID `station-01`입니다. Mock Edge의 기본 MQTT 주소는 문서 명세 그대로 `localhost:1883`입니다. 시뮬레이터의 REST 결과 전송은 백엔드용이며 프론트엔드는 `POST /api/v1/inspections`를 호출하지 않습니다.

> `mosquitto.conf`의 anonymous 설정은 로컬 개발 전용입니다.

## Vercel 배포

키오스크와 관리자 화면은 같은 저장소를 사용하되 **Vercel 프로젝트 2개로 분리**합니다. 각 프로젝트는 `VITE_APP_MODE`로 허용된 화면만 라우팅합니다.

- 키오스크 프로젝트: `/`와 `/kiosk`만 사용하며 `/admin/*` 접근은 `/kiosk`로 돌려보냅니다.
- 관리자 프로젝트: `/`와 `/admin/*`만 사용하며 `/kiosk` 접근은 `/admin/login`으로 돌려보냅니다.

두 프로젝트 모두 같은 저장소와 배포 브랜치를 선택하고 다음 빌드 설정을 사용합니다.

Vercel 프로젝트 설정:

```text
Root Directory: frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

`vercel.json`은 `/admin/inspections` 같은 SPA 경로를 직접 열거나 새로고침할 때도 `index.html`을 제공하도록 설정되어 있습니다.

### 키오스크 프로젝트 환경변수

Vercel 프로젝트의 Settings > Environment Variables에 다음 값을 등록합니다. MQTT 인증 정보는 명세에 따라 비워둡니다.

```text
VITE_APP_MODE=kiosk
VITE_MQTT_BROKER_URL=wss://rentaly.duckdns.org/mqtt
VITE_DEVICE_ID=station-01
```

### 관리자 프로젝트 환경변수

```text
VITE_APP_MODE=admin
VITE_API_BASE_URL=https://rentaly.duckdns.org
```

Vercel 페이지는 HTTPS로 제공되므로 로컬 전용 `ws://localhost:9001`에는 연결할 수 없습니다. 키오스크 배포는 명세에 확정된 TLS WebSocket 주소 `wss://rentaly.duckdns.org/mqtt`를 사용합니다.

### 개인 GitHub 레포에서 배포

팀의 허가를 받은 뒤 개인 계정에 비공개 레포를 만들고 배포용 브랜치를 올립니다. `.env`, 인증서, 비밀번호와 같은 비밀값은 커밋하지 않고 Vercel 환경변수에만 등록합니다. Vercel에서 개인 레포를 Import한 후 위의 Root Directory와 빌드 설정을 적용합니다.

`VITE_APP_MODE=admin`에서는 기존 관리자 화면에 실제 서버의 JWT 로그인, 관리자 권한 확인, 검사 목록·상세·보호 이미지 조회 및 검토 대기 건 판정 확정을 연결합니다. 토큰은 현재 탭의 sessionStorage에 저장하며 로그아웃과 401 응답 시 삭제합니다. 비밀번호는 저장하지 않습니다. 장비 관리 API가 없어 해당 탭은 `Mock 장비 데이터`로 표시되는 로컬 시연 기능입니다. combined 모드는 기존 로컬 Mock 개발용입니다.

관리자 계정 비밀번호는 코드나 Vercel 환경변수에 넣지 않습니다. 백엔드 CORS에 Production 및 필요한 Preview 도메인을 허용한 뒤 브라우저에서 로그인과 이미지 표시를 확인합니다. `VITE_*` 값은 빌드 시 공개되므로 비밀값을 넣으면 안 됩니다. 환경변수 변경 후에는 재배포합니다.
