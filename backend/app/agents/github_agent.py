from uagents import Agent, Context

from app.agents.models import InvestigationResult, PatchRequest
from app.agents.addresses import (
    GITHUB_AGENT_ENDPOINT,
    GITHUB_SEED,
    LOCAL_AGENT_RESOLVER,
    PATCH_AGENT_ADDRESS,
)
from app.services.github_service import load_repository_context

github_agent = Agent(
    name="github_agent",
    seed=GITHUB_SEED,
    port=8004,
    endpoint=[GITHUB_AGENT_ENDPOINT],
    resolve=LOCAL_AGENT_RESOLVER,
)


@github_agent.on_message(model=InvestigationResult)
async def fetch_repo_context(ctx: Context, sender: str, msg: InvestigationResult):
    ctx.logger.info(
        f"Fetching GitHub context for incident {msg.incident_id}: "
        f"{msg.repo_full_name}@{msg.default_branch}"
    )

    if not msg.is_actionable:
        ctx.logger.info(f"Skipping GitHub context for non-actionable incident {msg.incident_id}")
        return

    repository_context = load_repository_context(
        repo_full_name=msg.repo_full_name,
        default_branch=msg.default_branch,
        files_to_inspect=msg.files_to_inspect,
    )
    ctx.logger.info(repository_context.summary)

    if not repository_context.files:
        ctx.logger.warning(
            f"[github] no repository files loaded for incident {msg.incident_id}; "
            "patch agent will use limited context"
        )

    patch_request = PatchRequest(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        default_branch=msg.default_branch,
        severity=msg.severity,
        suspected_root_cause=msg.suspected_root_cause,
        recommendation=msg.recommendation,
        files_to_inspect=msg.files_to_inspect,
        repository_context=repository_context,
        recent_incidents=msg.recent_incidents,
    )

    ctx.logger.info(f"Forwarding repository context to Patch agent for incident {msg.incident_id}")
    status = await ctx.send(PATCH_AGENT_ADDRESS, patch_request)
    ctx.logger.info(f"Patch agent delivery status: {status.status} - {status.detail}")
    if status.status.value != "delivered":
        ctx.logger.warning(
            f"[github] Patch handoff looked unhealthy for incident {msg.incident_id}"
        )


if __name__ == "__main__":
    print("GitHub address:", github_agent.address)
    github_agent.run()
