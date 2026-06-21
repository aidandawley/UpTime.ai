from uagents import Agent, Context

from app.agents.models import PatchRequest, PatchResult
from app.agents.addresses import PATCH_SEED, VALIDATION_AGENT_ADDRESS
from app.services.llm_service import generate_patch_plan

patch_agent = Agent(
    name="patch_agent",
    seed=PATCH_SEED,
    port=8003,
    endpoint="http://127.0.0.1:8003/submit",
)


@patch_agent.on_message(model=PatchRequest)
async def create_patch(ctx: Context, sender: str, msg: PatchRequest):
    ctx.logger.info(f"Creating patch plan for incident {msg.incident_id}")

    patch_summary = generate_patch_plan(
        root_cause=msg.suspected_root_cause,
        recommendation=msg.recommendation,
    )

    result = PatchResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        branch_name=f"fix/sentry-{msg.incident_id}",
        commit_message=f"Fix Sentry incident {msg.incident_id}",
        changed_files=msg.files_to_inspect or ["UNKNOWN_FILE"],
        patch_summary=patch_summary,
    )

    ctx.logger.info(
        f"Forwarding patch result to Validation agent for incident {msg.incident_id}"
    )

    await ctx.send(VALIDATION_AGENT_ADDRESS, result)


if __name__ == "__main__":
    print("Patch address:", patch_agent.address)
    patch_agent.run()