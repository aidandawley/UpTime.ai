import re
from dataclasses import dataclass
from typing import Callable

from github import Github, InputGitTreeElement

from app.agents.models import (
    PullRequestRequest,
    PullRequestResult,
    RepositoryContext,
    RepositoryFile,
)
from app.config import settings

DEFAULT_CONTEXT_FILES = [
    "backend/app/main.py",
    "backend/app/models.py",
    "backend/app/database.py",
    "README.md",
    "backend/app/routes/sentry.py",
    "backend/app/agents/models.py",
    "backend/app/agents/investigation_agent.py",
    "backend/app/agents/github_agent.py",
    "backend/app/agents/patch_agent.py",
    "backend/app/agents/validation_agent.py",
    "frontend/src/App.tsx",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
]

PLACEHOLDER_MARKERS = (
    "existing failing behavior",
    "existing failing path",
    "todo: implement",
    "your code here",
    "placeholder",
)


class UnsafePatchError(ValueError):
    """Raised before GitHub is modified when a generated patch is not exact/safe."""


@dataclass(frozen=True)
class FilePatch:
    path: str
    hunks: list[tuple[int, list[str]]]


def create_pull_request(
    request: PullRequestRequest,
    on_step: Callable[[str, str], None] | None = None,
) -> PullRequestResult:
    """Create one commit and PR without ever modifying the default branch."""
    token = (settings.github_token or "").strip()
    branch_name = f"uptime-ai/incident-{request.incident_id}"
    if not token:
        return PullRequestResult(
            status="skipped",
            branch_name=branch_name,
            error="GitHub credentials are unavailable.",
        )

    patches = parse_unified_diff(request.code_patch)
    expected_files = {_clean_repo_path(path) for path in request.changed_files}
    patch_files = {patch.path for patch in patches}
    if not expected_files or "UNKNOWN_FILE" in expected_files:
        raise UnsafePatchError("Changed files are unknown.")
    if expected_files != patch_files:
        raise UnsafePatchError("Patch files do not exactly match the validated changed files.")
    lowered = request.code_patch.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        raise UnsafePatchError("Patch contains placeholder content.")

    repo = Github(token).get_repo(_normalize_repo_full_name(request.repo_full_name))
    default_branch = repo.default_branch

    existing = _find_pull_request(repo, branch_name, default_branch)
    if existing is not None:
        return PullRequestResult(
            status="existing",
            branch_name=branch_name,
            pr_url=existing.html_url,
            pr_number=existing.number,
        )

    default_ref = repo.get_git_ref(f"heads/{default_branch}")
    base_sha = default_ref.object.sha
    try:
        branch_ref = repo.get_git_ref(f"heads/{branch_name}")
        if branch_ref.object.sha != base_sha:
            raise UnsafePatchError(
                "The incident branch already exists with different content; refusing to overwrite it."
            )
    except UnsafePatchError:
        raise
    except Exception as exc:
        if getattr(exc, "status", None) != 404:
            raise
        branch_ref = repo.create_git_ref(f"refs/heads/{branch_name}", base_sha)
        if on_step:
            on_step("branch created", branch_name)

    base_commit = repo.get_git_commit(base_sha)
    base_tree = repo.get_git_tree(base_commit.tree.sha, recursive=True)
    file_modes = {
        element.path: element.mode
        for element in base_tree.tree
        if element.type == "blob"
    }
    blobs: list[InputGitTreeElement] = []
    for file_patch in patches:
        if file_patch.path not in file_modes:
            raise UnsafePatchError(f"Patch target is not a tracked file: {file_patch.path}")
        contents = repo.get_contents(file_patch.path, ref=base_sha)
        if isinstance(contents, list):
            raise UnsafePatchError(f"Patch target is not a file: {file_patch.path}")
        original = contents.decoded_content.decode("utf-8")
        updated = apply_file_patch(original, file_patch)
        blob = repo.create_git_blob(updated, "utf-8")
        blobs.append(
            InputGitTreeElement(
                path=file_patch.path,
                mode=file_modes[file_patch.path],
                type="blob",
                sha=blob.sha,
            )
        )
    if on_step:
        on_step("patch applied", ", ".join(patch_files))

    tree = repo.create_git_tree(blobs, base_tree=base_commit.tree)
    commit = repo.create_git_commit(
        f"Fix incident {request.incident_id}: {request.recommendation_title}",
        tree,
        [base_commit],
    )
    branch_ref.edit(commit.sha, force=False)
    if on_step:
        on_step("commit created", commit.sha)
    pull = repo.create_pull(
        title=request.recommendation_title,
        body=_pull_request_body(request),
        head=branch_name,
        base=default_branch,
    )
    if on_step:
        on_step("PR opened", pull.html_url)
    return PullRequestResult(
        status="created",
        branch_name=branch_name,
        pr_url=pull.html_url,
        pr_number=pull.number,
    )


