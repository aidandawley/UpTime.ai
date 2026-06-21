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

    if _needs_fallback(raw_plan):
        ctx.logger.warning(
            f"[patch] incident {msg.incident_id}: model output was malformed; using guarded fallback"
        )
        trace_step(
            "patch",
            msg.incident_id,
            "LLM patch plan malformed; using guarded fallback",
            preview=raw_plan[:160],
        )
        raw_plan = _best_fallback_raw_plan(msg)

    result = PatchResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        recommendation_title=_section(raw_plan, "RECOMMENDATION TITLE"),
        changed_files=_changed_files_for(msg),
        patch_summary=_section(raw_plan, "PATCH SUMMARY"),
        justification=_section(raw_plan, "JUSTIFICATION"),
        code_recommendation=_section(raw_plan, "CODE RECOMMENDATION"),
        code_patch=_section(raw_plan, "CODE PATCH"),
        risk=_section(raw_plan, "RISK"),
        workflow_notes=_workflow_notes_for(msg, raw_plan),
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
        return ""

    start += len(marker)
    headings = [
        "PATCH SUMMARY:",
        "RECOMMENDATION TITLE:",
        "JUSTIFICATION:",
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


def _needs_fallback(text: str) -> bool:
    cleaned = text.strip()

    if not cleaned:
        return True

    bad_tokens = ["</think>", "<tool_call", "analyze_IMAGE", "<|", "```tool"]
    if any(token.lower() in cleaned.lower() for token in bad_tokens):
        return True

    required_headings = [
        "RECOMMENDATION TITLE:",
        "PATCH SUMMARY:",
        "JUSTIFICATION:",
        "CODE PATCH:",
        "TESTS TO RUN:",
    ]
    return any(heading not in cleaned for heading in required_headings)


def _tests_from(text: str) -> list[str]:
    tests_text = _section(text, "TESTS TO RUN")
    tests = [
        line.strip("- ").strip()
        for line in tests_text.splitlines()
        if line.strip().strip("- ")
    ]
    return tests or ["Run the smallest test that reproduces the Sentry event."]


def _best_fallback_raw_plan(msg: PatchRequest) -> str:
    if _is_index_error(msg):
        return _index_error_raw_plan(msg)

    return _fallback_raw_plan(msg)


def _is_index_error(msg: PatchRequest) -> bool:
    text = " ".join(
        [
            msg.suspected_root_cause,
            msg.recommendation,
            " ".join(incident.title for incident in msg.recent_incidents),
        ]
    ).lower()
    return "indexerror" in text or "string index out of range" in text or "list index out of range" in text


def _index_error_raw_plan(msg: PatchRequest) -> str:
    file_hint = _best_code_file(msg)
    route_hint = _route_hint(msg)

    return f"""RECOMMENDATION TITLE:
Add bounds validation around the failing todo input path

PATCH SUMMARY:
The Sentry event is an IndexError, which usually means the route assumes a string, list, or split result has at least one element. Add an explicit length check before indexing and return a controlled 400-level error for malformed todo input.

JUSTIFICATION:
The issue points near {route_hint}. A defensive guard prevents malformed user input from becoming a 500 while keeping the valid todo creation path unchanged. This is safer than catching every exception because it fixes the likely precondition directly.

CODE RECOMMENDATION:
Inspect {file_hint} for direct indexing or split indexing in the todo creation flow, such as value[0], parts[1], token[0], or text.split(...)[1]. Validate the value before indexing and keep the existing success behavior for valid requests.

CODE PATCH:
--- {file_hint}
+++ {file_hint}
@@
-    # Existing code indexes into a string/list without proving it has data.
-    selected_value = incoming_value[0]
+    if not incoming_value:
+        raise HTTPException(
+            status_code=400,
+            detail="Todo input is malformed or missing the expected value.",
+        )
+    selected_value = incoming_value[0]

RISK:
Low to medium. The recommendation is intentionally narrow, but the exact variable name should be matched to the failing line in {file_hint}.

TESTS TO RUN:
- Send the same malformed todo request that triggered Sentry and confirm it returns 400 instead of 500
- Send a valid todo creation request and confirm the todo is still created
- Run the backend route tests covering {file_hint}
"""


def _best_code_file(msg: PatchRequest) -> str:
    candidate_paths = [
        *msg.files_to_inspect,
        *(file.path for file in msg.repository_context.files),
    ]

    for path in candidate_paths:
        if path.endswith(".py") and "README" not in path:
            return path

    return "backend/app/main.py"


def _route_hint(msg: PatchRequest) -> str:
    text = f"{msg.suspected_root_cause} {msg.recommendation}"

    for route in ["/todos/create_todo", "/todos", "/create_todo"]:
        if route in text:
            return route

    return "the failing FastAPI route"


def _workflow_notes_for(msg: PatchRequest, raw_plan: str) -> str:
    loaded_files = [file.path for file in msg.repository_context.files]
    notes = [
        f"Investigation: classified incident {msg.incident_id} as actionable with severity {msg.severity}.",
        f"GitHub: loaded {len(loaded_files)} file(s): {', '.join(loaded_files) if loaded_files else 'none'}.",
    ]

    if _is_index_error(msg):
        notes.append("Patch: applied IndexError heuristic and looked for unsafe string/list indexing.")
    elif _needs_fallback(raw_plan):
        notes.append("Patch: model output was malformed, so a guarded fallback recommendation was used.")
    else:
        notes.append("Patch: used the structured model recommendation.")

    notes.append("Validation: checked title, justification, patch text, changed files, and tests before storing.")
    return "\n".join(f"- {note}" for note in notes)


def _fallback_raw_plan(msg: PatchRequest) -> str:
    file_hint = _changed_files_for(msg)[0]
    return f"""RECOMMENDATION TITLE:
Review defensive handling in {file_hint}

PATCH SUMMARY:
Recommend a minimal defensive change around the suspected failure.

JUSTIFICATION:
The incident points to a backend failure path. A small defensive change should prevent repeat alerts while keeping behavior easy to verify.

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

    if not result.recommendation_title.strip():
        warnings.append("no recommendation title was produced")

    if not result.justification.strip():
        warnings.append("no justification was produced")

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
