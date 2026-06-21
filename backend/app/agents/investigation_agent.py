from uagents import Agent, Context

from app.agents.models import IncidentMessage, InvestigationResult
from app.agents.addresses import (
    GITHUB_AGENT_ADDRESS,
    INVESTIGATION_SEED,
)

investigation_agent = Agent(
    name="investigation_agent",
    seed=INVESTIGATION_SEED,
    port=8002,
    endpoint=["http://127.0.0.1:8002/submit"],
)


@investigation_agent.on_message(model=IncidentMessage)
async def investigate(ctx: Context, sender: str, msg: IncidentMessage):
    ctx.logger.info(f"Investigating Sentry issue: {msg.sentry_issue_id}")

    result = InvestigationResult(
        incident_id=msg.incident_id,
        sentry_issue_id=msg.sentry_issue_id,
        repo_full_name=msg.repo_full_name,
        severity="high" if "500" in msg.title.lower() else "medium",
        suspected_root_cause=f"Possible failure near {msg.culprit or 'unknown module'}",
        files_to_inspect=[],
        recommendation="Inspect stack trace, identify failing function, and create minimal safe patch.",
    )

    ctx.logger.info(
        f"Forwarding investigation result to patch agent for incident {msg.incident_id}"
    )

    await ctx.send(GITHUB_AGENT_ADDRESS, result)


if __name__ == "__main__":
    print("Investigation address:", investigation_agent.address)
    investigation_agent.run()