def parse_unified_diff(text: str) -> list[FilePatch]:
    if not text.strip():
        raise UnsafePatchError("Patch is empty.")
    lines = text.splitlines(keepends=True)
    patches: list[FilePatch] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        old_path = lines[index][4:].strip().split("\t", 1)[0]
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            raise UnsafePatchError("Malformed unified diff file header.")
        new_path = lines[index][4:].strip().split("\t", 1)[0]
        if old_path == "/dev/null" or new_path == "/dev/null":
            raise UnsafePatchError("Creating or deleting files is not supported safely.")
        path = _clean_repo_path(new_path)
        if _clean_repo_path(old_path) != path:
            raise UnsafePatchError("Renames are not supported safely.")
        index += 1
        hunks: list[tuple[int, list[str]]] = []
        while index < len(lines) and not lines[index].startswith("--- "):
            if lines[index].startswith("@@ "):
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", lines[index])
                if not match:
                    raise UnsafePatchError("Malformed unified diff hunk header.")
                old_start = int(match.group(1))
                index += 1
                body: list[str] = []
                while index < len(lines) and not lines[index].startswith(("@@ ", "--- ")):
                    line = lines[index]
                    if line.startswith("\\ No newline at end of file"):
                        index += 1
                        continue
                    if not line.startswith((" ", "+", "-")):
                        raise UnsafePatchError("Malformed unified diff hunk body.")
                    body.append(line)
                    index += 1
                hunks.append((old_start, body))
            elif lines[index].strip() == "":
                index += 1
            else:
                raise UnsafePatchError("Unexpected content between diff headers and hunks.")
        if not hunks:
            raise UnsafePatchError(f"No patch hunks found for {path}.")
        patches.append(FilePatch(path=path, hunks=hunks))
    if not patches:
        raise UnsafePatchError("No unified diff file sections were found.")
    if len({patch.path for patch in patches}) != len(patches):
        raise UnsafePatchError("A changed file appears more than once in the patch.")
    return patches


def apply_file_patch(original: str, patch: FilePatch) -> str:
    source = original.splitlines(keepends=True)
    output: list[str] = []
    cursor = 0
    for old_start, hunk in patch.hunks:
        start = old_start - 1
        if start < cursor or start > len(source):
            raise UnsafePatchError(f"Invalid or overlapping hunk for {patch.path}.")
        output.extend(source[cursor:start])
        cursor = start
        for diff_line in hunk:
            marker, value = diff_line[0], diff_line[1:]
            if marker in (" ", "-"):
                if cursor >= len(source) or source[cursor] != value:
                    raise UnsafePatchError(
                        f"Patch context does not match default-branch content for {patch.path}."
                    )
                if marker == " ":
                    output.append(source[cursor])
                cursor += 1
            else:
                output.append(value)
    output.extend(source[cursor:])
    updated = "".join(output)
    if updated == original:
        raise UnsafePatchError(f"Patch makes no changes to {patch.path}.")
    return updated


def _find_pull_request(repo, branch_name: str, default_branch: str):
    owner = repo.full_name.split("/", 1)[0]
    pulls = repo.get_pulls(
        state="all", head=f"{owner}:{branch_name}", base=default_branch
    )
    return next(iter(pulls), None)


def _pull_request_body(request: PullRequestRequest) -> str:
    issue = request.sentry_issue_id or "Not available"
    files = "\n".join(f"- `{path}`" for path in request.changed_files)
    tests = "\n".join(f"- {test}" for test in request.tests_to_run) or "- None provided"
    return f"""## Incident
- **Incident ID:** {request.incident_id}
- **Sentry issue ID:** {issue}

## Recommendation
**{request.recommendation_title}**

### Suspected root cause / justification
{request.justification}

### Changed files
{files}

### Risk assessment
{request.risk or "Not provided"}

### Recommended tests
{tests}

> This patch was AI-generated and requires developer review. It has not been automatically merged.
"""


def _clean_repo_path(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith(("a/", "b/")):
        cleaned = cleaned[2:]
    if not cleaned or cleaned.startswith("/") or ".." in cleaned.split("/"):
        raise UnsafePatchError(f"Unsafe repository path: {path}")
    return cleaned


def load_repository_context(
    repo_full_name: str,
    default_branch: str = "main",
    files_to_inspect: list[str] | None = None,
    max_chars_per_file: int = 4000,
) -> RepositoryContext:
    repo_full_name = _normalize_repo_full_name(repo_full_name)
    default_branch = default_branch.strip() or "main"
    paths = _dedupe([*(files_to_inspect or []), *DEFAULT_CONTEXT_FILES])

    github_token = settings.github_token.strip() if settings.github_token else None

    if not github_token:
        return RepositoryContext(
            repo_full_name=repo_full_name,
            default_branch=default_branch,
            summary="GitHub token is not configured, so repository context is unavailable.",
            files=[],
        )

    try:
        gh = Github(github_token)
        repo = gh.get_repo(repo_full_name)
    except Exception as exc:
        return RepositoryContext(
            repo_full_name=repo_full_name,
            default_branch=default_branch,
            summary=(
                f"Failed to load repository metadata for {repo_full_name} "
                f"on branch {default_branch}: {exc}"
            ),
            files=[],
        )

    loaded_files: list[RepositoryFile] = []

    for path in paths:
        try:
            contents = repo.get_contents(path, ref=default_branch)
        except Exception:
            continue

        if isinstance(contents, list):
            continue

        try:
            text = contents.decoded_content.decode("utf-8", errors="replace")
        except Exception:
            continue

        truncated = len(text) > max_chars_per_file
        loaded_files.append(
            RepositoryFile(
                path=path,
                content=text[:max_chars_per_file],
                truncated=truncated,
            )
        )

    return RepositoryContext(
        repo_full_name=repo_full_name,
        default_branch=default_branch,
        summary=(
            f"Loaded {len(loaded_files)} repository files from {repo_full_name} "
            f"on branch {default_branch}."
        ),
        files=loaded_files,
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    return result


def _normalize_repo_full_name(repo_full_name: str) -> str:
    cleaned = repo_full_name.strip()

    if cleaned.startswith("https://github.com/"):
        cleaned = cleaned.removeprefix("https://github.com/")

    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    return cleaned.strip("/")
