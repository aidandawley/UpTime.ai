from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    redis_url: str = "redis://localhost:6379"

    fetch_ai_agent_url: str = "http://localhost:8001"

    sentry_auth_token: str | None = None
    sentry_org_slug: str | None = None
    sentry_project_slug: str | None = None
    sentry_dsn: str | None = None

    github_token: str | None = None

    openai_api_key: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
