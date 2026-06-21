from typing import Optional, List

from uagents import Model


class RecentIncident(Model):
    incident_id: int
    sentry_issue_id: str
    title: str
    status: str
    severity: str
    issue_url: Optional[str] = None
    recommendation: Optional[str] = None


class IncidentMessage(Model):
    incident_id: int
    sentry_issue_id: str
    title: str
    culprit: Optional[str] = None
    permalink: Optional[str] = None
    repo_full_name: str
    default_branch: str = "main"
    level: str = "unknown"
    environment: Optional[str] = None
    full_error: Optional[str] = None
    http_method: Optional[str] = None
    route: Optional[str] = None
    status_code: Optional[int] = None
    event_type: Optional[str] = None
    recent_incidents: List[RecentIncident] = []


class InvestigationResult(Model):
    incident_id: int
    sentry_issue_id: str
    repo_full_name: str
    default_branch: str
    is_actionable: bool
    confidence: float
    severity: str
    reason: str
    suspected_root_cause: str
    files_to_inspect: List[str] = []
    recommendation: str
    recent_incidents: List[RecentIncident] = []


class RepositoryFile(Model):
    path: str
    content: str
    truncated: bool = False


class RepositoryContext(Model):
    repo_full_name: str
    default_branch: str
    summary: str
    files: List[RepositoryFile] = []


class PatchRequest(Model):
    incident_id: int
    repo_full_name: str
    default_branch: str
    severity: str
    suspected_root_cause: str
    recommendation: str
    files_to_inspect: List[str] = []
    repository_context: RepositoryContext
    recent_incidents: List[RecentIncident] = []


class PatchResult(Model):
    incident_id: int
    repo_full_name: str
    changed_files: List[str]
    patch_summary: str
    code_recommendation: str
    code_patch: str
    risk: str
    tests_to_run: List[str] = []


class ValidationResult(Model):
    incident_id: int
    repo_full_name: str
    looks_safe: bool
    validation_summary: str
    warnings: List[str] = []
