from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.exceptions import UnauthorizedError
from src.core.security import TokenError, decode_access_token
from src.models.user import User
from src.repositories.user_repository import UserRepository

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]
    try:
        user_id = decode_access_token(token)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User for this token no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
