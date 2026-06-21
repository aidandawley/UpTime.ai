import httpx
from app.config import settings


async def request_patch_from_agent(
    repo_full_name: str,
    sentry_issue_id: str,
    default_branch: str = "main",
):
    url = f"{settings.fetch_ai_agent_url}/patch-from-sentry"

    payload = {
        "repo_full_name": repo_full_name,
        "sentry_issue_id": sentry_issue_id,
        "default_branch": default_branch,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
