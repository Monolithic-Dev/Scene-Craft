from sqlalchemy.orm import Session

from src.core.exceptions import ConflictError, UnauthorizedError
from src.core.security import create_access_token, hash_password, verify_password
from src.models.user import User
from src.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def signup(self, email: str, password: str) -> User:
        if self._users.get_by_email(email) is not None:
            raise ConflictError(f"An account with email '{email}' already exists")
        return self._users.create(email=email, password_hash=hash_password(password))

    def authenticate(self, email: str, password: str) -> User:
        user = self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=user.id)
