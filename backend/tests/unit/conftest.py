"""
Conftest for unit tests that do NOT require database connectivity.

Overrides the session-scoped autouse fixtures from the parent conftest
so they become no-ops, preventing connection errors when PostgreSQL is
not available.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
async def _fix_schema_mismatches():
    """No-op override: unit tests do not need the database."""
    yield
