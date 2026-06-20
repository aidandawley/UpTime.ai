import os

from uagents import Agent, Context, Model


class PatchRequest(Model):
    repo_full_name: str
    sentry_issue_id: str
    issue_title: str
    issue_url: str | None = None


class PatchResponse(Model):
    status: str
    severity: str
    recommendation: str
    should_create_pr: bool


agent = Agent(
    name="patch_engineer_agent",
    seed=os.getenv("FETCH_AI_AGENT_SEED", "replace_me_with_real_seed"),
    port=8001,
    endpoint=["http://localhost:8001/submit"],
)


@agent.on_rest_post("/analyze-incident", PatchRequest, PatchResponse)
async def analyze_incident(ctx: Context, req: PatchRequest) -> PatchResponse:
    title = req.issue_title.lower()

    if "cannot read properties" in title or "undefined" in title or "null" in title:
        return PatchResponse(
            status="recommendation_created",
            severity="high",
            recommendation="Likely null or undefined access. Add a null guard, loading state, or optional chaining near the failing component.",
            should_create_pr=True,
        )

    if "timeout" in title or "latency" in title:
        return PatchResponse(
            status="recommendation_created",
            severity="medium",
            recommendation="Likely slow API route or database query. Inspect recent backend changes and add timeout/error handling.",
            should_create_pr=False,
        )

    return PatchResponse(
        status="recommendation_created",
        severity="low",
        recommendation="Investigate the Sentry stack trace and recent commits related to this issue.",
        should_create_pr=False,
    )


if __name__ == "__main__":
    agent.run()