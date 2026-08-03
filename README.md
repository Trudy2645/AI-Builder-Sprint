# 찍어보소

부산 관광 셀러가 상품과 계약 조건을 공고하고, 외국인 개인 바이어가 AI의 도움을 받아 계약 내용을 검토·협의한 뒤 전자서명할 수 있는 B2B 관광 계약 서비스입니다.

## 주요 기능

- 셀러의 관광 상품 공고 등록·게시 및 판매 가능 조건 관리
- 외국인 바이어의 상품 탐색, 견적 확인, 계약 요청
- 계약서 파일 파싱과 핵심 정보 추출
- AI 기반 계약 조항 검토, 위험 요소·근거 안내, 쉬운 설명과 다국어 번역
- 계약 조건 수정 요청 및 셀러-바이어 협의
- 모두싸인 연동 전자서명과 계약 상태·알림 관리
- 공식 자료와 승인된 템플릿을 활용한 근거 기반 검색(RAG)

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | React, TypeScript, Vite, MUI, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, asyncpg |
| Database / Auth / Storage | Supabase PostgreSQL, Supabase Auth, Supabase Storage |
| AI / RAG | Upstage Document Parse, Information Extract, Solar Pro 3, Files, Vector Store, File Search |
| 전자서명 | 모두싸인 API |
| Test / Lint | pytest, pytest-asyncio, Ruff |

## 실행·배포 환경

| 영역 | 환경 및 실행 방식 |
| --- | --- |
| Frontend 개발 | Node.js와 npm, Vite 개발 서버(`http://localhost:5173`) |
| Frontend 배포 | `npm run build`로 생성한 `frontend/dist` 정적 파일을 정적 호스팅 또는 CDN에 배포 |
| Backend 개발 | Python 3.12, FastAPI/Uvicorn(`http://127.0.0.1:8000`) |
| Backend 배포 | Uvicorn을 실행할 수 있는 ASGI 환경에서 `app.main:app` 실행. 배포 시 `--host 0.0.0.0`과 플랫폼의 포트를 사용 |
| 데이터·인증·파일 | Supabase PostgreSQL, Auth, Storage |
| 외부 연동 | Upstage AI와 모두싸인 API. 로컬 기본 AI provider는 `fake`로 외부 API 없이 흐름을 확인 가능 |

저장소에는 특정 배포 플랫폼에 종속된 설정을 두지 않았습니다. 배포 환경에서는 환경변수를 Secret Manager에 등록하고, 프론트엔드의 실제 도메인을 백엔드 `CORS_ORIGINS`에 추가합니다.

## 프로젝트 구조

```text
.
├── frontend/                 # React + Vite 사용자 화면
├── backend/
│   ├── app/api/              # FastAPI router
│   ├── app/domain/           # 업무 규칙과 상태 전이
│   ├── app/repositories/     # 데이터베이스 접근
│   ├── app/ai/               # AI task, agent, tool, prompt
│   ├── app/integrations/     # Supabase, Upstage, 모두싸인 연동
│   ├── docs/                 # 백엔드 API·DB·AI·RAG 명세
│   └── tests/                # 백엔드 테스트
├── rag/                      # RAG 지식베이스 관련 자료
├── supabase/migrations/      # 순서대로 적용하는 DB migration
├── docs/                     # 브랜치·커밋·이슈·PR 협업 문서
├── AGENTS.md                 # 저장소 개발 규칙
└── README.md
```

## 로컬 기동 실행 가이드

### 사전 준비

- Python 3.12
- Node.js와 npm
- 전체 API를 사용하려면 Supabase 프로젝트와 필요한 외부 API 키

### Frontend

```bash
set -e
cd "$(git rev-parse --show-toplevel)/frontend"

npm install

if [ ! -f .env ]; then
  cp .env.example .env
fi

npm run dev
```

### Backend

```bash
set -e
cd "$(git rev-parse --show-toplevel)/backend"

if [ ! -x .venv/bin/python ] || [ ! -x .venv/bin/pip ]; then
  python3.12 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -e '.[dev]'

if [ ! -f .env ]; then
  cp .env.example .env
fi

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

프론트엔드와 백엔드를 각각 실행한 뒤 API 문서는 [http://localhost:8000/docs](http://localhost:8000/docs)에서 확인할 수 있습니다. 백엔드의 생존 확인 endpoint는 `GET /health/live`, 준비 상태 확인 endpoint는 `GET /health/ready`입니다.

### 검사 및 빌드

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest

cd ../frontend
npm run build
```

## 환경변수 정보

실제 키와 개인정보는 `.env` 또는 배포 환경의 Secret Manager에만 저장하고 Git에 커밋하지 않습니다. 예시 파일은 [`frontend/.env.example`](frontend/.env.example)와 [`backend/.env.example`](backend/.env.example)에서 확인할 수 있습니다.

### Frontend (`frontend/.env`)

| 변수 | 설명 |
| --- | --- |
| `VITE_API_BASE_URL` | 백엔드 API 주소. 기본값은 `http://localhost:8000/api/v1` |
| `VITE_SELLER_ORGANIZATION_ID` | 셀러 화면에서 사용할 조직 ID |
| `VITE_API_ACCESS_TOKEN` | 로컬 API 연동용 access token. 실제 토큰을 저장소에 남기지 않음 |
| `VITE_SHOW_TEST_DATA` | 테스트 데이터 표시 여부. 기본값 `false` |

