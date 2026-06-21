from uagents import Agent, Context

from app.agents.models import IncidentMessage, InvestigationResult
from app.agents.addresses import (
    GITHUB_AGENT_ADDRESS,
    INVESTIGATION_AGENT_ENDPOINT,
    INVESTIGATION_SEED,
    LOCAL_AGENT_RESOLVER,
)
from app.agents.workflow_trace import trace_step

investigation_agent = Agent(
    name="investigation_agent",
    seed=INVESTIGATION_SEED,
    port=8002,
    endpoint=[INVESTIGATION_AGENT_ENDPOINT],
    resolve=LOCAL_AGENT_RESOLVER,
)


@investigation_agent.on_message(model=IncidentMessage)
async def investigate(ctx: Context, sender: str, msg: IncidentMessage):
    ctx.logger.info(f"Investigating Sentry issue: {msg.sentry_issue_id}")
    trace_step(
        "investigation",
        msg.incident_id,
        "started investigation",
        sentry_issue_id=msg.sentry_issue_id,
        title=msg.title,
        level=msg.level,
        status_code=msg.status_code,
        route=msg.route,
        event_type=msg.event_type,
    )

    if not msg.full_error:
        ctx.logger.warning(
            f"[investigation] incident {msg.incident_id} has no full_error context"
        )
        trace_step(
            "investigation",
            msg.incident_id,
            "missing detailed Sentry error context",
        )

    if not msg.recent_incidents:
        ctx.logger.warning(
            f"[investigation] incident {msg.incident_id} has no recent incident context"
        )
        trace_step(
            "investigation",
            msg.incident_id,
            "no recent incident history available",
        )

    actionable, reason = _is_actionable(msg)
    severity = _severity_for(msg)
    files_to_inspect = _guess_files(msg)

    result = InvestigationResult(
        incident_id=msg.incident_id,
        sentry_issue_id=msg.sentry_issue_id,
        repo_full_name=msg.repo_full_name,
        default_branch=msg.default_branch,
        is_actionable=actionable,
        confidence=0.78 if actionable else 0.35,
        severity=severity,
        reason=reason,
        suspected_root_cause=_root_cause_for(msg),
        files_to_inspect=files_to_inspect,
        recommendation=_recommendation_for(msg, files_to_inspect),
        recent_incidents=msg.recent_incidents,
    )

    if not result.is_actionable:
        ctx.logger.warning(
            f"[investigation] stopping chain for incident {msg.incident_id}: {result.reason}"
        )
        trace_step(
            "investigation",
            msg.incident_id,
            "decision: stop pipeline",
            reason=result.reason,
            confidence=result.confidence,
            severity=result.severity,
        )
        return

    if not result.files_to_inspect:
        ctx.logger.warning(
            f"[investigation] no likely files guessed for incident {msg.incident_id}"
        )
        trace_step(
            "investigation",
            msg.incident_id,
            "no likely files guessed; continuing with repository defaults",
            reason=result.reason,
            severity=result.severity,
        )

    trace_step(
        "investigation",
        msg.incident_id,
        "decision: continue pipeline",
        reason=result.reason,
        confidence=result.confidence,
        severity=result.severity,
        files_to_inspect=result.files_to_inspect,
        suspected_root_cause=result.suspected_root_cause,
    )
    ctx.logger.info(
        f"Forwarding actionable investigation to GitHub agent for incident {msg.incident_id}"
    )
    status = await ctx.send(GITHUB_AGENT_ADDRESS, result)
    ctx.logger.info(f"GitHub agent delivery status: {status.status} - {status.detail}")
    trace_step(
        "investigation",
        msg.incident_id,
        "GitHub Agent handoff completed",
        delivery=status.status,
        detail=status.detail,
    )
    if status.status.value != "delivered":
        ctx.logger.warning(
            f"[investigation] GitHub handoff looked unhealthy for incident {msg.incident_id}"
        )
        trace_step(
            "investigation",
            msg.incident_id,
            "GitHub Agent handoff looked unhealthy",
            delivery=status.status,
            detail=status.detail,
        )


