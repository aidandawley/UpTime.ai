from uagents import Agent, Context
from sqlmodel import Session, select

from app.agents.models import PatchResult, ValidationResult
from app.agents.addresses import (
    LOCAL_AGENT_RESOLVER,
    VALIDATION_AGENT_ENDPOINT,
    VALIDATION_SEED,
)
from app.agents.workflow_trace import trace_step
from app.database import engine, init_db
from app.models.recommendation import Recommendation

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
    trace_step(
        "validation",
        msg.incident_id,
        "started validation",
        changed_files=msg.changed_files,
        tests_to_run=msg.tests_to_run,
    )

    warnings = _warnings_for(msg)
    for warning in warnings:
        ctx.logger.warning(f"[validation] incident {msg.incident_id}: {warning}")
        trace_step(
            "validation",
            msg.incident_id,
            "validation warning",
            warning=warning,
        )

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
    trace_step(
        "validation",
        msg.incident_id,
        "validation finished",
        looks_safe=result.looks_safe,
        summary=result.validation_summary,
        warnings=result.warnings,
    )
    recommendation = _store_recommendation(msg, result)

    if recommendation is None:
        trace_step(
            "validation",
            msg.incident_id,
            "recommendation not stored for frontend",
            reason="missing title, justification, or code patch",
        )
        return

    trace_step(
        "validation",
        msg.incident_id,
        "stored recommendation for frontend",
        recommendation_id=recommendation.id,
        validation_status=recommendation.validation_status,
        title=recommendation.title,
    )


def _warnings_for(msg: PatchResult) -> list[str]:
    warnings: list[str] = []

    if not msg.recommendation_title.strip():
        warnings.append("No recommendation title was generated.")

    if not msg.justification.strip():
        warnings.append("No recommendation justification was generated.")

    if not msg.changed_files or msg.changed_files == ["UNKNOWN_FILE"]:
        warnings.append("No concrete changed files were identified.")

    if not msg.code_patch.strip():
        warnings.append("No code patch text was generated.")

    if "existing failing behavior" in msg.code_patch or "existing failing path" in msg.code_patch:
        warnings.append("Patch text is still a placeholder and needs developer refinement.")

    malformed_fields = _malformed_fields(msg)
    if malformed_fields:
        warnings.append(
            "Recommendation contains malformed model artifacts in: "
            + ", ".join(malformed_fields)
        )

    if not _looks_like_patch(msg.code_patch):
        warnings.append("Code patch does not look like a concrete diff-style recommendation.")

    if not msg.tests_to_run:
        warnings.append("No test suggestions were generated.")

    return warnings


def _store_recommendation(msg: PatchResult, result: ValidationResult) -> Recommendation | None:
    if not _has_minimum_ui_fields(msg):
        return None

    init_db()

    with Session(engine) as session:
        recommendation = session.exec(
            select(Recommendation)
            .where(Recommendation.incident_id == msg.incident_id)
            .order_by(Recommendation.id.desc())
        ).first()

        if recommendation is None:
            recommendation = Recommendation(
                incident_id=msg.incident_id,
                repo_full_name=msg.repo_full_name,
                title=msg.recommendation_title.strip(),
                summary=_summary_for(msg),
                justification=msg.justification.strip(),
                code_patch=msg.code_patch.strip(),
                changed_files="\n".join(msg.changed_files),
                tests_to_run="\n".join(msg.tests_to_run),
                risk=msg.risk.strip(),
                workflow_notes=msg.workflow_notes.strip(),
                validation_status="approved" if result.looks_safe else "needs_review",
                validation_summary=result.validation_summary,
                warnings="\n".join(result.warnings),
            )
        else:
            recommendation.repo_full_name = msg.repo_full_name
            recommendation.title = msg.recommendation_title.strip()
            recommendation.summary = _summary_for(msg)
            recommendation.justification = msg.justification.strip()
            recommendation.code_patch = msg.code_patch.strip()
            recommendation.changed_files = "\n".join(msg.changed_files)
            recommendation.tests_to_run = "\n".join(msg.tests_to_run)
            recommendation.risk = msg.risk.strip()
            recommendation.workflow_notes = msg.workflow_notes.strip()
            recommendation.validation_status = "approved" if result.looks_safe else "needs_review"
            recommendation.validation_summary = result.validation_summary
            recommendation.warnings = "\n".join(result.warnings)

        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)

    return recommendation


def _has_minimum_ui_fields(msg: PatchResult) -> bool:
    return all(
        [
            msg.recommendation_title.strip(),
            msg.justification.strip(),
            msg.code_patch.strip(),
        ]
    ) and not _malformed_fields(msg)


def _malformed_fields(msg: PatchResult) -> list[str]:
    fields = {
        "title": msg.recommendation_title,
        "summary": msg.patch_summary,
        "justification": msg.justification,
        "code_patch": msg.code_patch,
        "risk": msg.risk,
        "tests": "\n".join(msg.tests_to_run),
    }
    bad_tokens = ["</think>", "<tool_call", "analyze_IMAGE", "<|", "```tool"]
    malformed = []

    for name, value in fields.items():
        lowered = value.lower()
        if any(token.lower() in lowered for token in bad_tokens):
            malformed.append(name)

    return malformed


def _looks_like_patch(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines()]
    return any(line.startswith("--- ") for line in lines) and any(
        line.startswith("+++ ") for line in lines
    )


def _summary_for(msg: PatchResult) -> str:
    return _first_meaningful_line(msg.code_recommendation) or msg.patch_summary


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().strip("-").strip()
        if cleaned:
            return cleaned

    return ""


if __name__ == "__main__":
    print("Validation address:", validation_agent.address)
    validation_agent.run()
