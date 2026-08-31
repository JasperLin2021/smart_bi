from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
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
        if database_url.startswith("sqlite"):
            if ":memory:" in database_url:
                # 内存库必须保持连接复用（每个连接独立内存库），沿用默认池
                _datasource_engines[database_url] = create_engine(database_url, pool_pre_ping=True)
            else:
                # 文件型 SQLite 单文件连接建立开销极低，用 NullPool 即用即关，
                # 避免连接池长期持有句柄导致 Windows 下临时库文件无法释放。
                _datasource_engines[database_url] = create_engine(
                    database_url, pool_pre_ping=True, poolclass=NullPool
                )
        else:
            _datasource_engines[database_url] = create_engine(
                database_url, pool_pre_ping=True, pool_size=5, max_overflow=10
            )
    return _datasource_engines[database_url]
