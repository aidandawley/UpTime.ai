from fastapi import APIRouter
from app.services.patch_agent_service import request_patch_from_agent

router = APIRouter(prefix="/api/patch-agent", tags=["patch-agent"])


@router.post("/sentry/{issue_id}")
async def patch_sentry_issue(
    issue_id: str,
    repo_full_name: str,
):
    result = await request_patch_from_agent(
        repo_full_name=repo_full_name,
        sentry_issue_id=issue_id,
    )

    return result
