from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_auth_account_service, get_auth_session_service
from app.core.auth import get_access_token, get_current_user
from app.domain.auth_accounts.service import AuthAccountService
from app.integrations.auth import AuthenticatedUser
from app.schemas.auth import (
    DemoLoginRequest,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetEmailResponse,
    SignupRequest,
    SignupResponse,
)
from app.schemas.common import SuccessEnvelope, typed_envelope

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=SuccessEnvelope[SignupResponse],
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    request: Request,
    payload: SignupRequest,
    service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> SuccessEnvelope[SignupResponse]:
    return typed_envelope(request, await service.signup(payload))


@router.post("/login", response_model=SuccessEnvelope[LoginResponse])
async def login(
    request: Request,
    payload: LoginRequest,
    service: Annotated[AuthAccountService, Depends(get_auth_session_service)],
) -> SuccessEnvelope[LoginResponse]:
    return typed_envelope(request, await service.login(payload))


@router.post("/demo-login", response_model=SuccessEnvelope[LoginResponse])
async def demo_login(
    request: Request,
    payload: DemoLoginRequest,
    service: Annotated[AuthAccountService, Depends(get_auth_session_service)],
) -> SuccessEnvelope[LoginResponse]:
    return typed_envelope(request, await service.demo_login(payload))


@router.post("/logout", response_model=SuccessEnvelope[LogoutResponse])
async def logout(
    request: Request,
    access_token: Annotated[str, Depends(get_access_token)],
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AuthAccountService, Depends(get_auth_session_service)],
) -> SuccessEnvelope[LogoutResponse]:
    del actor
    await service.logout(access_token)
    return typed_envelope(request, LogoutResponse())


@router.patch("/password", response_model=SuccessEnvelope[PasswordChangeResponse])
async def change_password(
    request: Request,
    payload: PasswordChangeRequest,
    access_token: Annotated[str, Depends(get_access_token)],
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AuthAccountService, Depends(get_auth_session_service)],
) -> SuccessEnvelope[PasswordChangeResponse]:
    del actor
    return typed_envelope(request, await service.change_password(access_token, payload))


@router.post(
    "/password/reset-email",
    response_model=SuccessEnvelope[PasswordResetEmailResponse],
)
async def send_password_reset_email(
    request: Request,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[AuthAccountService, Depends(get_auth_session_service)],
) -> SuccessEnvelope[PasswordResetEmailResponse]:
    return typed_envelope(request, await service.send_password_reset_email(actor.email))
