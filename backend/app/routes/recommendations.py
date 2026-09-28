from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.agents.models import PullRequestRequest
from app.agents.workflow_trace import trace_step
from app.models.incident import Incident
from app.models.recommendation import Recommendation
from app.services.github_service import UnsafePatchError, create_pull_request

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/")
def list_recommendations(session: Session = Depends(get_session)):
    recommendations = session.exec(
        select(Recommendation).order_by(Recommendation.id.desc())
    ).all()
    return [
        recommendation
        for recommendation in recommendations
        if not _contains_malformed_model_artifacts(recommendation)
    ]


@router.delete("/{recommendation_id}")
def delete_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
):
    recommendation = session.get(Recommendation, recommendation_id)

    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    session.delete(recommendation)
    session.commit()

    return {"deleted": True, "recommendation_id": recommendation_id}


@router.post("/{recommendation_id}/pull-request")
def open_pull_request(
    recommendation_id: int,
    session: Session = Depends(get_session),
):
    recommendation = session.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    trace_step(
        "pr creation requested",
        recommendation.incident_id,
        "developer requested pull request creation",
        recommendation_id=recommendation.id,
    )
    if recommendation.validation_status != "approved":
        return _skip_pr(
            session,
            recommendation,
            "Only approved recommendations can create pull requests.",
        )

    incident = session.get(Incident, recommendation.incident_id)
    request = PullRequestRequest(
        incident_id=recommendation.incident_id,
        sentry_issue_id=incident.sentry_issue_id if incident else None,
        repo_full_name=recommendation.repo_full_name,
        recommendation_title=recommendation.title,
        justification=recommendation.justification,
        code_patch=recommendation.code_patch,
        changed_files=_lines(recommendation.changed_files),
        risk=recommendation.risk,
        tests_to_run=_lines(recommendation.tests_to_run),
    )
    recommendation.pr_creation_status = "creating"
    recommendation.pr_creation_error = None
    session.add(recommendation)
    session.commit()

    def record_step(step: str, detail: str) -> None:
        trace_step(step, recommendation.incident_id, step, detail=detail)

    try:
        result = create_pull_request(request, on_step=record_step)
    except UnsafePatchError as exc:
        return _skip_pr(session, recommendation, str(exc))
    except Exception as exc:
        recommendation.pr_creation_status = "failed"
        recommendation.pr_creation_error = str(exc)
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)
        trace_step(
            "pr creation failed",
            recommendation.incident_id,
            "pull request creation failed",
            error=str(exc),
        )
        return recommendation

    recommendation.pr_creation_status = result.status
    recommendation.pr_creation_error = result.error
    recommendation.pr_branch = result.branch_name
    recommendation.pr_url = result.pr_url
    recommendation.pr_number = result.pr_number
    session.add(recommendation)
    session.commit()
    session.refresh(recommendation)
    if result.status == "skipped":
        trace_step(
            "pr skipped",
            recommendation.incident_id,
            "pull request creation skipped",
            reason=result.error,
        )
    elif result.status == "existing":
        trace_step(
            "pr skipped",
            recommendation.incident_id,
            "existing pull request reused",
            pr_url=result.pr_url,
        )
    return recommendation


def _skip_pr(
    session: Session, recommendation: Recommendation, reason: str
) -> Recommendation:
    recommendation.pr_creation_status = "skipped"
    recommendation.pr_creation_error = reason
    session.add(recommendation)
    session.commit()
    session.refresh(recommendation)
    trace_step(
        "pr skipped",
        recommendation.incident_id,
        "pull request creation skipped",
        reason=reason,
    )
    return recommendation


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _contains_malformed_model_artifacts(recommendation: Recommendation) -> bool:
    text = " ".join(
        [
            recommendation.title,
            recommendation.summary,
            recommendation.justification,
            recommendation.code_patch,
            recommendation.risk,
            recommendation.tests_to_run,
        ]
    ).lower()
    bad_tokens = ["</think>", "<tool_call", "analyze_image", "<|", "```tool"]
    return any(token in text for token in bad_tokens)
