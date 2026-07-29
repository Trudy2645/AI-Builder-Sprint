import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.integration


def test_real_supabase_token_and_database_profile_smoke() -> None:
    if os.getenv("RUN_SUPABASE_SMOKE") != "1":
        pytest.skip("Set RUN_SUPABASE_SMOKE=1 to run the real Supabase smoke test.")
    access_token = os.getenv("SUPABASE_SMOKE_ACCESS_TOKEN")
    if not access_token:
        pytest.fail("SUPABASE_SMOKE_ACCESS_TOKEN is required when smoke testing is enabled.")

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        UUID(response.json()["data"]["id"])

        organization_id = os.getenv("SUPABASE_SMOKE_ORGANIZATION_ID")
        if organization_id:
            organization_response = client.get(
                f"/api/v1/organizations/{UUID(organization_id)}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Organization-Id": organization_id,
                },
            )
            assert organization_response.status_code == 200
