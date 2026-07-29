from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ProfileRecord:
    id: UUID
    username: str
    display_name: str
    phone: str | None
    country_code: str | None
    locale: str
    preferred_currency: str
    default_group_name: str | None
    active_organization_id: UUID | None
    active_business_role: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OrganizationRecord:
    id: UUID
    organization_type: str
    name: str
    legal_name: str | None
    business_registration_no: str | None
    verification_status: str
    rating_average: Decimal
    rating_count: int
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None


@dataclass(frozen=True, slots=True)
class OrganizationMembershipRecord:
    organization_id: UUID
    organization_name: str
    organization_type: str
    verification_status: str
    role: str


class ProfileRepository(Protocol):
    async def get_profile(self, user_id: UUID) -> ProfileRecord | None: ...

    async def update_profile(
        self, user_id: UUID, changes: dict[str, Any]
    ) -> ProfileRecord | None: ...

    async def list_memberships(self, user_id: UUID) -> list[OrganizationMembershipRecord]: ...

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationMembershipRecord | None: ...

    async def get_organization(self, organization_id: UUID) -> OrganizationRecord | None: ...

    async def update_organization(
        self, organization_id: UUID, changes: dict[str, Any]
    ) -> OrganizationRecord | None: ...


class DuplicateUsernameError(Exception):
    pass


class RepositoryUnavailableError(Exception):
    pass


class SqlAlchemyProfileRepository:
    _PROFILE_COLUMNS = {
        "username",
        "display_name",
        "phone",
        "country_code",
        "locale",
        "preferred_currency",
        "default_group_name",
    }
    _ORGANIZATION_COLUMNS = {"name", "legal_name", "business_registration_no"}

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_profile(self, user_id: UUID) -> ProfileRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, username, display_name, phone, country_code, locale,
                           preferred_currency, default_group_name, active_organization_id,
                           active_business_role, created_at, updated_at
                    from public.profiles
                    where id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return ProfileRecord(**row) if row else None

    async def update_profile(self, user_id: UUID, changes: dict[str, Any]) -> ProfileRecord | None:
        safe_changes = {
            key: value for key, value in changes.items() if key in self._PROFILE_COLUMNS
        }
        if not safe_changes:
            return await self.get_profile(user_id)
        assignments = ", ".join(f"{key} = :{key}" for key in safe_changes)
        try:
            result = await self._session.execute(
                text(
                    f"""
                    update public.profiles
                    set {assignments}
                    where id = :user_id
                    returning id
                    """  # noqa: S608 - columns are restricted by an allowlist
                ),
                {"user_id": user_id, **safe_changes},
            )
            updated = result.scalar_one_or_none()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise DuplicateUsernameError from exc
            raise RepositoryUnavailableError from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise RepositoryUnavailableError from exc
        return await self.get_profile(user_id) if updated else None

    async def list_memberships(self, user_id: UUID) -> list[OrganizationMembershipRecord]:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.name as organization_name,
                           o.organization_type, o.verification_status, om.role
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id
                    order by o.name, o.id
                    """
                ),
                {"user_id": user_id},
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        return [OrganizationMembershipRecord(**row) for row in result.mappings().all()]

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationMembershipRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select om.organization_id, o.name as organization_name,
                           o.organization_type, o.verification_status, om.role
                    from public.organization_members om
                    join public.organizations o on o.id = om.organization_id
                    where om.user_id = :user_id and om.organization_id = :organization_id
                    """
                ),
                {"user_id": user_id, "organization_id": organization_id},
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return OrganizationMembershipRecord(**row) if row else None

    async def get_organization(self, organization_id: UUID) -> OrganizationRecord | None:
        try:
            result = await self._session.execute(
                text(
                    """
                    select id, organization_type, name, legal_name, business_registration_no,
                           verification_status, rating_average, rating_count, created_at,
                           updated_at, verified_at
                    from public.organizations
                    where id = :organization_id
                    """
                ),
                {"organization_id": organization_id},
            )
        except SQLAlchemyError as exc:
            raise RepositoryUnavailableError from exc
        row = result.mappings().one_or_none()
        return OrganizationRecord(**row) if row else None

    async def update_organization(
        self, organization_id: UUID, changes: dict[str, Any]
    ) -> OrganizationRecord | None:
        safe_changes = {
            key: value for key, value in changes.items() if key in self._ORGANIZATION_COLUMNS
        }
        if not safe_changes:
            return await self.get_organization(organization_id)
        assignments = ", ".join(f"{key} = :{key}" for key in safe_changes)
        try:
            result = await self._session.execute(
                text(
                    f"""
                    update public.organizations
                    set {assignments}
                    where id = :organization_id
                    returning id
                    """  # noqa: S608 - columns are restricted by an allowlist
                ),
                {"organization_id": organization_id, **safe_changes},
            )
            updated = result.scalar_one_or_none()
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise RepositoryUnavailableError from exc
        return await self.get_organization(organization_id) if updated else None
