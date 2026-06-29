# Frontend

HPM 서비스의 웹 클라이언트 영역입니다. 실제 React 애플리케이션은 `frontend/hpm` 아래에 있으며, 사용자는 이 화면에서 로그인, 프로젝트 선택, 회의 생성/녹음, 안건 생성, 회의록 검토, Jira 등록, 문서 관리, 구성원 관리를 진행합니다.

## 폴더 구조

```text
frontend/
├─ hpm/                 # React + TypeScript + Vite 애플리케이션
│  ├─ src/
│  │  ├─ assets/        # 화면에서 사용하는 이미지, 아이콘
│  │  ├─ components/    # 공통 UI와 도메인별 컴포넌트
│  │  ├─ constants/     # 화면 문구, 옵션, 디자인 상수
│  │  ├─ context/       # 인증/녹음 등 전역 상태
│  │  ├─ features/      # 기능 단위 API 또는 로직
│  │  ├─ hooks/         # 커스텀 훅
│  │  ├─ pages/         # 라우트별 화면
│  │  ├─ routes/        # React Router 설정
│  │  ├─ services/      # 백엔드 API 호출 모듈
│  │  ├─ store/         # Zustand 기반 클라이언트 상태
│  │  └─ types/         # 화면/응답 타입 정의
│  ├─ package.json
│  └─ vite.config.ts
├─ package.json         # Tailwind 관련 상위 의존성
└─ package-lock.json
```

## 주요 기술

- React 19
- TypeScript
- Vite
- React Router
- Axios
- Zustand
- Tailwind CSS
- html2canvas, jsPDF

## 실행 방법

```bash
cd frontend/hpm
npm install
npm run dev
```

개발 서버 기본 주소는 다음과 같습니다.

```text
http://localhost:5173
```

`vite.config.ts`에서 `/api` 요청은 로컬 Django 서버로 프록시됩니다.

```text
/api -> http://localhost:8000
```

## 빌드

```bash
cd frontend/hpm
npm run build
```

빌드 결과물은 `frontend/hpm/dist`에 생성됩니다. Docker 배포에서는 `Dockerfile.frontend`가 이 결과물을 nginx 이미지에 복사해 정적 파일로 서빙합니다.

## 환경변수

프론트엔드는 Vite 환경변수를 사용합니다.

| 이름 | 설명 | 예시 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | 백엔드 API 기본 주소 | `http://localhost:8000/api` |

로컬 개발 시에는 `frontend/hpm/.env` 또는 루트 `.env`에 값을 둡니다. `.env` 파일은 Git에 올리지 않습니다.

## .env 양식

`frontend/hpm/.env` 예시입니다.

```dotenv
# Django API base URL
VITE_API_BASE_URL=http://localhost:8000/api
```

## 화면 라우트

대표 라우트는 `frontend/hpm/src/routes/index.tsx`에서 관리합니다.

| 경로 | 역할 |
| --- | --- |
| `/login` | 로그인 |
| `/change-password` | 비밀번호 변경 |
| `/projects` | 프로젝트 선택 |
| `/projects/create` | 프로젝트 생성 |
| `/dashboard` | 칸반 보드 |
| `/meetings` | 회의 목록 |
| `/meetings/create` | 회의 생성 |
| `/meetings/:id/upload` | 회의 자료 업로드 |
| `/meetings/:id/agenda` | 안건 생성/확정 |
| `/meetings/:id/prep-material` | 회의 준비 자료 |
| `/meetings/:id/speaker-mapping` | 화자 매핑 |
| `/meetings/:id/minutes` | 회의록 확인 |
| `/meetings/:id/jira` | Jira 태스크 확인 |
| `/meetings/:id/email` | 회의록 메일 발송 |
| `/documents` | 문서 관리 |
| `/documents/upload` | 문서 업로드 |
| `/members` | 구성원 관리 |
| `/admin/users` | 관리자 사용자 관리 |

## API 호출 구조

API 호출은 `src/services`에 모여 있습니다.

- `users.ts`: 로그인, 로그아웃, 내 정보, 사용자/관리자 API
- `meeting.ts`: 회의 생성, 녹음 종료, 안건, 회의록, 태스크, 알림 관련 API
- `documents.ts`: 문서 업로드, 문서 목록, parsed ingest 상태 조회
- `jira.ts`: Jira OAuth, 보드, 이슈 관련 API

`meeting.ts`의 Axios 인스턴스는 `localStorage`의 `hpm_user.access`를 읽어 `Authorization: Bearer ...` 헤더를 붙이고, 401 응답이 오면 refresh token으로 access token을 갱신합니다.

## 개발 시 주의사항

- 실제 앱 위치는 `frontend/hpm`입니다.
- `node_modules`, `dist`, `.env`는 Git에 올리지 않습니다.
- API base URL은 코드에 직접 박지 말고 `VITE_API_BASE_URL`로 관리합니다.
- 백엔드가 켜져 있지 않으면 로그인과 데이터 조회 화면이 정상 동작하지 않습니다.
- Docker 배포에서는 nginx가 React 정적 파일을 서빙하고 `/api` 요청을 백엔드로 넘기는 구조입니다.
