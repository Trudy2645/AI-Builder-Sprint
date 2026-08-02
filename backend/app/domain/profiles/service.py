from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import AuthenticatedUser
from app.repositories.profiles import (
    DuplicateUsernameError,
    OrganizationMembershipRecord,
    OrganizationRecord,
    ProfileRecord,
    ProfileRepository,
    RepositoryUnavailableError,
)
from app.schemas.profiles import (
    MeResponse,
    OrganizationPatch,
    OrganizationResponse,
    OrganizationSummary,
    ProfilePatch,
)


class ProfileService:
    def __init__(self, repository: ProfileRepository) -> None:
        self._repository = repository

    async def get_me(self, actor: AuthenticatedUser) -> MeResponse:
        try:
            profile = await self._repository.get_profile(actor.id)
            if profile is None:
                self._profile_not_found()
            memberships = await self._repository.list_memberships(actor.id)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return self._me_response(actor, profile, memberships)

    async def update_me(self, actor: AuthenticatedUser, patch: ProfilePatch) -> MeResponse:
        changes = patch.model_dump(exclude_unset=True)
        try:
            profile = await self._repository.update_profile(actor.id, changes)
            if profile is None:
                self._profile_not_found()
            memberships = await self._repository.list_memberships(actor.id)
        except DuplicateUsernameError as exc:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="USERNAME_CONFLICT",
                message="The username is already in use.",
            ) from exc
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        return self._me_response(actor, profile, memberships)

    async def get_organization(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        header_organization_id: str | None,
    ) -> OrganizationResponse:
        membership = await self._authorize_organization(
            actor, organization_id, header_organization_id, require_manager=False
        )
        try:
            organization = await self._repository.get_organization(organization_id)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if organization is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ORGANIZATION_NOT_FOUND",
                message="Organization was not found.",
            )
        return self._organization_response(organization, membership)

    async def update_organization(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        header_organization_id: str | None,
        patch: OrganizationPatch,
    ) -> OrganizationResponse:
        membership = await self._authorize_organization(
            actor, organization_id, header_organization_id, require_manager=True
        )
        try:
            organization = await self._repository.update_organization(
                organization_id, patch.model_dump(exclude_unset=True)
            )
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if organization is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ORGANIZATION_NOT_FOUND",
                message="Organization was not found.",
            )
        return self._organization_response(organization, membership)

    async def _authorize_organization(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        header_organization_id: str | None,
        *,
        require_manager: bool,
    ) -> OrganizationMembershipRecord:
        if header_organization_id is None:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ORGANIZATION_HEADER_REQUIRED",
                message="X-Organization-Id is required for seller organization APIs.",
            )
        try:
            parsed_header = UUID(header_organization_id)
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="X-Organization-Id must be a UUID.",
                details={"header": "X-Organization-Id"},
            ) from exc
        if parsed_header != organization_id:
            self._organization_access_denied()
        try:
            membership = await self._repository.get_membership(actor.id, organization_id)
        except RepositoryUnavailableError as exc:
            self._database_unavailable(exc)
        if membership is None or membership.organization_type != "seller":
            self._organization_access_denied()
        if require_manager and membership.role not in {"owner", "admin"}:
            self._organization_access_denied()
        return membership

    @staticmethod
    def _me_response(
        actor: AuthenticatedUser,
        profile: ProfileRecord,
        memberships: list[OrganizationMembershipRecord],
    ) -> MeResponse:
        seller_organizations = []
        if profile.active_business_role == "seller":
            seller_organizations = [
                OrganizationSummary(
                    id=membership.organization_id,
                    name=membership.organization_name,
                    verification_status=membership.verification_status,
                    member_role=membership.role,
                )
                for membership in memberships
                if membership.organization_type == "seller"
            ]
        return MeResponse(
            id=profile.id,
            email=actor.email,
            username=profile.username,
            display_name=profile.display_name,
            phone=profile.phone,
            country_code=profile.country_code,
            locale=profile.locale,
            preferred_currency=profile.preferred_currency,
            default_group_name=profile.default_group_name,
            affiliation_name=profile.affiliation_name,
            business_type=profile.business_type,
            role=profile.active_business_role,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            organizations=seller_organizations,
        )

    @staticmethod
    def _organization_response(
        organization: OrganizationRecord,
        membership: OrganizationMembershipRecord,
    ) -> OrganizationResponse:
        return OrganizationResponse(
            id=organization.id,
            organization_type=organization.organization_type,
            name=organization.name,
            legal_name=organization.legal_name,
            business_registration_no=organization.business_registration_no,
            representative_name=organization.representative_name,
            business_address=organization.business_address,
            supply_categories=organization.supply_categories or [],
            verification_status=organization.verification_status,
            rating_average=organization.rating_average,
            rating_count=organization.rating_count,
            member_role=membership.role,
            created_at=organization.created_at,
            updated_at=organization.updated_at,
            verified_at=organization.verified_at,
        )

    @staticmethod
    def _profile_not_found() -> None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROFILE_NOT_FOUND",
            message="Profile was not found.",
        )

    @staticmethod
    def _organization_access_denied() -> None:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ORG_ACCESS_DENIED",
            message="You do not have access to this organization.",
        )

    @staticmethod
    def _database_unavailable(exc: Exception) -> None:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            message="Database connection is unavailable.",
        ) from exc
