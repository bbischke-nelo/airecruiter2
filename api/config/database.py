"""Database configuration for SQL Server using SQLAlchemy."""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from .settings import settings

# Build connection URL with MARS enabled
# MARS (Multiple Active Result Sets) allows multiple queries on the same connection
database_url = settings.DATABASE_URL
if "MARS_Connection" not in database_url:
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}MARS_Connection=Yes"

# Create engine for SQL Server
# Note: We use sync engine since aioodbc is not well-maintained
# FastAPI can handle sync database operations via thread pool
engine = create_engine(
    database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    # Import all models to register them with Base
    from api import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
