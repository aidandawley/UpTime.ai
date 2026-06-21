from uagents import Agent, Context

from app.agents.models import InvestigationResult, PatchRequest
from app.agents.addresses import GITHUB_SEED, PATCH_AGENT_ADDRESS

github_agent = Agent(
    name="github_agent",
    seed=GITHUB_SEED,
    port=8004,
    endpoint="http://127.0.0.1:8004/submit",
)


@github_agent.on_message(model=InvestigationResult)
async def fetch_repo_context(ctx: Context, sender: str, msg: InvestigationResult):
    ctx.logger.info(f"Fetching GitHub context for incident {msg.incident_id}")

    patch_request = PatchRequest(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        default_branch="main",
        suspected_root_cause=msg.suspected_root_cause,
        recommendation=msg.recommendation,
        files_to_inspect=msg.files_to_inspect,
    )

    ctx.logger.info(f"Forwarding patch request to Patch agent for incident {msg.incident_id}")

    await ctx.send(PATCH_AGENT_ADDRESS, patch_request)


if __name__ == "__main__":
    print("GitHub address:", github_agent.address)
    github_agent.run()