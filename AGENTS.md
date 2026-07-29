# AGENTS.md

이 문서는 BusanLink 저장소에서 개발하는 사람과 AI 에이전트가 따라야 할 공통 규칙이다.

## 1. 서비스 개요

BusanLink는 부산 관광 셀러가 계약 가능한 상품 공고를 게시하고, 외국인 개인 바이어가 계약 내용을 AI로 검토한 뒤 서명하거나 조항 수정을 요청하는 서비스다.

핵심 모델은 다음과 같다.

- `listing`: 여러 바이어에게 공개되는 셀러의 상품·계약 공고
- `contract`: 특정 개인 바이어가 공고를 선택해 생성한 실제 계약
- 공고에서 계약을 만들 때 현재 공고 내용과 조항을 계약에 복사한다.
- 공고나 계약 내용을 수정할 때 기존 버전을 덮어쓰지 않고 새 버전을 만든다.
- 단체 여행이어도 계약 당사자는 개인 바이어 한 명이다.
- MVP 단체 서명은 대표자 한 명의 서명이며 참가자 전체의 다중 서명이 아니다.

## 2. 기술 스택

- Frontend: React, Vite
- Backend: Python 3.12, FastAPI, Pydantic v2
- Database: Supabase PostgreSQL
- Authentication: Supabase Auth
- File Storage: Supabase Storage
- Database access: SQLAlchemy async, asyncpg
- AI: Upstage Document Parse, Information Extract, Solar Pro 3
- RAG: Upstage Files, Vector Store, File Search
- Test and lint: pytest, Ruff

## 3. 저장소 구조

```text
frontend/                 React 애플리케이션
backend/
  app/
    api/                  FastAPI router
    core/                 설정, 인증, 오류, 공통 기능
    domain/               업무 규칙과 상태 전이
    repositories/         DB 접근
    schemas/              API 및 AI 입출력 schema
    integrations/         Supabase, Upstage, 모두싸인 adapter
    ai/
      tasks/              생성, 요약, 번역 등 고정 AI 함수
      agents/             contract_review 단일 Agent
      tools/              Agent가 사용할 수 있는 제한된 도구
      prompts/            버전이 지정된 prompt
  tests/
docs/                     API, DB, AI 및 협업 문서
supabase/migrations/      순서대로 적용하는 SQL migration
```

새 코드는 역할에 맞는 디렉터리에 둔다. Router에 업무 규칙이나 SQL을 직접 작성하지 않는다.

## 4. 로컬 실행과 검사

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

변경을 완료하기 전에 다음 명령을 모두 실행한다.

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

## 5. API 규칙

- 일반 API prefix는 `/api/v1`이다.
- `/public/**`, `/auth/**`, `/health/**`만 인증 없이 접근할 수 있다.
- 셀러 조직 API는 `X-Organization-Id`를 사용한다.
- 개인 바이어 권한은 로그인한 Supabase `auth.uid()`를 기준으로 검사한다.
- service role은 RLS를 우회하므로 repository 호출 전에 애플리케이션 권한을 반드시 확인한다.
- 금액은 정수 `amount_minor`로 처리한다.
- timestamp는 UTC ISO 8601 형식으로 처리한다.
- 외부 부작용이나 비용이 있는 POST 요청은 `Idempotency-Key`를 지원한다.

성공 응답:

```json
{
  "data": {},
  "meta": { "request_id": "..." }
}
```

