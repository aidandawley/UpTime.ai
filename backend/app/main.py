from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routes import health, patch_agent, sentry, incidents, github
import sentry_sdk

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI On-Call Engineer Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(sentry.router)
app.include_router(patch_agent.router)
app.include_router(incidents.router)
app.include_router(github.router)
