"""
Shared FastAPI dependencies (Phase 5).

`get_db` already lived in app.db.session (Phase 1) and is re-exported here so routers have
one place to import both DB and auth deps from, matching the plan's `api/deps.py` layout.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.config import settings
from app.db.models import User
from app.db.session import get_db  # re-exported for router convenience

__all__ = ["get_db", "get_current_user", "require_role"]

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=False,  # we handle the "no token" case ourselves, gated by AUTH_ENABLED
)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Resolves the requesting user from a bearer token.

    When settings.AUTH_ENABLED is False (MVP default), this is a no-op that returns None so
    every route is reachable unauthenticated - this keeps the Phase 1-4 endpoints and test
    suites working without a login step. Once AUTH_ENABLED=True, a missing/invalid/expired
    token raises 401.
    """
    if not settings.AUTH_ENABLED:
        return None

    if token is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


def require_role(*allowed_roles: str):
    """
    Dependency factory for future RBAC (Section: Phase 5 task 4). With a single role in
    play today this only matters once AUTH_ENABLED=True; it's here so mutating routers
    (e.g. /contracts writes) can declare their intent now (`Depends(require_role("logistics_manager"))`)
    without a rewrite when analyst/manager/admin roles are added.
    """

    def _check(user: Optional[User] = Depends(get_current_user)) -> Optional[User]:
        if not settings.AUTH_ENABLED:
            return None
        if user is None or user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return _check
