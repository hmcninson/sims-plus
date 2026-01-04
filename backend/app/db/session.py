"""
SIMS Plus - Database Session Management

Async SQLAlchemy engine and session configuration.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# Create async engine
# Use NullPool in development for easier debugging
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE if not settings.DEBUG else 5,
    max_overflow=settings.DATABASE_MAX_OVERFLOW if not settings.DEBUG else 10,
    # Use NullPool for testing to avoid connection issues
    # poolclass=NullPool if settings.ENVIRONMENT == "testing" else None,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """
    Get a new async database session.

    Returns:
        AsyncSession instance
    """
    async with async_session_maker() as session:
        return session
