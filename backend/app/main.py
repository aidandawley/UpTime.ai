from fastapi import FastAPI

from app.database import init_db
from app.routes import health, patch_agent, sentry, incidents
import sentry_sdk

sentry_sdk.init(
    dsn="https://84344397706aa48848849c54322a0709@o4511599396192256.ingest.us.sentry.io/4511599678586880",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)

app = FastAPI(
    title="AI On-Call Engineer Backend",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0

app.include_router(health.router)
app.include_router(sentry.router)
app.include_router(patch_agent.router)
app.include_router(incidents.router)