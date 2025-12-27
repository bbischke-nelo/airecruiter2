"""Database configuration for processor."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from processor.config import settings

# Build connection URL with MARS enabled
# MARS (Multiple Active Result Sets) allows multiple queries on the same connection
database_url = settings.DATABASE_URL
if "MARS_Connection" not in database_url:
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}MARS_Connection=Yes"

# Create engine with SQL Server specific settings
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session as context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
