"""
Lightweight API-key auth with role checks.
Designed to be optional in demo/development and enforced in production via settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from .settings import get_settings


ROLE_ORDER = {
    "viewer": 1,
    "analyst": 2,
    "admin": 3,
}


@dataclass(frozen=True)
class AuthContext:
    role: str
    token: str


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key.strip()

    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()

    return None


def _resolve_context(request: Request) -> AuthContext:
    settings = get_settings()
    token = _extract_token(request)
    token_to_role = {value: key for key, value in settings.api_tokens.items()}

    if not settings.require_auth and not token:
        # Keep demo/dev ergonomic while still attaching a role for downstream auditing.
        return AuthContext(role="admin", token="implicit-demo")

    if not token or token not in token_to_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token",
        )

    return AuthContext(role=token_to_role[token], token=token)


def require_role(min_role: str = "viewer"):
    min_level = ROLE_ORDER[min_role]

    def dependency(request: Request) -> AuthContext:
        ctx = _resolve_context(request)
        if ROLE_ORDER.get(ctx.role, 0) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{min_role} role or higher is required",
            )
        return ctx

    return dependency


ViewerAccess = Depends(require_role("viewer"))
AnalystAccess = Depends(require_role("analyst"))
AdminAccess = Depends(require_role("admin"))
