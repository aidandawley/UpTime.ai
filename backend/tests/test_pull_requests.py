from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.agents.models import PullRequestRequest
from app.models.recommendation import Recommendation
from app.routes import recommendations as recommendation_routes
from app.services import github_service
from app.services.github_service import UnsafePatchError


PATCH = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-old = True
+old = False
 keep = 1
"""


def request(**overrides):
    values = {
        "incident_id": 42,
        "sentry_issue_id": "SENTRY-9",
        "repo_full_name": "owner/repo",
        "recommendation_title": "Fix the failure",
        "justification": "The old value causes the reported failure.",
        "code_patch": PATCH,
        "changed_files": ["app.py"],
        "risk": "Low",
        "tests_to_run": ["pytest"],
    }
    values.update(overrides)
    return PullRequestRequest(**values)


class FakeRepo:
    full_name = "owner/repo"
    default_branch = "main"

    def __init__(self, *, existing_pull=None, fail_pull=False):
        self.existing_pull = existing_pull
        self.fail_pull = fail_pull
        self.branch = None
        self.ref = SimpleNamespace(object=SimpleNamespace(sha="base"))

    def get_pulls(self, **kwargs):
        return [self.existing_pull] if self.existing_pull else []

    def get_git_ref(self, name):
        if name == "heads/main":
            return self.ref
        if self.branch:
            return self.branch
        error = RuntimeError("not found")
        error.status = 404
        raise error

    def create_git_ref(self, name, sha):
        self.branch = SimpleNamespace(
            object=SimpleNamespace(sha=sha),
            edit=lambda new_sha, force: setattr(self.branch.object, "sha", new_sha),
        )
        return self.branch

    def get_contents(self, path, ref):
        assert path == "app.py" and ref == "base"
        return SimpleNamespace(decoded_content=b"old = True\nkeep = 1\n")

    def create_git_blob(self, content, encoding):
        assert content == "old = False\nkeep = 1\n"
        return SimpleNamespace(sha="blob")

    def get_git_commit(self, sha):
        return SimpleNamespace(sha=sha, tree=SimpleNamespace(sha="tree"))

    def get_git_tree(self, sha, recursive):
        return SimpleNamespace(
            tree=[SimpleNamespace(path="app.py", mode="100644", type="blob")]
        )

    def create_git_tree(self, blobs, base_tree):
        assert len(blobs) == 1
        return SimpleNamespace(sha="new-tree")

    def create_git_commit(self, message, tree, parents):
        return SimpleNamespace(sha="commit")

    def create_pull(self, **kwargs):
        if self.fail_pull:
            raise RuntimeError("GitHub unavailable")
        return SimpleNamespace(number=7, html_url="https://github.test/owner/repo/pull/7")


def install_github(monkeypatch, repo):
    monkeypatch.setattr(github_service.settings, "github_token", "token")
    monkeypatch.setattr(
        github_service,
        "Github",
        lambda token: SimpleNamespace(get_repo=lambda name: repo),
    )


def test_successful_pr_creation(monkeypatch):
    repo = FakeRepo()
    install_github(monkeypatch, repo)
    steps = []

    result = github_service.create_pull_request(
        request(), on_step=lambda stage, detail: steps.append(stage)
    )

    assert result.status == "created"
    assert result.pr_number == 7
    assert result.branch_name == "uptime-ai/incident-42"
    assert steps == ["branch created", "patch applied", "commit created", "PR opened"]


def test_malformed_patch_is_rejected_before_github(monkeypatch):
    monkeypatch.setattr(github_service.settings, "github_token", "token")
    with pytest.raises(UnsafePatchError, match="No unified diff"):
        github_service.create_pull_request(request(code_patch="change app.py"))


def test_placeholder_patch_is_rejected(monkeypatch):
    monkeypatch.setattr(github_service.settings, "github_token", "token")
    with pytest.raises(UnsafePatchError, match="placeholder"):
        github_service.create_pull_request(
            request(code_patch=PATCH.replace("old = False", "# placeholder"))
        )


def test_duplicate_pr_returns_existing(monkeypatch):
    pull = SimpleNamespace(number=3, html_url="https://github.test/pull/3")
    install_github(monkeypatch, FakeRepo(existing_pull=pull))

    result = github_service.create_pull_request(request())

    assert result.status == "existing"
    assert result.pr_number == 3


def test_missing_credentials_skips(monkeypatch):
    monkeypatch.setattr(github_service.settings, "github_token", None)
    result = github_service.create_pull_request(request())
    assert result.status == "skipped"
    assert "credentials" in result.error


def recommendation(status="approved"):
    return Recommendation(
        incident_id=42,
        repo_full_name="owner/repo",
        title="Fix",
        summary="Summary",
        justification="Cause",
        code_patch=PATCH,
        changed_files="app.py",
        tests_to_run="pytest",
        risk="Low",
        validation_status=status,
        validation_summary="Checked",
    )


def memory_session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_validation_failure_never_calls_github(monkeypatch):
    session = memory_session()
    item = recommendation("needs_review")
    session.add(item)
    session.commit()
    session.refresh(item)
    monkeypatch.setattr(
        recommendation_routes,
        "create_pull_request",
        lambda *args, **kwargs: pytest.fail("GitHub must not be called"),
    )

    result = recommendation_routes.open_pull_request(item.id, session)

    assert result.pr_creation_status == "skipped"
    assert result.code_patch == PATCH


def test_github_api_failure_keeps_recommendation(monkeypatch):
    session = memory_session()
    item = recommendation()
    session.add(item)
    session.commit()
    session.refresh(item)
    monkeypatch.setattr(
        recommendation_routes,
        "create_pull_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API failed")),
    )

    result = recommendation_routes.open_pull_request(item.id, session)

    assert result.pr_creation_status == "failed"
    assert result.pr_creation_error == "API failed"
    assert result.code_patch == PATCH
