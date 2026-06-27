from sqlmodel import SQLModel, Session, create_engine
from app.config import settings
import app.infrastructure.db.models  # noqa: F401 — register SQLModel metadata

engine = create_engine(settings.database_url, echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
