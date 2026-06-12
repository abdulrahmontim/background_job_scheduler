from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import get_settings

settings = get_settings()

connect_args = {}
pool_args = {}

if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}
else:
    pool_args = {
        "pool_size": 10,
        "max_overflow": 20
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    **pool_args,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
