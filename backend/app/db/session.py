from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# App database engine (stores users, datasources, settings, etc.)
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cache of datasource engines keyed by database_url
_datasource_engines: dict = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_datasource_engine(database_url: str):
    """Get or create a SQLAlchemy engine for a business datasource."""
    if database_url not in _datasource_engines:
        _datasource_engines[database_url] = create_engine(
            database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
        )
    return _datasource_engines[database_url]
