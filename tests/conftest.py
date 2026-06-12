import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# 1. CRITICAL: Force SQLite memory database BEFORE any app modules are imported.
# This prevents the app from ever seeing your PostgreSQL URL during tests.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# 2. Now it is safe to import from your app
from app.database import engine, Base

# 3. Create a dedicated session factory bound strictly to the test engine
TestSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    """
    Creates all database tables before each test and drops them after.
    Using run_sync is the standard way to handle DDL with SQLAlchemy async SQLite.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session():
    """Provides a fresh, clean database session for each test to use."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
        await session.close()