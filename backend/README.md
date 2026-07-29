# BusanLink Backend

구현 기준 문서는 [`docs/`](docs/)에서 확인할 수 있습니다.

## Local setup

Python 3.12 is required.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

API documentation is available at <http://localhost:8000/docs>.

## Checks

```bash
ruff check .
ruff format --check .
pytest
```

`GET /health/live` checks the API process. `GET /health/ready` additionally checks the
database connection configured by `DATABASE_URL`.
