from fastapi import FastAPI
from app.routes import health, sentry, incidents, patch_agent

app = FastAPI(
    title="AI On-Call Engineer Backend",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(sentry.router)
app.include_router(incidents.router)
app.include_router(patch_agent.router)