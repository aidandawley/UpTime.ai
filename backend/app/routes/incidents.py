# app/routes/incidents.py

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.incident import Incident

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
def list_incidents(session: Session = Depends(get_session)):
    incidents = session.exec(select(Incident).order_by(Incident.id.desc())).all()
    return incidents