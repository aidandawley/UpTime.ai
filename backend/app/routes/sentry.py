from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models.incident import Incident
from app.services.agent_service import analyze_incident_with_agent

router = APIRouter(prefix="/api/sentry", tags=["sentry"])


@router.post("/webhook")
async def sentry_webhook(payload: dict, session: Session = Depends(get_session)):
    issue = payload.get("data", {}).get("issue", {})
    issue_id = issue.get("id")

    if not issue_id:
        raise HTTPException(status_code=400, detail="Missing Sentry issue id")

    incident = Incident(
        sentry_issue_id=str(issue_id),
        title=issue.get("title", "Unknown Sentry issue"),
        issue_url=issue.get("permalink"),
        repo_full_name=payload.get("repo_full_name"),
        status="detected",
    )

    session.add(incident)
    session.commit()
    session.refresh(incident)

    agent_payload = {
        "repo_full_name": incident.repo_full_name or "unknown/repo",
        "sentry_issue_id": incident.sentry_issue_id,
        "issue_title": incident.title,
        "issue_url": incident.issue_url,
    }

    try:
        agent_result = await analyze_incident_with_agent(agent_payload)

        incident.status = agent_result.get("status", "recommendation_created")
        incident.severity = agent_result.get("severity", "unknown")
        incident.recommendation = agent_result.get("recommendation")

        session.add(incident)
        session.commit()
        session.refresh(incident)

    except Exception as e:
        incident.status = "agent_failed"
        incident.recommendation = f"Agent failed: {str(e)}"
        session.add(incident)
        session.commit()

    return {
        "received": True,
        "incident_id": incident.id,
        "status": incident.status,
    }