오류 응답:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "오류 설명",
    "details": {},
    "request_id": "..."
  }
}
```

## 6. 공통 값

상품 카테고리는 다음 값만 사용한다.

- `vehicle_rental`
- `activity`
- `tour`
- `accommodation`

지원 언어는 다음 값만 사용한다.

- `ko-KR`
- `en-US`
- `ja-JP`
- `zh-CN`

공고 상태:

- `draft`, `processing`, `ready`, `published`, `paused`, `expired`, `archived`

계약 상태:

- `draft`, `seller_review`, `revision_requested`, `signing`, `signed`, `cancelled`

상태 변경은 domain service에서만 수행하고 허용되지 않은 변경은 `INVALID_STATE_TRANSITION`으로 처리한다.

## 7. 데이터베이스 규칙

- DB 변경은 기존 migration을 수정하지 않고 새 migration으로 추가한다.
- 깨끗한 DB에서 migration이 순서대로 적용되는지 확인한다.
- version 테이블의 기존 행은 수정하지 않는다.
- 계약 당사자 정보는 계약 생성 당시 snapshot으로 보존한다.
- 비밀번호와 password hash를 애플리케이션 DB에 저장하지 않는다.
- 감사 기록은 append-only로 관리한다.
- 공개 API는 필요한 컬럼만 명시적으로 반환하고 개인정보를 노출하지 않는다.

## 8. AI 개발 규칙

FastAPI가 전체 작업 순서와 상태 변경을 결정한다. AI는 구조화된 결과를 반환할 뿐 공고 게시, 계약 변경, 서명을 직접 실행하지 않는다.

고정 함수로 구현할 작업:

- Document Parse
- Information Extract
- 계약 초안 생성
- 공개 요약
- 다국어 번역과 쉬운 설명
- 수정 요청 문구 초안

Agent는 `contract_review` 하나만 사용한다. Agent가 사용할 수 있는 도구는 다음 네 개로 제한한다.

- `get_clause_context`
- `search_official_evidence`
- `search_approved_templates`
- `submit_review`

검색 반복은 최대 2회다. 근거가 부족하면 내용을 만들어내지 않고 `insufficient_evidence`로 반환한다.

추가 규칙:

- AI 입출력은 Pydantic 또는 JSON Schema로 검증한다.
- 가격 계산은 Python 코드가 담당하고 AI는 설명만 생성한다.
- AI 추천 문구는 사용자가 적용하기 전까지 계약서에 반영하지 않는다.
- 셀러 분석 결과를 공개 바이어 API에 노출하지 않는다.
- 번역 후 금액, 날짜, 비율, 근거 번호가 유지되는지 코드로 검사한다.
- 사용자 계약서는 공용 Vector Store에 넣지 않는다.
- 공식 자료와 팀이 승인한 템플릿만 RAG 지식베이스에 넣는다.
- 실제 provider가 없어도 전체 흐름을 테스트할 수 있도록 fake provider를 제공한다.

## 9. 보안과 로그

다음 값을 Git이나 로그에 남기지 않는다.

- `.env`와 API key
- Supabase service role key
- 전체 계약서 원문
- 비밀번호
- 사업자번호, 이메일, 전화번호 등 개인정보
- 외부 provider의 임시 다운로드 URL

로그에는 request ID, job ID, 대상 version ID, task type, model, prompt version, 처리 시간과 provider 상태 같은 비민감 정보만 기록한다.

## 10. 테스트 기준

모든 API 구현에는 최소한 다음 테스트를 함께 작성한다.

- 정상 요청
- 인증 또는 권한 실패
- 잘못된 상태 변경
- version 충돌
- 외부 provider 실패
- 중복 요청과 idempotency
- 공개 API의 내부 정보 비노출

AI 기능은 추가로 다음을 검사한다.

- JSON Schema 검증 실패
- timeout, 429, 일시적 5xx 재시도
- Agent 도구 allowlist와 최대 2회 반복
- 근거 부족 처리
- 숫자와 날짜 보존
- prompt injection이 포함된 계약 원문 처리

## 11. Git 협업 규칙

- PR, 이슈, 커밋은 원본 저장소(`ApptiveDev/AI-Builder-Sprint`)가 아닌 팀에서 포크한 저장소에서만 진행한다.
- `main`에 직접 커밋하거나 push하지 않는다.
- 최신 `main`에서 작업 브랜치를 만든다.
- 브랜치 이름은 `feature/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/` 규칙을 따른다.
- 한 브랜치에는 하나의 논리적 작업만 포함한다.
- API 코드와 해당 테스트를 같은 브랜치에서 작성한다.
- 커밋 메시지는 `<type>[(scope)]: <summary>` 형식을 사용한다.
- 사용자 요청 없이 원격 push, PR 생성 또는 병합을 하지 않는다.
- 기존 사용자 변경을 덮어쓰거나 되돌리지 않는다.

## 12. 완료 기준

작업은 다음 조건을 모두 만족해야 완료로 본다.

- API 명세와 request, response, error code가 일치한다.
- 필요한 migration과 테스트가 포함되어 있다.
- Ruff와 pytest가 통과한다.
- 새 환경변수가 실제 값 없이 `.env.example`에 추가되어 있다.
- Swagger에서 endpoint와 schema를 확인할 수 있다.
- secret, 개인정보, 실제 계약 파일이 변경사항에 포함되지 않는다.
