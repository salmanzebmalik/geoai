from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings

# Important: import models so SQLModel metadata knows about tables
from app.db import models  # noqa: F401


engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session