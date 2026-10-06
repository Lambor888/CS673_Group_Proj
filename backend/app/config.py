from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — so dev.db and .env resolve here no matter where you run commands from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Local default: a SQLite file, nothing to install.
    # CI/deploy: set DATABASE_URL=postgresql+psycopg://user:pass@host/db
    database_url: str = f"sqlite:///{BACKEND_DIR / 'dev.db'}"

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env")


settings = Settings()
