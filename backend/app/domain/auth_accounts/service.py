from dataclasses import dataclass
from uuid import UUID

from fastapi import status

from app.core.errors import AppError
from app.integrations.auth import (
    AuthAccountError,
    AuthAccountProvider,
    AuthSession,
)
from app.repositories.auth_accounts import (
    RegistrationConflictError,
    RegistrationRepository,
    RegistrationRepositoryError,
)
from app.schemas.auth import (
    AuthSessionResponse,
    BuyerSignupRequest,
    DemoLoginRequest,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetEmailResponse,
    SellerSignupRequest,
    SignupRequest,
    SignupResponse,
)


@dataclass(frozen=True, slots=True)
class DemoLoginConfig:
    enabled: bool = False
    buyer_email: str | None = None
    buyer_password: str | None = None
    seller_email: str | None = None
    seller_password: str | None = None

    def credentials(self, role: str) -> tuple[str, str] | None:
        pair = (
            (self.buyer_email, self.buyer_password)
            if role == "buyer"
            else (self.seller_email, self.seller_password)
        )
        if not pair[0] or not pair[1]:
            return None
        return pair[0], pair[1]


class AuthAccountService:
    def __init__(
        self,
        repository: RegistrationRepository | None,
        provider: AuthAccountProvider,
        demo_config: DemoLoginConfig | None = None,
        password_reset_redirect_url: str | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._demo_config = demo_config or DemoLoginConfig()
        self._password_reset_redirect_url = password_reset_redirect_url

    async def signup(self, payload: SignupRequest) -> SignupResponse:
        if self._repository is None:  # pragma: no cover - dependency wiring invariant
            raise AssertionError("Signup requires a registration repository")
        try:
            auth_user = await self._provider.signup(str(payload.email), payload.password)
        except AuthAccountError as exc:
            self._provider_error(exc, operation="signup")

        username = payload.username or f"user_{auth_user.user_id.hex[:12]}"
        common = {
            "user_id": auth_user.user_id,
            "username": username,
            "display_name": payload.display_name,
            "phone": payload.phone,
        }
        try:
            if isinstance(payload, BuyerSignupRequest):
                registration = await self._repository.create_buyer(
                    {
                        **common,
                        "country_code": payload.country_code,
                        "locale": payload.locale.value,
                        "preferred_currency": payload.preferred_currency,
                        "default_group_name": payload.default_group_name,
                        "affiliation_name": payload.affiliation_name,
                        "business_type": payload.business_type,
                    }
                )
            elif isinstance(payload, SellerSignupRequest):
                registration = await self._repository.create_seller(
                    {
                        **common,
                        "organization_name": payload.organization_name,
                        "legal_name": payload.legal_name,
                        "representative_name": payload.representative_name,
                        "business_registration_no": payload.business_registration_no,
                        "business_address": payload.business_address,
                        "supply_categories": [item.value for item in payload.supply_categories],
                        "job_title": payload.job_title,
                    }
                )
            else:  # pragma: no cover - protected by the discriminated request schema
                raise AssertionError("Unsupported signup role")
        except RegistrationConflictError as exc:
            await self._compensate(auth_user.user_id)
            code = (
                "USERNAME_CONFLICT" if exc.field == "username" else "BUSINESS_REGISTRATION_CONFLICT"
            )
            message = (
                "The username is already in use."
                if exc.field == "username"
                else "The business registration number is already in use."
            )
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code=code,
                message=message,
            ) from exc
        except RegistrationRepositoryError as exc:
            await self._compensate(auth_user.user_id)
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DATABASE_UNAVAILABLE",
                message="Database connection is unavailable.",
            ) from exc

        return SignupResponse(
            user_id=auth_user.user_id,
            email=auth_user.email,
            role=payload.role,
            organization_id=registration.organization_id,
            organization_verification_status=(
                "pending" if registration.organization_id is not None else None
            ),
            email_confirmation_required=auth_user.session is None,
            session=self._session(auth_user.session),
        )

    async def login(self, payload: LoginRequest) -> LoginResponse:
        return await self._login(str(payload.email), payload.password)

    async def demo_login(self, payload: DemoLoginRequest) -> LoginResponse:
        if not self._demo_config.enabled:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DEMO_LOGIN_DISABLED",
                message="Demo login is disabled.",
            )
        credentials = self._demo_config.credentials(payload.role)
        if credentials is None:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="DEMO_ACCOUNT_NOT_CONFIGURED",
                message="The requested demo account is not configured.",
            )
        return await self._login(*credentials)

    async def _login(self, email: str, password: str) -> LoginResponse:
        try:
            result = await self._provider.login(email, password)
        except AuthAccountError as exc:
            self._provider_error(exc, operation="login")
        return LoginResponse(
            user_id=result.user_id,
            email=result.email,
            session=self._required_session(result.session),
        )

    async def logout(self, access_token: str) -> None:
        try:
            await self._provider.logout(access_token)
        except AuthAccountError as exc:
            self._provider_error(exc, operation="authenticated")

    async def change_password(
        self, access_token: str, payload: PasswordChangeRequest
    ) -> PasswordChangeResponse:
        try:
            await self._provider.change_password(access_token, payload.new_password)
        except AuthAccountError as exc:
            self._provider_error(exc, operation="authenticated")
        return PasswordChangeResponse()

    async def send_password_reset_email(self, email: str | None) -> PasswordResetEmailResponse:
        if not email:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="EMAIL_UNAVAILABLE",
                message="The authenticated account has no email address.",
            )
        try:
            await self._provider.send_password_reset_email(
                email,
                self._password_reset_redirect_url,
            )
        except AuthAccountError as exc:
            self._provider_error(exc, operation="password_reset")
        return PasswordResetEmailResponse()

    async def _compensate(self, user_id: UUID) -> None:
        try:
            await self._provider.delete_user(user_id)
        except AuthAccountError as exc:
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="SIGNUP_ROLLBACK_FAILED",
                message="Signup could not be completed or safely rolled back.",
            ) from exc

    @staticmethod
    def _session(session: AuthSession | None) -> AuthSessionResponse | None:
        if session is None:
            return None
        return AuthSessionResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_type=session.token_type,
            expires_in=session.expires_in,
            expires_at=session.expires_at,
        )

    @classmethod
    def _required_session(cls, session: AuthSession) -> AuthSessionResponse:
        response = cls._session(session)
        if response is None:  # pragma: no cover - guarded by the provider contract
            raise AssertionError("Login provider returned no session")
        return response

    @staticmethod
    def _provider_error(exc: AuthAccountError, *, operation: str) -> None:
        if exc.reason == "email_conflict":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="EMAIL_CONFLICT",
                message="The email is already registered.",
            ) from exc
        if exc.reason == "invalid_credentials":
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_CREDENTIALS",
                message="The email or password is incorrect.",
            ) from exc
        if exc.reason == "token_invalid":
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="TOKEN_INVALID",
                message="The access token is invalid or expired.",
            ) from exc
        if exc.reason == "weak_password":
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="WEAK_PASSWORD",
                message="The password does not satisfy the authentication policy.",
            ) from exc
        if exc.reason == "rate_limited":
            raise AppError(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="AUTH_RATE_LIMITED",
                message="Too many authentication requests were made.",
            ) from exc
        if exc.reason == "provider_unavailable":
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="AUTH_PROVIDER_UNAVAILABLE",
                message="Authentication provider is unavailable.",
            ) from exc
        code = "INVALID_CREDENTIALS" if operation == "login" else "AUTH_REQUEST_REJECTED"
        status_code = (
            status.HTTP_401_UNAUTHORIZED
            if operation in {"login", "authenticated"}
            else status.HTTP_400_BAD_REQUEST
        )
        raise AppError(
            status_code=status_code,
            code=code,
            message="The authentication request was rejected.",
        ) from exc
