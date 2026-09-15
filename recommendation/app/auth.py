"""
Phase 5 auth: minimal OAuth2 (password flow) + JWT, single "logistics_manager" role for MVP.

Kept intentionally simple per the implementation plan (Section: Phase 5, task 4):
"auth is minimal (single role) for MVP but structured so RBAC (multiple roles: analyst,
manager, admin) can be added without a rewrite (role field already reserved in the user
model)." `User.role` is a free-text column, not an enum, so adding roles later is a data
change, not a migration.

Auth is gated behind `settings.AUTH_ENABLED` (default False) so the existing Phase 1-4
endpoints and test/smoke suites keep working unauthenticated in local/dev/CI. Flip it on
(and set a real SECRET_KEY) once a client ships a login flow.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jose.JWTError on an invalid/expired token - callers translate that to a 401."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def ensure_default_user(db: Session) -> None:
    """
    Seeds a single default 'logistics_manager' account on startup so the MVP has someone
    to log in as out of the box. Purely a dev/demo convenience - real deployments should
    rotate this password (or disable AUTH_ENABLED entirely and front the API with a
    proper IdP) before going anywhere near production traffic.
    """
    if db.query(User).count() > 0:
        return
    default_user = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
        role="logistics_manager",
        is_active=True,
    )
    db.add(default_user)
    db.commit()
