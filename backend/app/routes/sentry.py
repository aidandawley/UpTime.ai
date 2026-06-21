import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session
from uagents.communication import send_sync_message

from app.config import settings
from app.database import get_session
from app.models.incident import Incident
from app.agents.models import IncidentMessage

router = APIRouter(prefix="/api/sentry", tags=["sentry"])


@router.post("/webhook")
async def sentry_webhook(
    request: Request,
    session: Session = Depends(get_session),
    sentry_hook_resource: str | None = Header(default=None, alias="Sentry-Hook-Resource"),
    sentry_hook_signature: str | None = Header(default=None, alias="Sentry-Hook-Signature"),
):
    body = await request.body()

    if settings.sentry_webhook_secret:
        if not sentry_hook_signature:
            raise HTTPException(status_code=401, detail="Missing Sentry webhook signature")

        digest = hmac.new(
            settings.sentry_webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(digest, sentry_hook_signature):
            raise HTTPException(status_code=401, detail="Invalid Sentry webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    data = payload.get("data", {})
    event = data.get("event") or {}
    issue = data.get("issue") or {}

    issue_id = event.get("issue_id") or issue.get("id")

    if not issue_id:
        raise HTTPException(status_code=400, detail="Missing Sentry issue id")

    title = (
        event.get("title")
        or issue.get("title")
        or event.get("message")
        or "Unknown Sentry issue"
    )

    issue_url = event.get("web_url") or event.get("issue_url") or issue.get("permalink")
    project = event.get("project") or payload.get("project")
    triggered_rule = data.get("triggered_rule") or data.get("issue_alert", {}).get("title")

    incident = Incident(
        sentry_issue_id=str(issue_id),
        title=title,
        issue_url=issue_url,
        repo_full_name=str(project) if project is not None else None,
        status="received",
        recommendation=f"Sentry alert received from rule: {triggered_rule}" if triggered_rule else None,
    )
    
    session.add(incident)
    session.commit()
    session.refresh(incident)

    if incident.id is None:
        raise HTTPException(status_code=500, detail="Incident was created without an id")

    repo_full_name = incident.repo_full_name or settings.default_repo_full_name

    if not repo_full_name:
        raise HTTPException(
            status_code=500,
            detail="Missing repo_full_name. Set DEFAULT_REPO_FULL_NAME in .env",
        )

    if not settings.investigation_agent_address:
        raise HTTPException(
            status_code=500,
            detail="Missing INVESTIGATION_AGENT_ADDRESS in .env",
        )

    msg = IncidentMessage(
        incident_id=incident.id,
        sentry_issue_id=incident.sentry_issue_id,
        title=incident.title,
        culprit=None,
        permalink=incident.issue_url,
        repo_full_name=repo_full_name,
        default_branch=settings.default_branch,
    )

    try:
        await send_sync_message(
            destination=settings.investigation_agent_address,
            message=msg,
            timeout=30,
        )

        incident.status = "agent_workflow_started"
        session.add(incident)
        session.commit()
        session.refresh(incident)

    except Exception as exc:
        incident.status = "agent_workflow_failed_to_start"
        incident.recommendation = (
            f"{incident.recommendation or ''}\n"
            f"Failed to start Fetch.ai workflow: {str(exc)}"
        ).strip()

        session.add(incident)
        session.commit()
        session.refresh(incident)

        raise HTTPException(
            status_code=502,
            detail=f"Incident saved, but failed to start Fetch.ai workflow: {str(exc)}",
        )

    return {
        "received": True,
        "incident_id": incident.id,
        "status": incident.status,
        "resource": sentry_hook_resource,
        "sentry_issue_id": incident.sentry_issue_id,
        "title": incident.title,
    }