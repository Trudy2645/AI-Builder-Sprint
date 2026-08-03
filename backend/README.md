# 찍어보소 Backend

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

## Supabase authentication configuration

찍어보소 keeps passwords in Supabase Auth only. The frontend signs users in with
Supabase, then sends the returned access token as `Authorization: Bearer <token>`.
FastAPI verifies asymmetric tokens with the project's public JWKS. Projects still using
the legacy HS256 signing secret are verified through the Supabase Auth `/user` endpoint;
the JWT secret itself is not needed by this application.

Copy `.env.example` to `.env` and fill only the local file:

1. In Supabase Dashboard, open **Project Settings → API Keys**. Copy the project URL to
   `SUPABASE_URL` and the publishable key to `SUPABASE_PUBLISHABLE_KEY`. A legacy `anon`
   key can be used only while the project still uses legacy API keys.
2. Open **Authentication → Signing Keys**. Prefer an active asymmetric ES256 or RS256
   signing key. `SUPABASE_JWKS_URL` normally stays empty because FastAPI derives
   `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` automatically.
3. Use the Dashboard **Connect** dialog's SQLAlchemy/asyncpg connection details for
   `DATABASE_URL`. Change the scheme to `postgresql+asyncpg://` when necessary. This is
   a direct PostgreSQL connection and does not require Supabase Data API to be enabled.
4. Keep `SUPABASE_SERVICE_ROLE_KEY`, database passwords, access tokens, and all other
   secrets only in `.env` or a secret manager. Never paste them into source, tests, logs,
   issues, or chat.
5. Set `AUTH_PASSWORD_RESET_REDIRECT_URL` to the frontend page that accepts Supabase
   recovery links. Add the same URL to the Supabase Auth redirect allowlist.

Demo login is disabled by default. In a development/demo environment only, set
`DEMO_LOGIN_ENABLED=true` and provide the buyer/seller demo email and password variables
from `.env.example`. Never enable this endpoint with privileged or production accounts.

The official references are [Supabase JWT verification](https://supabase.com/docs/guides/auth/jwts)
and [JWT signing keys](https://supabase.com/docs/guides/auth/signing-keys).

### Optional real Supabase smoke test

Normal tests use `FakeAuthProvider` and never contact Supabase. To opt into the real
token/database smoke test, create a disposable Auth user that already has a `profiles`
row, put its short-lived access token in the shell environment (not in Git), and run:

```bash
RUN_SUPABASE_SMOKE=1 \
SUPABASE_SMOKE_ACCESS_TOKEN='<short-lived-access-token>' \
.venv/bin/pytest -m integration tests/integration/test_supabase_auth_smoke.py
```

For a seller membership, optionally add `SUPABASE_SMOKE_ORGANIZATION_ID`. Unset the
token after the test. The regular suite skips this test unless explicitly enabled.
