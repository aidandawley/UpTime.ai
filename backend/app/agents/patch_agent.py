from uagents import Agent, Context

from app.agents.models import PatchRequest, PatchResult
from app.agents.addresses import (
    LOCAL_AGENT_RESOLVER,
    PATCH_AGENT_ENDPOINT,
    PATCH_SEED,
    VALIDATION_AGENT_ADDRESS,
)
from app.agents.workflow_trace import trace_step
from app.services.llm_service import generate_patch_plan

patch_agent = Agent(
    name="patch_agent",
    seed=PATCH_SEED,
    port=8003,
    endpoint=[PATCH_AGENT_ENDPOINT],
    resolve=LOCAL_AGENT_RESOLVER,
)


@patch_agent.on_message(model=PatchRequest)
async def create_patch(ctx: Context, sender: str, msg: PatchRequest):
    ctx.logger.info(f"Creating code recommendation for incident {msg.incident_id}")
    trace_step(
        "patch",
        msg.incident_id,
        "started code recommendation",
        severity=msg.severity,
        suspected_root_cause=msg.suspected_root_cause,
        repository_files=[file.path for file in msg.repository_context.files],
        files_to_inspect=msg.files_to_inspect,
    )

    try:
        raw_plan = generate_patch_plan(
            root_cause=msg.suspected_root_cause,
            recommendation=msg.recommendation,
            repository_context=msg.repository_context,
            recent_incidents=msg.recent_incidents,
        )
        trace_step(
            "patch",
            msg.incident_id,
            "LLM patch plan generated",
            characters=len(raw_plan),
        )
    except Exception as exc:
        ctx.logger.warning(f"Patch plan generation failed, using fallback: {exc}")
        trace_step(
            "patch",
            msg.incident_id,
            "LLM patch plan failed; using fallback recommendation",
            error=str(exc),
        )
        raw_plan = _fallback_raw_plan(msg)

    result = PatchResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        changed_files=_changed_files_for(msg),
        patch_summary=_section(raw_plan, "PATCH SUMMARY"),
        code_recommendation=_section(raw_plan, "CODE RECOMMENDATION"),
        code_patch=_section(raw_plan, "CODE PATCH"),
        risk=_section(raw_plan, "RISK"),
        tests_to_run=_tests_from(raw_plan),
    )

    warnings = _warnings_for_result(result)
    for warning in warnings:
        ctx.logger.warning(f"[patch] incident {msg.incident_id}: {warning}")
        trace_step(
            "patch",
            msg.incident_id,
            "patch recommendation warning",
            warning=warning,
        )

    trace_step(
        "patch",
        msg.incident_id,
        "code recommendation ready",
        changed_files=result.changed_files,
        risk=result.risk,
        tests_to_run=result.tests_to_run,
    )
    ctx.logger.info(
        f"Forwarding code recommendation to Validation agent for incident {msg.incident_id}"
    )
    trace_step(
        "patch",
        msg.incident_id,
        "forwarding code recommendation to Validation Agent",
    )
    status = await ctx.send(VALIDATION_AGENT_ADDRESS, result)
    ctx.logger.info(f"Validation agent delivery status: {status.status} - {status.detail}")
    trace_step(
        "patch",
        msg.incident_id,
        "Validation Agent handoff completed",
        delivery=status.status,
        detail=status.detail,
    )
    if status.status.value != "delivered":
        ctx.logger.warning(
            f"[patch] Validation handoff looked unhealthy for incident {msg.incident_id}"
        )
        trace_step(
            "patch",
            msg.incident_id,
            "Validation Agent handoff looked unhealthy",
            delivery=status.status,
            detail=status.detail,
        )


def _changed_files_for(msg: PatchRequest) -> list[str]:
    if msg.files_to_inspect:
        return msg.files_to_inspect

    if msg.repository_context.files:
        return [file.path for file in msg.repository_context.files[:3]]

    return ["UNKNOWN_FILE"]


def _section(text: str, heading: str) -> str:
    marker = f"{heading}:"
    start = text.find(marker)

    if start == -1:
        return text.strip()

    start += len(marker)
    headings = [
        "PATCH SUMMARY:",
        "CODE RECOMMENDATION:",
        "CODE PATCH:",
        "RISK:",
        "TESTS TO RUN:",
    ]
    following = [
        text.find(candidate, start)
        for candidate in headings
        if candidate != marker and text.find(candidate, start) != -1
    ]
    end = min(following) if following else len(text)
    return text[start:end].strip()


def _tests_from(text: str) -> list[str]:
    tests_text = _section(text, "TESTS TO RUN")
    tests = [
        line.strip("- ").strip()
        for line in tests_text.splitlines()
        if line.strip().strip("- ")
    ]
    return tests or ["Run the smallest test that reproduces the Sentry event."]


def _fallback_raw_plan(msg: PatchRequest) -> str:
    file_hint = _changed_files_for(msg)[0]
    return f"""PATCH SUMMARY:
Recommend a minimal defensive change around the suspected failure.

CODE RECOMMENDATION:
{msg.recommendation}

CODE PATCH:
--- {file_hint}
+++ {file_hint}
@@
- existing failing behavior
+ add validation or fallback handling for: {msg.suspected_root_cause}

RISK:
Medium. Repository context may be incomplete.

TESTS TO RUN:
- Reproduce the Sentry event locally
- Run tests covering {file_hint}
"""


def _warnings_for_result(result: PatchResult) -> list[str]:
    warnings: list[str] = []

    if not result.code_patch.strip():
        warnings.append("no code patch text was produced")

    if result.changed_files == ["UNKNOWN_FILE"]:
        warnings.append("changed file target is unknown")

    if "existing failing behavior" in result.code_patch:
        warnings.append("code patch is still placeholder-level")

    if not result.tests_to_run:
        warnings.append("no tests were suggested")

    return warnings


if __name__ == "__main__":
    print("Patch address:", patch_agent.address)
    patch_agent.run()
