from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    sentry_issue_id: str
    title: str
    status: str = "detected"
    severity: str = "unknown"

    issue_url: Optional[str] = None
    repo_full_name: Optional[str] = None
    recommendation: Optional[str] = None
    pr_url: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)