import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, select
from uagents.communication import send_message
from uagents_core.types import DeliveryStatus

from app.config import settings
from app.database import get_session
from app.models.incident import Incident
from app.agents.models import IncidentMessage, RecentIncident
from app.agents.addresses import LOCAL_AGENT_RESOLVER
from app.agents.workflow_trace import trace_step

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
        print("[sentry] rejected webhook: invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    print("Received Sentry webhook")
    print(f"Sentry-Hook-Resource: {sentry_hook_resource}")
    print(json.dumps(payload, indent=2, sort_keys=True))

    data = payload.get("data", {})
    event = data.get("event") or {}
    issue = data.get("issue") or {}

    issue_id = event.get("issue_id") or issue.get("id")

    if not issue_id:
        print("[sentry] rejected webhook: missing Sentry issue id")
        raise HTTPException(status_code=400, detail="Missing Sentry issue id")

    title = (
        event.get("title")
        or issue.get("title")
        or event.get("message")
        or "Unknown Sentry issue"
    )

    issue_url = event.get("web_url") or event.get("issue_url") or issue.get("permalink")
    repo_full_name = payload.get("repo_full_name") or settings.default_repo_full_name
    triggered_rule = data.get("triggered_rule") or data.get("issue_alert", {}).get("title")
    level = event.get("level") or "unknown"
    environment = event.get("environment")
    context = _request_context_from_event(event)
    full_error = _full_error_from_event(event)

    trace_step(
        "webhook",
        None,
        "received Sentry webhook payload",
        sentry_issue_id=issue_id,
        resource=sentry_hook_resource,
        title=title,
        level=level,
        status_code=context["status_code"],
        route=context["route"],
        event_type=context["event_type"],
    )

    if not repo_full_name:
        print("[sentry] warning: no repo in payload and DEFAULT_REPO_FULL_NAME is unset")

    if not full_error:
        print(f"[sentry] warning: issue {issue_id} has no detailed error text")

    incident = Incident(
        sentry_issue_id=str(issue_id),
        title=title,
        issue_url=issue_url,
        repo_full_name=repo_full_name,
        status="received",
        severity=level,
        recommendation=f"Sentry alert received from rule: {triggered_rule}" if triggered_rule else None,
    )
    
    session.add(incident)
    session.commit()
    session.refresh(incident)

    if incident.id is None:
        raise HTTPException(status_code=500, detail="Incident was created without an id")

    trace_step(
        "webhook",
        incident.id,
        "saved incident to database",
        sentry_issue_id=incident.sentry_issue_id,
        title=incident.title,
        severity=incident.severity,
        repo=incident.repo_full_name,
    )

    recent_incidents = _recent_incidents(session=session, exclude_incident_id=incident.id)
    workflow_repo_full_name = incident.repo_full_name or settings.default_repo_full_name

    if not workflow_repo_full_name:
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
        culprit=event.get("culprit"),
        permalink=incident.issue_url,
        repo_full_name=workflow_repo_full_name,
        default_branch=settings.default_branch,
        level=level,
        environment=environment,
        full_error=full_error,
        http_method=context["method"],
        route=context["route"],
        status_code=context["status_code"],
        event_type=context["event_type"],
        recent_incidents=recent_incidents,
    )

    try:
        print(
            f"[sentry] forwarding incident {incident.id} to investigation "
            f"with {len(recent_incidents)} recent incidents"
        )
        trace_step(
            "webhook",
            incident.id,
            "forwarding incident to Investigation Agent",
            recent_incidents=len(recent_incidents),
            destination=settings.investigation_agent_address,
        )
        delivery = await send_message(
            destination=settings.investigation_agent_address,
            message=msg,
            resolver=LOCAL_AGENT_RESOLVER,
            timeout=30,
        )

        if delivery.status != DeliveryStatus.DELIVERED:
            print(
                f"[sentry] investigation delivery failed for incident {incident.id}: "
                f"{delivery.status} - {delivery.detail}"
            )
            raise RuntimeError(f"{delivery.status}: {delivery.detail}")

        print(f"[sentry] investigation delivery ok for incident {incident.id}")
        trace_step(
            "webhook",
            incident.id,
            "Investigation Agent accepted handoff",
            delivery=delivery.status,
        )

        incident.status = "agent_workflow_started"
        session.add(incident)
        session.commit()
        session.refresh(incident)

    except Exception as exc:
        trace_step(
            "webhook",
            incident.id,
            "Investigation Agent handoff failed",
            error=str(exc),
        )
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


def _full_error_from_event(event: dict) -> str | None:
    details: list[str] = []
    message = event.get("message")
    logentry = event.get("logentry") or {}
    formatted = logentry.get("formatted")
    extra = event.get("extra") or {}
    context = _request_context_from_event(event)
    exception_values = (
        event.get("exception", {})
        .get("values", [])
    )

    if exception_values:
        exception = exception_values[0]
        exception_type = exception.get("type")
        exception_value = exception.get("value")
        details.append(": ".join(part for part in [exception_type, exception_value] if part))

    if formatted:
        details.append(formatted)
    elif message:
        details.append(message)

    request_parts = []
    if context["method"]:
        request_parts.append(f"method={context['method']}")
    if context["route"]:
        request_parts.append(f"route={context['route']}")
    if context["status_code"] is not None:
        request_parts.append(f"status_code={context['status_code']}")
    if context["url"]:
        request_parts.append(f"url={context['url']}")
    if context["event_type"]:
        request_parts.append(f"event_type={context['event_type']}")

    if request_parts:
        details.append("request_context " + " ".join(request_parts))

    if extra:
        compact_extra = {
            key: value
            for key, value in extra.items()
            if key in {"app", "event_type", "path", "route", "status_code"}
        }
        if compact_extra:
            details.append(f"extra={compact_extra}")

    unique_details = list(dict.fromkeys(detail for detail in details if detail))
    return "\n".join(unique_details) if unique_details else None


def _request_context_from_event(event: dict) -> dict:
    request = event.get("request") or {}
    extra = event.get("extra") or {}
    raw_status_code = extra.get("status_code")

    try:
        status_code = int(raw_status_code) if raw_status_code is not None else None
    except (TypeError, ValueError):
        status_code = None

    return {
        "method": extra.get("method") or request.get("method"),
        "route": extra.get("route") or extra.get("path"),
        "status_code": status_code,
        "url": request.get("url"),
        "event_type": extra.get("event_type"),
    }


def _recent_incidents(
    session: Session,
    exclude_incident_id: int,
    limit: int = 5,
) -> list[RecentIncident]:
    incidents = session.exec(
        select(Incident)
        .where(Incident.id != exclude_incident_id)
        .order_by(Incident.id.desc())
        .limit(limit)
    ).all()

    return [
        RecentIncident(
            incident_id=incident.id or 0,
            sentry_issue_id=incident.sentry_issue_id,
            title=incident.title,
            status=incident.status,
            severity=incident.severity,
            issue_url=incident.issue_url,
            recommendation=incident.recommendation,
        )
        for incident in incidents
    ]
