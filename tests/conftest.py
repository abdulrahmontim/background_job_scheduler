import pytest_asyncio
from app.database import engine, Base

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """
    Creates all database tables in the test environment
    before the test session starts.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Optional: Drop tables after tests finish
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)