from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_session_factory

LISTING_IDS = {
    "coastline-hotel-room-2026": UUID("11111111-1111-4111-8111-111111111111"),
    "bluewave-surf-lesson-2026": UUID("22222222-2222-4222-8222-222222222222"),
    "route-rental-van-2026": UUID("33333333-3333-4333-8333-333333333333"),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_frontend_contracts() -> list[dict[str, Any]]:
    root = _repo_root()
    source = root / "frontend" / "src" / "app" / "data" / "contracts.ts"
    esbuild = root / "frontend" / "node_modules" / ".bin" / "esbuild"
    if not esbuild.exists():
        raise RuntimeError("Frontend dependencies are missing. Run `npm ci` in frontend/.")

    with tempfile.TemporaryDirectory(prefix="busanlink-demo-seed-") as temp_dir:
        bundle = Path(temp_dir) / "contracts.cjs"
        subprocess.run(
            [
                str(esbuild),
                str(source),
                "--platform=node",
                "--format=cjs",
                f"--outfile={bundle}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [
                "node",
                "-e",
                "process.stdout.write(JSON.stringify(require(process.argv[1]).contracts))",
                str(bundle),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    contracts = json.loads(result.stdout)
    source_ids = {item["id"] for item in contracts}
    if source_ids != set(LISTING_IDS):
        raise RuntimeError(f"Unexpected frontend demo IDs: {sorted(source_ids)}")
    return contracts


def _stable_uuid(kind: str, source_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://busan-link.local/demo/{kind}/{source_id}")


def _date(value: str) -> date:
    return date.fromisoformat(value.replace(".", "-"))


def _supply_values(item: dict[str, Any]) -> dict[str, Any]:
    source_id = item["id"]
    if source_id == "coastline-hotel-room-2026":
        return {
            "supply_quantity": 32,
            "quantity_unit": "room",
            "minimum_quantity": 10,
            "maximum_quantity": 32,
            "people_per_unit": 2,
            "minimum_people": 1,
            "maximum_people": 64,
        }
    if source_id == "bluewave-surf-lesson-2026":
        return {
            "supply_quantity": 45,
            "quantity_unit": "person",
            "minimum_quantity": 20,
            "maximum_quantity": 45,
            "people_per_unit": 1,
            "minimum_people": 20,
            "maximum_people": 45,
        }
    return {
        "supply_quantity": 12,
        "quantity_unit": "vehicle",
        "minimum_quantity": 1,
        "maximum_quantity": 12,
        "people_per_unit": 8,
        "minimum_people": 1,
        "maximum_people": 96,
    }


async def _seed(contracts: list[dict[str, Any]]) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    factory = get_session_factory(settings.database_url)
    async with factory.begin() as session:
        owner = (
            (
                await session.execute(
                    text(
                        """
                    select om.user_id, o.id as organization_id
                    from public.organizations o
                    join public.organization_members om on om.organization_id = o.id
                    where o.name = :seller_name
                      and o.organization_type = 'seller'
                    order by case om.role when 'owner' then 0 else 1 end, om.created_at
                    limit 1
                    """
                    ),
                    {"seller_name": contracts[0]["seller"]},
                )
            )
            .mappings()
            .one_or_none()
        )
        if owner is None:
            raise RuntimeError(
                "A seller member for the first demo organization is required before seeding."
            )
        owner_user_id = owner["user_id"]

        for item in contracts:
            source_id = item["id"]
            listing_id = LISTING_IDS[source_id]
            version_id = _stable_uuid("listing-version", source_id)
            organization_id = (
                owner["organization_id"]
                if item["seller"] == contracts[0]["seller"]
                else _stable_uuid("organization", item["seller"])
            )

            await session.execute(
                text(
                    """
                    insert into public.organizations (
                        id, organization_type, name, verification_status,
                        rating_average, rating_count, created_by, verified_at
                    ) values (
                        :id, 'seller', :name, 'verified', 4.80, 24, :owner, now()
                    )
                    on conflict (id) do update set
                        name = excluded.name,
                        verification_status = 'verified',
                        verified_at = coalesce(public.organizations.verified_at, now())
                    """
                ),
                {"id": organization_id, "name": item["seller"], "owner": owner_user_id},
            )
            await session.execute(
                text(
                    """
                    insert into public.organization_members (
                        id, organization_id, user_id, role
                    ) values (:id, :organization_id, :user_id, 'owner')
                    on conflict (organization_id, user_id) do nothing
                    """
                ),
                {
                    "id": _stable_uuid("organization-member", f"{organization_id}:{owner_user_id}"),
                    "organization_id": organization_id,
                    "user_id": owner_user_id,
                },
            )

            await session.execute(
                text(
                    """
                    insert into public.listings (
                        id, seller_organization_id, status, creation_method,
                        title, display_title, display_company_name, district,
                        category, language, public_headline, ai_summary,
                        popularity_score, published_at, created_by
                    ) values (
                        :id, :organization_id, 'published', 'manual',
                        :title, :title, :seller, :district,
                        cast(:category as public.contract_category), 'ko-KR',
                        :headline, :ai_summary, :popularity, now(), :owner
                    )
                    on conflict (id) do update set
                        seller_organization_id = excluded.seller_organization_id,
                        status = 'published',
                        display_title = excluded.display_title,
                        display_company_name = excluded.display_company_name,
                        district = excluded.district,
                        category = excluded.category,
                        public_headline = excluded.public_headline,
                        ai_summary = excluded.ai_summary,
                        popularity_score = excluded.popularity_score,
                        published_at = coalesce(public.listings.published_at, now())
                    """
                ),
                {
                    "id": listing_id,
                    "organization_id": organization_id,
                    "title": item["title"],
                    "seller": item["seller"],
                    "district": item["district"],
                    "category": item["category"],
                    "headline": item["aiSummary"][0],
                    "ai_summary": "\n".join(item["aiSummary"]),
                    "popularity": item["popularity"],
                    "owner": owner_user_id,
                },
            )

            terms = {
                **_supply_values(item),
                "listing_id": listing_id,
                "start_date": _date(item["start"]),
                "end_date": _date(item["end"]),
                "supply_description": item["details"]["supplyQuantity"],
                "amount": item["unitPrice"],
                "price_unit": item["priceUnit"],
                "cancellation": item["details"]["cancellation"],
                "no_show": item["details"]["noShow"],
                "settlement": item["details"]["settlement"],
            }
            await session.execute(
                text(
                    """
                    insert into public.listing_terms (
                        listing_id, service_start_date, service_end_date,
                        supply_quantity, supply_quantity_description, quantity_unit,
                        minimum_quantity, maximum_quantity, people_per_unit,
                        base_price_amount_minor, currency, price_unit,
                        minimum_people, maximum_people, cancellation_policy,
                        no_show_policy, settlement_policy, price_display_basis,
                        contract_availability_note
                    ) values (
                        :listing_id, :start_date, :end_date,
                        :supply_quantity, :supply_description, :quantity_unit,
                        :minimum_quantity, :maximum_quantity, :people_per_unit,
                        :amount, 'KRW', :price_unit,
                        :minimum_people, :maximum_people, :cancellation,
                        :no_show, :settlement, :price_unit, '데모 계약 요청 가능'
                    )
                    on conflict (listing_id) do update set
                        service_start_date = excluded.service_start_date,
                        service_end_date = excluded.service_end_date,
                        supply_quantity = excluded.supply_quantity,
                        supply_quantity_description = excluded.supply_quantity_description,
                        quantity_unit = excluded.quantity_unit,
                        minimum_quantity = excluded.minimum_quantity,
                        maximum_quantity = excluded.maximum_quantity,
                        people_per_unit = excluded.people_per_unit,
                        base_price_amount_minor = excluded.base_price_amount_minor,
                        currency = excluded.currency,
                        price_unit = excluded.price_unit,
                        minimum_people = excluded.minimum_people,
                        maximum_people = excluded.maximum_people,
                        cancellation_policy = excluded.cancellation_policy,
                        no_show_policy = excluded.no_show_policy,
                        settlement_policy = excluded.settlement_policy
                    """
                ),
                terms,
            )

            body = "\n\n".join(
                f"{clause['no']} {clause['title']}\n{clause['text']}" for clause in item["clauses"]
            )
            await session.execute(
                text(
                    """
                    insert into public.listing_versions (
                        id, listing_id, version_no, title, body, content_sha256,
                        structured_data, created_by
                    ) values (
                        :id, :listing_id, 1, :title, :body, :content_sha256,
                        cast(:structured_data as jsonb), :owner
                    )
                    on conflict (id) do nothing
                    """
                ),
                {
                    "id": version_id,
                    "listing_id": listing_id,
                    "title": item["title"],
                    "body": body,
                    "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "structured_data": json.dumps(
                        {
                            "demo_source_id": source_id,
                            "image_url": item["image"],
                            "ai_summary": item["aiSummary"],
                            "details": item["details"],
                        },
                        ensure_ascii=False,
                    ),
                    "owner": owner_user_id,
                },
            )
            for order, clause in enumerate(item["clauses"], start=1):
                await session.execute(
                    text(
                        """
                        insert into public.listing_clauses (
                            id, listing_version_id, clause_order, clause_key, title, body
                        ) values (:id, :version_id, :clause_order, :clause_key, :title, :body)
                        on conflict (id) do nothing
                        """
                    ),
                    {
                        "id": _stable_uuid("listing-clause", f"{source_id}:{order}"),
                        "version_id": version_id,
                        "clause_order": order,
                        "clause_key": clause["no"],
                        "title": clause["title"],
                        "body": clause["text"],
                    },
                )
            await session.execute(
                text("update public.listings set current_version_id = :version_id where id = :id"),
                {"version_id": version_id, "id": listing_id},
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed frontend demo listings into the DB.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required because this command writes to the configured database.",
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Pass --confirm to write the frontend demo data.")
    contracts = _load_frontend_contracts()
    asyncio.run(_seed(contracts))
    print(f"Seeded {len(contracts)} demo listings.")


if __name__ == "__main__":
    main()
