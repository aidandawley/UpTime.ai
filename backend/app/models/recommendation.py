from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Recommendation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    incident_id: int = Field(index=True)
    repo_full_name: str
    title: str
    summary: str
    justification: str
    code_patch: str
    changed_files: str
    tests_to_run: str
    risk: str
    workflow_notes: str = ""
    validation_status: str = "needs_review"
    validation_summary: str
    warnings: str = ""

    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    pr_branch: Optional[str] = None
    pr_creation_status: str = "not_requested"
    pr_creation_error: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
