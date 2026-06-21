from uagents import Model
from typing import Optional, List


class IncidentMessage(Model):
    incident_id: int
    sentry_issue_id: str
    title: str
    culprit: Optional[str] = None
    permalink: Optional[str] = None
    repo_full_name: str
    default_branch: str = "main"


class InvestigationResult(Model):
    incident_id: int
    sentry_issue_id: str
    repo_full_name: str
    severity: str
    suspected_root_cause: str
    files_to_inspect: List[str] = []
    recommendation: str


class PatchRequest(Model):
    incident_id: int
    repo_full_name: str
    default_branch: str
    suspected_root_cause: str
    recommendation: str
    files_to_inspect: List[str] = []


class PatchResult(Model):
    incident_id: int
    repo_full_name: str
    branch_name: str
    commit_message: str
    changed_files: List[str]
    patch_summary: str


class PullRequestResult(Model):
    incident_id: int
    repo_full_name: str
    pr_url: str
    branch_name: str
    changed_files: List[str]


class ValidationResult(Model):
    incident_id: int
    repo_full_name: str
    pr_url: str
    tests_passed: bool
    validation_summary: str