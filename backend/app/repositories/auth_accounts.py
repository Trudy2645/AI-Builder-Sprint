from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class RegistrationRecord:
    user_id: UUID
    organization_id: UUID | None


class RegistrationRepository(Protocol):
    async def create_buyer(self, values: dict[str, Any]) -> RegistrationRecord: ...

    async def create_seller(self, values: dict[str, Any]) -> RegistrationRecord: ...


class RegistrationRepositoryError(Exception):
    pass


class RegistrationConflictError(Exception):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(field)


class SqlAlchemyRegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_buyer(self, values: dict[str, Any]) -> RegistrationRecord:
        try:
            await self._prepare_transaction()
            async with self._session.begin():
                await self._session.execute(
                    text(
                        """
                        insert into public.profiles (
                            id, username, display_name, phone, country_code, locale,
                            preferred_currency, default_group_name, affiliation_name,
                            business_type, active_business_role
                        ) values (
                            :user_id, :username, :display_name, :phone, :country_code,
                            cast(:locale as public.supported_locale), :preferred_currency,
                            :default_group_name, :affiliation_name, :business_type, 'buyer'
                        )
                        """
                    ),
                    values,
                )
            return RegistrationRecord(user_id=values["user_id"], organization_id=None)
        except IntegrityError as exc:
            await self._session.rollback()
            self._raise_conflict(exc)
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise RegistrationRepositoryError from exc

    async def create_seller(self, values: dict[str, Any]) -> RegistrationRecord:
        try:
            await self._prepare_transaction()
            async with self._session.begin():
                organization_result = await self._session.execute(
                    text(
                        """
                        insert into public.organizations (
                            organization_type, name, legal_name, representative_name,
                            business_registration_no, business_address, supply_categories,
                            verification_status, created_by
                        ) values (
                            'seller', :organization_name, :legal_name, :representative_name,
                            :business_registration_no, :business_address,
                            cast(:supply_categories as public.contract_category[]),
                            'pending', :user_id
                        )
                        returning id
                        """
                    ),
                    values,
                )
                organization_id = organization_result.scalar_one()
                await self._session.execute(
                    text(
                        """
                        insert into public.profiles (
                            id, username, display_name, phone, country_code, locale,
                            preferred_currency, active_organization_id, active_business_role
                        ) values (
                            :user_id, :username, :display_name, :phone, 'KR', 'ko-KR',
                            'KRW', :organization_id, 'seller'
                        )
                        """
                    ),
                    {**values, "organization_id": organization_id},
                )
                await self._session.execute(
                    text(
                        """
                        insert into public.organization_members (
                            organization_id, user_id, role, job_title
                        ) values (:organization_id, :user_id, 'owner', :job_title)
                        """
                    ),
                    {**values, "organization_id": organization_id},
                )
            return RegistrationRecord(user_id=values["user_id"], organization_id=organization_id)
        except IntegrityError as exc:
            await self._session.rollback()
            self._raise_conflict(exc)
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise RegistrationRepositoryError from exc

    async def _prepare_transaction(self) -> None:
        if self._session.in_transaction():
            await self._session.rollback()

    @staticmethod
    def _raise_conflict(exc: IntegrityError) -> None:
        constraint = str(getattr(exc.orig, "constraint_name", "") or "")
        detail = str(getattr(exc.orig, "detail", "") or "").lower()
        if "username" in constraint or "username" in detail:
            raise RegistrationConflictError("username") from exc
        if "business_registration" in constraint or "business_registration" in detail:
            raise RegistrationConflictError("business_registration_no") from exc
        raise RegistrationRepositoryError from exc
