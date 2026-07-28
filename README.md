# BusanLink

계약서를 안전하게 보관하고, AI 검색으로 필요한 내용을 빠르게 찾는 계약 관리 서비스입니다.

## 주요 기능

- 계약서 파일 업로드 및 안전한 보관
- 계약서 내용 파싱과 핵심 정보 추출
- 자연어 질문 기반 계약서 검색(RAG)
- 검색 결과에서 근거가 된 계약서 내용 확인

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | React, Vite |
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| File Storage | Supabase Storage |
| AI / RAG | Upstage Document Parse, Information Extract, Solar Pro, Files, Vector Store, File Search |

## 프로젝트 구조

```text
busan_link/
├── frontend/        # React + Vite 사용자 화면
├── backend/         # FastAPI API 서버 및 AI 연동
├── .gitignore
├── .env.example     # 환경 변수 예시 (실제 키는 포함하지 않음)
└── README.md
```

## 시작하기

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 환경 변수

실제 키는 각자의 `.env` 파일에만 저장하며 GitHub에 올리지 않습니다.

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
UPSTAGE_API_KEY=
UPSTAGE_VECTOR_STORE_ID=
```

`SUPABASE_SERVICE_ROLE_KEY`와 `UPSTAGE_API_KEY`는 백엔드에서만 사용합니다.

## 팀 협업

모든 작업은 `main`에서 만든 작업 브랜치에서 진행하고, PR 리뷰 후 `main`으로 병합합니다.

```bash
git switch main
git pull origin main
git switch -c feature/short-description
```

자세한 규칙은 [협업 가이드](docs/branch_strategy.md)를 참고하세요.
