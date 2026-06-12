from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/scheduler_db"
    WORKER_POLL_INTERVAL: float = 3.0
    EMAIL_FAILURE_RATE: float = 0.0
    MAX_RETRIES: int = 3
    CONCURRENCY_LIMIT: float = 10
    STARVATION_THRESHOLD_SECONDS: int = 120
    STARVATION_CHECK_INTERVAL_SECONDS: int = 30
    DLQ_ALERT_THRESHOLD: int = 10
    ALERT_EMAIL: str = "admin@dilamme.com"
    
    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings():
    return Settings()
