import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.schema import CreateTable, DropTable
from app.database import engine, Base

@pytest_asyncio.fixture
async def setup_database():
    """
    Creates all database tables before each test and drops them after.
    Uses pure async DDL to avoid run_sync/greenlet conflicts with asyncpg.
    """
    async with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            compiled = CreateTable(table, if_not_exists=True).compile(engine.sync_engine)
            await conn.execute(text(str(compiled)))
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            compiled = DropTable(table, if_exists=True).compile(engine.sync_engine)
            await conn.execute(text(str(compiled)))