"""Database connection and initialization."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATA_DIR, PROJECT_ROOT, get_settings
from database.orm_models import Base

settings = get_settings()


def get_database_url() -> str:
    """Get database URL from settings."""
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        rel_path = db_url.replace("sqlite:///", "")
        db_path = Path(rel_path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    return db_url


def create_db_engine():
    """Create SQLAlchemy engine."""
    db_url = get_database_url()
    engine = create_engine(db_url, echo=settings.debug)
    return engine


def init_db():
    """Initialize database tables."""
    engine = create_db_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """Get database session."""
    engine = create_db_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


__all__ = ["init_db", "get_session", "get_database_url", "create_db_engine"]
