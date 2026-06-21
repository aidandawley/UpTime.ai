from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    redis_url: str = "redis://localhost:6379"

    fetch_ai_agent_url: str = "http://localhost:8001"

    sentry_auth_token: str | None = None
    sentry_org_slug: str | None = None
    sentry_project_slug: str | None = None
    sentry_dsn: str | None = None
    sentry_webhook_secret: str | None = None

    investigation_agent_address: str | None = None
    
    default_repo_full_name: str | None = None
    default_branch: str = "main"

    github_token: str | None = None

    asi_one_api_key: str | None = None
    asi_one_base_url: str = "https://api.asi1.ai/v1"
    asi_one_model: str = "asi1"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()