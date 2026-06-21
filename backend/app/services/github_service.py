from github import Github
from app.config import settings


def create_demo_pr(
    repo_full_name: str,
    branch_name: str,
    commit_message: str,
    patch_summary: str,
    default_branch: str = "main",
):
    gh = Github(settings.github_token)
    repo = gh.get_repo(repo_full_name)

    base = repo.get_branch(default_branch)

    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base.commit.sha,
    )

    file_path = "AI_PATCH_RECOMMENDATION.md"
    content = f"""# AI Patch Recommendation

{patch_summary}
"""

    repo.create_file(
        path=file_path,
        message=commit_message,
        content=content,
        branch=branch_name,
    )

    pr = repo.create_pull(
        title=commit_message,
        body=patch_summary,
        head=branch_name,
        base=default_branch,
    )

    return pr.html_url