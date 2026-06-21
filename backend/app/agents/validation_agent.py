from uagents import Agent, Context

from app.agents.models import PatchResult, ValidationResult
from app.agents.addresses import (
    LOCAL_AGENT_RESOLVER,
    VALIDATION_AGENT_ENDPOINT,
    VALIDATION_SEED,
)

validation_agent = Agent(
    name="validation_agent",
    seed=VALIDATION_SEED,
    port=8005,
    endpoint=[VALIDATION_AGENT_ENDPOINT],
    resolve=LOCAL_AGENT_RESOLVER,
)


@validation_agent.on_message(model=PatchResult)
async def validate_patch(ctx: Context, sender: str, msg: PatchResult):
    ctx.logger.info(f"Validating patch recommendation for incident {msg.incident_id}")

    warnings = _warnings_for(msg)
    for warning in warnings:
        ctx.logger.warning(f"[validation] incident {msg.incident_id}: {warning}")

    result = ValidationResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        looks_safe=not warnings,
        validation_summary=(
            "Patch recommendation has code guidance, changed-file targets, and test suggestions."
            if not warnings
            else "Patch recommendation needs review before use."
        ),
        warnings=warnings,
    )

    ctx.logger.info(result.model_dump_json())


def _warnings_for(msg: PatchResult) -> list[str]:
    warnings: list[str] = []

    if not msg.changed_files or msg.changed_files == ["UNKNOWN_FILE"]:
        warnings.append("No concrete changed files were identified.")

    if not msg.code_patch.strip():
        warnings.append("No code patch text was generated.")

    if "existing failing behavior" in msg.code_patch:
        warnings.append("Patch text is still a placeholder and needs developer refinement.")

    if not msg.tests_to_run:
        warnings.append("No test suggestions were generated.")

    return warnings


if __name__ == "__main__":
    print("Validation address:", validation_agent.address)
    validation_agent.run()