### Backend (`backend/.env`)

| 변수 | 설명 |
| --- | --- |
| `APP_ENVIRONMENT` | 실행 환경. 로컬 기본값 `local` |
| `DOCS_ENABLED` | OpenAPI 문서 노출 여부 |
| `DATABASE_URL` | `postgresql+asyncpg://...` 형식의 Supabase PostgreSQL 연결 문자열 |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_PUBLISHABLE_KEY` | 프론트엔드·인증에 사용하는 publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | 서버 전용 service role key. 절대 클라이언트에 노출하지 않음 |
| `SUPABASE_JWKS_URL` | 선택값. 비워두면 Supabase URL에서 JWKS 주소를 자동 구성 |
| `AUTH_PASSWORD_RESET_REDIRECT_URL` | 비밀번호 재설정 redirect URL |
| `CORS_ORIGINS` | 허용할 프론트엔드 origin 목록(JSON 배열) |
| `AI_PROVIDER` | `fake` 또는 `upstage`. 로컬 기본값은 `fake` |
| `UPSTAGE_API_KEY` | Upstage API key |
| `UPSTAGE_OFFICIAL_VECTOR_STORE_ID` | 공식 자료 RAG vector store ID |
| `UPSTAGE_TEMPLATE_VECTOR_STORE_ID` | 승인 템플릿 RAG vector store ID |
| `UPSTAGE_CASE_VECTOR_STORE_ID` | 계약 사례 RAG vector store ID |
| `MODUSIGN_API_KEY` | 모두싸인 API key |
| `MODUSIGN_AUTH_EMAIL` | 모두싸인 인증 이메일 |
| `MODUSIGN_TEMPLATE_ID` | 전자서명 템플릿 ID |
| `MODUSIGN_WEBHOOK_SECRET` | 모두싸인 webhook 검증 secret |
| `DEMO_LOGIN_ENABLED` | 개발·데모 로그인 활성화 여부. 기본값 `false` |

`SUPABASE_SERVICE_ROLE_KEY`, `UPSTAGE_API_KEY`, `MODUSIGN_API_KEY`, webhook secret, 데이터베이스 비밀번호와 access token은 로그·이슈·채팅에도 남기지 않습니다. 상세한 Supabase 인증 설정은 [`backend/README.md`](backend/README.md)를 참고하세요.

## AI 활용 방식

### 서비스에서의 활용

Upstage 기능은 역할별로 나누어 사용하며, 자세한 설계는 [`AI_UPSTAGE_ARCHITECTURE.md`](backend/docs/AI_UPSTAGE_ARCHITECTURE.md)에서 확인할 수 있습니다.

| Upstage 기능 | 활용 목적 | 서비스 적용 방식 |
| --- | --- | --- |
| Document Parse | 계약서의 텍스트·페이지·레이아웃 파싱 | 업로드된 계약서를 파싱하고 결과 artifact를 저장합니다. |
| Information Extract<br>(Universal Extraction adapter) | 계약 조건의 구조화 | 요금, 기간, 취소·환불, 안전·보상·책임 등 핵심 정보를 JSON schema로 추출합니다. |
| Solar Pro 3 | 생성·요약·번역·계약 검토 | 고정 task와 `contract_review` 단일 Agent에 사용합니다. AI는 설명과 검토 결과를 반환하고 가격 계산은 Python 코드가 담당합니다. |
| Files / Vector Store | 승인된 지식베이스 관리 | 공식 자료, 팀 승인 템플릿, 승인된 사례만 적재·색인합니다. 사용자 계약서 원문은 공용 Vector Store에 넣지 않습니다. |
| File Search | 검토 근거 검색 | `contract_review` Agent가 공식 근거와 승인 템플릿을 검색하고 page, excerpt, score를 활용해 근거를 연결합니다. |
| Agents API 연동 | 제한형 계약 검토 실행 | `get_clause_context`, `search_official_evidence`, `search_approved_templates`, `submit_review`만 허용하고 검색 반복은 최대 2회로 제한합니다. |

AI는 구조화된 결과와 설명만 반환하며, 공고 게시·계약 변경·서명 같은 상태 변경은 FastAPI와 domain service가 수행합니다. 외부 provider가 없어도 `AI_PROVIDER=fake`로 전체 흐름을 테스트할 수 있습니다.

### 개발 과정에서의 활용

- 저장소 공통 규칙은 [`AGENTS.md`](AGENTS.md)를 기준으로 확인하고, API·DB·AI 명세와 구현의 일관성을 점검했습니다.
- Codex를 코드 탐색, 문서 초안 작성, 오류 원인 확인, 테스트·lint·빌드 검증에 활용했습니다.
- AI가 생성한 제안은 바로 계약에 반영하지 않고, schema 검증과 서버 검증을 거친 뒤 사용자가 적용하도록 구성했습니다.

## 팀 협업

작업 전 이슈를 만들고, 최신 `main`에서 `feature/`, `fix/`, `docs/` 등의 작업 브랜치를 생성합니다. 변경 후 테스트와 리뷰를 거쳐 PR로 `main`에 병합합니다.

- [브랜치 전략](docs/branch_strategy.md)
- [커밋 전략](docs/commit_strategy.md)
- [이슈 전략](docs/issue_strategy.md)
- [PR 전략](docs/pr_strategy.md)
