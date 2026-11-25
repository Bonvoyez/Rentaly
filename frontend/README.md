# Rentaly Frontend

React + TypeScript + Vite + Tailwind CSS v4로 구성된 검사대·관리자 프론트엔드입니다.

- 키오스크: MQTT로 검사 진행 상태를 받고, 첫 화면의 실시간 카메라 프리뷰 위에 보드 배치 가이드를 표시합니다.
- 관리자: 서버 계정으로 로그인해 검사 이력·이미지를 조회하고 최종 판정을 저장합니다. 장비 관리 탭은 Mock 데이터입니다.

## 로컬 실행

```bash
cd frontend
npm install
npm run dev
```

- 관리자: `http://localhost:5173/admin/login` (`admin` / `admin`, Mock 인증)
- 검사대: `http://localhost:5173/kiosk`

로컬 개발에서 React 개발 도구를 끄려면 선택적으로 `VITE_DISABLE_REACT_DEVTOOLS`를 설정합니다. 운영 빌드에는 필요하지 않습니다.

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

터미널 3 (프로젝트 루트에서):

```powershell
.\venv\Scripts\Activate.ps1
python mock/mock_edge.py --scenario pass
# 또는 python mock/mock_edge.py --scenario fail
# 또는 python mock/mock_edge.py --scenario fail_led
# 또는 python mock/mock_edge.py --scenario reposition
# 또는 python mock/mock_edge.py --scenario error
# 또는 python mock/mock_edge.py --scenario manual_return
```

macOS/Linux에서는 가상환경 활성화 명령을 `source venv/bin/activate`로 바꿉니다.

개발용 연결 값은 `.env.development`를 확인하세요. Mock Edge의 기본 MQTT 주소는 `docs/API_CONTRACT.md`를 따릅니다. 시뮬레이터의 REST 결과 전송은 백엔드용이며 프론트엔드는 `POST /api/v1/inspections`를 호출하지 않습니다.

> `mosquitto.conf`의 anonymous 설정은 로컬 개발 전용입니다.

## 키오스크 카메라 프리뷰

첫 화면과 검사 진행 화면은 `VITE_CAMERA_FEED_URL`의 MJPEG 스트림을 `<img>`로 표시합니다. 첫 화면에서는 파란 보드 배치 가이드가 영상 위에 겹쳐집니다. 스트림이 없거나 로드에 실패하면 예시 이미지를 표시하며, 검사 중에는 MQTT로 받은 촬영 이미지가 있으면 이를 대신 표시합니다.

카메라 주소는 `VITE_CAMERA_FEED_URL`로만 관리합니다. 터널 주소가 바뀌면 환경 변수를 변경하고 **재배포**하세요. 주소는 브라우저에 공개되며, 카메라 스트림 운영은 Vercel 프론트엔드 배포와 별개입니다. “검사 시작”은 MQTT 연결이 있을 때 `inspection/{device_id}/command`에 `{"action":"START"}`를 발행합니다. 발행에 실패하면 첫 화면에 머물며 오류를 표시합니다.

## Vercel 배포

키오스크와 관리자 화면은 같은 저장소를 사용하되 **Vercel 프로젝트 2개로 분리**합니다. 각 프로젝트는 `VITE_APP_MODE`로 허용된 화면만 라우팅합니다.

- 키오스크 프로젝트: `/`와 `/kiosk`만 사용하며 `/admin/*` 접근은 `/kiosk`로 돌려보냅니다.
- 관리자 프로젝트: `/`와 `/admin/*`만 사용하며 `/kiosk` 접근은 `/admin/login`으로 돌려보냅니다.

현재 배포는 팀 저장소의 `chore/vercel-deployment` 브랜치를 푸시한 뒤 Vercel CLI로 수동 실행합니다. 저장소와 Vercel을 자동 연동하지 않았으므로 **푸시만으로는 배포되지 않습니다.**

Vercel 프로젝트 설정 (Git 연동 시):

```text
Root Directory: frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

`vercel.json`은 `/admin/inspections` 같은 SPA 경로를 직접 열거나 새로고침할 때도 `index.html`을 제공하도록 설정되어 있습니다.

CLI는 `frontend` 디렉터리에서 실행합니다. 이때 Root Directory는 현재 디렉터리(`./`)이며 `frontend`를 한 번 더 지정하지 않습니다. `vercel link`가 만드는 `.vercel`은 로컬 연결 정보로 Git에 커밋하지 않습니다.

```bash
cd frontend
npx vercel@latest login
npx vercel@latest link --yes --scope parksiwoons-projects --project rentaly-kiosk
npx vercel@latest --prod --yes
```

관리자 배포 시에는 `link`의 프로젝트 이름을 `rentaly-admin`으로 바꿉니다. 배포 전에 `.vercel/project.json`의 `projectName`이 의도한 프로젝트인지 확인하세요. 운영 URL은 [키오스크](https://rentaly-kiosk.vercel.app)와 [관리자](https://rentaly-admin-phi.vercel.app)입니다. 두 프로젝트의 환경 변수는 각각 Vercel 대시보드에서 설정합니다.

### 키오스크 프로젝트 환경변수

Vercel 프로젝트의 Settings > Environment Variables에 값을 등록합니다. 실제 값은 `.env.example`을 참고하고 운영 값은 Vercel에서 관리합니다.

| 변수 | 용도 |
| --- | --- |
| `VITE_APP_MODE` | 키오스크 화면만 활성화 |
| `VITE_MQTT_BROKER_URL` | 검사 진행 정보를 받는 MQTT WebSocket 주소 |
| `VITE_DEVICE_ID` | 구독할 검사대 장비 ID |
| `VITE_CAMERA_FEED_URL` | 첫 화면과 검사 진행 화면의 카메라 스트림 주소 |

### 관리자 프로젝트 환경변수

| 변수 | 용도 |
| --- | --- |
| `VITE_APP_MODE` | 관리자 화면만 활성화 |
| `VITE_API_BASE_URL` | 관리자 REST API 서버 주소 |

Vercel 페이지는 HTTPS로 제공되므로 키오스크의 MQTT WebSocket 주소도 `wss://`를 사용해야 합니다.

`VITE_APP_MODE=admin`에서는 기존 관리자 화면에 실제 서버의 JWT 로그인, 관리자 권한 확인, 검사 목록·상세·보호 이미지 조회 및 검토 대기 건 판정 확정을 연결합니다. 토큰은 현재 탭의 sessionStorage에 저장하며 로그아웃과 401 응답 시 삭제합니다. 비밀번호는 저장하지 않습니다. 장비 관리 API가 없어 해당 탭은 `Mock 장비 데이터`로 표시되는 로컬 시연 기능입니다. combined 모드는 기존 로컬 Mock 개발용입니다.

관리자 상세 화면의 이미지는 상세 API의 `image_id`로 보호 이미지 API를 다시 호출해 표시합니다. `image_id` 자체에 이미지 데이터가 들어 있는 것은 아닙니다. 검토 대기 건은 아직 관리자 판정 전이며, AI 1차 판정이 `FAIL`이면 반려를 기본 선택으로 보여줍니다. 승인·반려의 최종 저장은 관리자가 확정할 때 이루어집니다.

관리자 계정 비밀번호는 코드나 Vercel 환경변수에 넣지 않습니다. 백엔드 CORS에 Production 및 필요한 Preview 도메인을 허용한 뒤 브라우저에서 로그인과 이미지 표시를 확인합니다. `VITE_*` 값은 빌드 시 공개되므로 비밀값을 넣으면 안 됩니다. 환경변수 변경 후에는 재배포합니다.
