from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — so dev.db and .env resolve here no matter where you run commands from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    google_maps_api_key: str = ""
    # OAuth client id for "Sign in with Google" (same value as the frontend's VITE_GOOGLE_CLIENT_ID).
    # Empty = Google sign-in is turned off.
    google_client_id: str = ""
    # Local default: a SQLite file, nothing to install.
    # CI/deploy: set DATABASE_URL=postgresql+psycopg://user:pass@host/db
    database_url: str = f"sqlite:///{BACKEND_DIR / 'dev.db'}"

    # Signs login tokens. The default is for local dev only;
    # deployments MUST set JWT_SECRET or anyone reading the repo can forge tokens.
    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env")


settings = Settings()
