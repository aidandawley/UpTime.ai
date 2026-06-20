from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.services.patch_agent_service import request_patch_from_agent

router = APIRouter(prefix="/api/patch-agent", tags=["patch-agent"])


@router.post("/sentry/{issue_id}")
async def patch_sentry_issue(
    issue_id: str,
    repo_full_name: str,
    session: Session = Depends(get_session),
):
    result = await request_patch_from_agent(
        repo_full_name=repo_full_name,
        sentry_issue_id=issue_id,
    )

    return result