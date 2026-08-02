# Frontend API E2E verification (2026-08-02)

## Completed checks

- `npm run build` in `frontend/`: passed.
- Backend: Ruff check and format check passed; pytest passed (`318 passed, 1 skipped`).
- Local Supabase containers were running. The backend readiness endpoint returned `200` after using the local database port (`54322`).
- `POST /api/v1/auth/signup`: buyer `201`, seller `201`.
- `POST /api/v1/seller/listings`: `201`.
- `PATCH /api/v1/seller/listings/{listing_id}/terms`: `200`.
- `POST /api/v1/seller/listings/{listing_id}/complete`: `200`.

## Blocked E2E stages

`POST /api/v1/seller/listings/{listing_id}/publish` returned `403` with
`SELLER_NOT_VERIFIED`. New seller signups intentionally create an organization
with `verification_status=pending`; there is no application API for a test
operator to verify it. The test did not bypass that authorization control by
modifying the database.

Therefore the following dependent stages were not executed against a real
published listing: buyer contract request, both-party approval, signature
request creation, and signature status sync/completion.

To reproduce, start the local Supabase stack and API with the local Supabase
URL, publishable key, service-role key, and database URL (asyncpg port `54322`),
then create a seller through `/api/v1/auth/signup`, create and complete a
listing, and call its `/publish` endpoint with the returned seller token and
`X-Organization-Id`. A pending seller receives the documented 403 response.
