from sqlalchemy.orm import Session
from app.models.user_model import User
from app.schemas.user_schema import UserCreate


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    db_user = User(telegram_username=user_in.telegram_username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
