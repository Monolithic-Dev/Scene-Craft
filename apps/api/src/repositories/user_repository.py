from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.user import User


class UserRepository:
    """Data-access layer for User. Services depend on this, never on the ORM directly."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        return self._db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def get_by_id(self, user_id: str) -> User | None:
        return self._db.get(User, user_id)

    def create(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
