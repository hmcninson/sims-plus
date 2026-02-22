"""
SIMS Plus - Database Session Management

Async SQLAlchemy engine and session configuration.

SECURITY:
- Connection pool checkout listener resets tenant context to prevent leaking.
- The application MUST connect as sims_app_user (non-superuser) so RLS is enforced.
- expire_on_commit=False for performance; manual expire_all() after context switch.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Create async engine
# The DATABASE_URL MUST point to sims_app_user (non-superuser) for RLS enforcement.
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE if not settings.DEBUG else 5,
    max_overflow=settings.DATABASE_MAX_OVERFLOW if not settings.DEBUG else 10,
)


# CRITICAL: Reset tenant context when connection is checked out from pool.
# This prevents stale context from a previous request leaking to a new request.
# The listener fires on the sync_engine because asyncpg uses sync connections
# under the hood via greenlet.
@event.listens_for(engine.sync_engine, "checkout")
def _reset_tenant_context_on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Clear tenant context when a connection is checked out from the pool.

    Without this, a connection returned to the pool after handling Tenant A's
    request could be checked out for Tenant B's request with Tenant A's context
    still set. The middleware would set Tenant B's context, but there is a window
    between checkout and middleware execution where the old context is active.

    By clearing on checkout, the worst case is zero rows (NULL context = no match),
    never wrong-tenant rows.

    NOTE: We use `false` (session-scoped) here intentionally, NOT `true`
    (transaction-scoped). This listener fires at the raw DBAPI level outside
    of any SQLAlchemy-managed transaction. With `true`, the clear would be
    scoped to the implicit auto-commit transaction of this single statement
    and would be reverted immediately, defeating the purpose.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SELECT set_config('app.current_tenant_id', '', false)")
    cursor.close()


# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncSession:
    """Get a new async database session.

    Returns:
        AsyncSession instance
    """
    async with async_session_maker() as session:
        return session
