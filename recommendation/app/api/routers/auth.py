from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import authenticate_user, create_access_token
from app.db.models import User
from app.deps import get_current_user, get_db
from app.schemas.auth import Token, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """
    OAuth2 password flow. Exchanges username/password for a bearer JWT.
    Default seeded MVP account: username `logistics_manager` (see settings.DEFAULT_ADMIN_USERNAME).
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username, role=user.role)
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=Optional[UserResponse])
def read_current_user(user: Optional[User] = Depends(get_current_user)) -> Optional[UserResponse]:
    """
    Returns the authenticated user. When AUTH_ENABLED=False (MVP default) this returns null
    rather than erroring, since there's no session to describe.
    """
    return user
