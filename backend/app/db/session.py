"""
SIMS Plus - Database Session Management

Async SQLAlchemy engine and session configuration.

SECURITY:
- Connection pool checkout listener resets tenant context to prevent leaking.
- The application MUST connect as sims_app_user (non-superuser) so RLS is enforced.
- expire_on_commit=False for performance; manual expire_all() after context switch.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

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


# ---------------------------------------------------------------------------
# Superuser engine for platform admin cross-tenant queries.
# Uses sims_admin role which bypasses RLS (policies target sims_app_user only).
# This engine is ONLY used by PlatformService — never exposed as a FastAPI
# dependency. Small pool to limit blast radius: 2 base + 3 overflow = 5 max.
# ---------------------------------------------------------------------------

_platform_admin_engine: AsyncEngine | None = None
_platform_admin_session_maker: async_sessionmaker | None = None


def get_platform_admin_session_maker() -> async_sessionmaker:
    """
    Get the superuser session factory for cross-tenant queries.

    Lazily creates the engine on first call. Uses ALEMBIC_DATABASE_URL
    (sims_admin credentials) which bypasses RLS.

    WARNING: This must ONLY be used from PlatformService methods.
    Never expose this as a FastAPI dependency or pass to route handlers.
    """
    global _platform_admin_engine, _platform_admin_session_maker

    if _platform_admin_session_maker is None:
        admin_url = settings.ALEMBIC_DATABASE_URL
        if not admin_url:
            raise RuntimeError(
                "ALEMBIC_DATABASE_URL is required for platform admin operations. "
                "Set it in .env or environment variables."
            )

        # RISK FIX (R3): ALEMBIC_DATABASE_URL may use sync driver prefix
        # (postgresql://) but create_async_engine requires postgresql+asyncpg://.
        admin_url_str = str(admin_url)
        if admin_url_str.startswith("postgresql://"):
            admin_url_str = admin_url_str.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        _platform_admin_engine = create_async_engine(
            admin_url_str,
            echo=False,  # Never echo superuser queries
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
        )
        _platform_admin_session_maker = async_sessionmaker(
            _platform_admin_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _platform_admin_session_maker