def _is_actionable(msg: IncidentMessage) -> tuple[bool, str]:
    text = _incident_text(msg)
    recent_same_title = sum(
        1 for incident in msg.recent_incidents if incident.title.lower() == msg.title.lower()
    )

    if msg.status_code is not None and msg.status_code >= 500:
        return True, f"Sentry captured a server-side HTTP {msg.status_code}."

    if _is_expected_client_noise(msg, text):
        return False, "Likely expected client or scanner noise."

    if msg.level in {"error", "fatal"}:
        return True, "Sentry marked the event as error/fatal."

    if any(token in text for token in ["500", "exception", "traceback", "crash", "failed"]):
        return True, "The event text suggests a runtime failure."

    if recent_same_title >= 2:
        return True, "This issue is recurring in recent Sentry context."

    return True, "Defaulting to actionable because the alert rule fired."


def _severity_for(msg: IncidentMessage) -> str:
    text = _incident_text(msg)

    if (
        msg.level == "fatal"
        or (msg.status_code is not None and msg.status_code >= 500)
        or "critical" in text
    ):
        return "high"

    if msg.level == "error" or "exception" in text:
        return "medium"

    return "low"


def _guess_files(msg: IncidentMessage) -> list[str]:
    text = _incident_text(msg)
    files: list[str] = []

    if (
        "indexerror" in text
        or "string index out of range" in text
        or "list index out of range" in text
        or "todo" in text
        or "create_todo" in text
    ):
        files.append("backend/app/main.py")
    if _is_missing_user_attribute_error(text):
        files.append("backend/app/main.py")
    if "sentry" in text or "webhook" in text:
        files.append("backend/app/routes/sentry.py")
    if "login" in text or "auth" in text or "401" in text:
        files.extend(["backend/app/main.py", "backend/app/routes/github.py"])
    if "agent" in text or "workflow" in text:
        files.extend(
            [
                "backend/app/agents/investigation_agent.py",
                "backend/app/agents/github_agent.py",
                "backend/app/agents/patch_agent.py",
            ]
        )

    return files[:5]


def _incident_text(msg: IncidentMessage) -> str:
    return " ".join(
        str(part)
        for part in [
            msg.title,
            msg.full_error,
            msg.http_method,
            msg.route,
            msg.status_code,
            msg.event_type,
        ]
        if part is not None
    ).lower()


def _is_expected_client_noise(msg: IncidentMessage, text: str) -> bool:
    if msg.event_type == "bogus_backend_request":
        return True

    if msg.status_code not in {401, 404}:
        return False

    noise_tokens = [
        "bogus",
        "scanner",
        "bot",
        "unauthorized",
        "not found",
        "unknown route",
        "does-not-exist",
    ]

    return any(token in text for token in noise_tokens)


def _root_cause_for(msg: IncidentMessage) -> str:
    text = _incident_text(msg)

    if "indexerror" in text or "string index out of range" in text:
        return (
            "IndexError suggests the failing route indexes into a string, list, "
            "or split result before validating that the value exists."
        )

    if _is_missing_user_attribute_error(text):
        return (
            "AttributeError suggests an auth/user lookup returned None before code "
            "accessed current_user.id or a similar user id field."
        )

    if msg.culprit:
        return f"Possible failure near {msg.culprit}."

    if msg.full_error:
        return f"Failure inferred from Sentry details: {msg.full_error[:300]}"

    return f"Failure inferred from alert title: {msg.title}"


def _recommendation_for(msg: IncidentMessage, files_to_inspect: list[str]) -> str:
    file_hint = ", ".join(files_to_inspect) if files_to_inspect else "the failing route"
    text = _incident_text(msg)

    if "indexerror" in text or "string index out of range" in text:
        return (
            f"Inspect {file_hint} for direct indexing into strings, lists, or split results. "
            "Recommend the smallest guard that returns a controlled 400 for malformed input "
            "instead of allowing a 500-level IndexError."
        )

    if _is_missing_user_attribute_error(text):
        return (
            f"Inspect {file_hint} for auth/session code that reads current_user.id or user.id "
            "before proving the user exists. Recommend a small authentication guard that returns "
            "401 when the user lookup fails instead of allowing a NoneType AttributeError."
        )

    return (
        f"Inspect {file_hint}, reproduce the Sentry event, and recommend the smallest "
        "defensive code change. Return code guidance only, not a PR."
    )


def _is_missing_user_attribute_error(text: str) -> bool:
    return (
        "attributeerror" in text
        and "nonetype" in text
        and ("attribute 'id'" in text or 'attribute "id"' in text or ".id" in text)
    )


if __name__ == "__main__":
    print("Investigation address:", investigation_agent.address)
    investigation_agent.run()
