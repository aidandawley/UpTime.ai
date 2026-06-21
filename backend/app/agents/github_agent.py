from uagents import Agent, Context

from app.agents.models import PatchResult, PullRequestResult
from app.agents.addresses import GITHUB_SEED, PATCH_AGENT_ADDRESS
from app.services.github_service import create_demo_pr

github_agent = Agent(
    name="github_agent",
    seed=GITHUB_SEED,
    port=8004,
    endpoint=["http://127.0.0.1:8004/submit"],
)


@github_agent.on_message(model=PatchResult)
async def create_pr(ctx: Context, sender: str, msg: PatchResult):
    ctx.logger.info(f"Creating GitHub PR for incident {msg.incident_id}")

    pr_url = create_demo_pr(
        repo_full_name=msg.repo_full_name,
        branch_name=msg.branch_name,
        commit_message=msg.commit_message,
        patch_summary=msg.patch_summary,
    )

    result = PullRequestResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        pr_url=pr_url,
        branch_name=msg.branch_name,
        changed_files=msg.changed_files,
    )

    ctx.logger.info(f"Forwarding PR result to validation agent: {pr_url}")

    await ctx.send(PATCH_AGENT_ADDRESS, result)


if __name__ == "__main__":
    print("GitHub address:", github_agent.address)
    github_agent.run()