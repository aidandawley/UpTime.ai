# app/routes/incidents.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.incident import Incident
from app.models.recommendation import Recommendation

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
def list_incidents(session: Session = Depends(get_session)):
    incidents = session.exec(select(Incident).order_by(Incident.id.desc())).all()
    return incidents


@router.delete("/{incident_id}")
def delete_incident(incident_id: int, session: Session = Depends(get_session)):
    incident = session.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    recommendations = session.exec(
        select(Recommendation).where(Recommendation.incident_id == incident_id)
    ).all()

    for recommendation in recommendations:
        session.delete(recommendation)

    session.delete(incident)
    session.commit()

    return {
        "deleted": True,
        "incident_id": incident_id,
        "recommendations_deleted": len(recommendations),
    }
