from dataclasses import replace
from typing import Any
from uuid import UUID

from app.repositories.profiles import (
    DuplicateUsernameError,
    OrganizationMembershipRecord,
    OrganizationRecord,
    ProfileRecord,
    RepositoryUnavailableError,
)


class FakeProfileRepository:
    def __init__(
        self,
        *,
        profiles: list[ProfileRecord],
        organizations: list[OrganizationRecord],
        memberships: dict[tuple[UUID, UUID], OrganizationMembershipRecord],
    ) -> None:
        self.profiles = {profile.id: profile for profile in profiles}
        self.organizations = {organization.id: organization for organization in organizations}
        self.memberships = memberships
        self.unavailable = False

    def _check_available(self) -> None:
        if self.unavailable:
            raise RepositoryUnavailableError

    async def get_profile(self, user_id: UUID) -> ProfileRecord | None:
        self._check_available()
        return self.profiles.get(user_id)

    async def update_profile(self, user_id: UUID, changes: dict[str, Any]) -> ProfileRecord | None:
        self._check_available()
        profile = self.profiles.get(user_id)
        if profile is None:
            return None
        if "username" in changes and any(
            other.id != user_id and other.username.lower() == changes["username"].lower()
            for other in self.profiles.values()
        ):
            raise DuplicateUsernameError
        updated = replace(profile, **changes)
        self.profiles[user_id] = updated
        return updated

    async def list_memberships(self, user_id: UUID) -> list[OrganizationMembershipRecord]:
        self._check_available()
        return [
            membership
            for (member_user_id, _), membership in self.memberships.items()
            if member_user_id == user_id
        ]

    async def get_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationMembershipRecord | None:
        self._check_available()
        return self.memberships.get((user_id, organization_id))

    async def get_organization(self, organization_id: UUID) -> OrganizationRecord | None:
        self._check_available()
        return self.organizations.get(organization_id)

    async def update_organization(
        self, organization_id: UUID, changes: dict[str, Any]
    ) -> OrganizationRecord | None:
        self._check_available()
        organization = self.organizations.get(organization_id)
        if organization is None:
            return None
        updated = replace(organization, **changes)
        self.organizations[organization_id] = updated
        return updated
