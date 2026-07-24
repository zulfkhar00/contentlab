import asyncio
import sys
import os
import pytest

# Add backend/ to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def event_loop():
    """
    Session-scoped event loop.
    Required for SQLAlchemy async + asyncpg integration tests so that
    all fixtures and tests share one loop — avoids "Future attached to
    a different loop" errors when connection pool objects cross loop boundaries.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
