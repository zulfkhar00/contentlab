from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings

_pool_kwargs: dict = (
    {"poolclass": NullPool}
    if settings.environment == "test"
    else {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
)
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    **_pool_kwargs,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
