from openai import OpenAI

from app.agents.models import RecentIncident, RepositoryContext
from app.config import settings


def generate_patch_plan(
    root_cause: str,
    recommendation: str,
    repository_context: RepositoryContext,
    recent_incidents: list[RecentIncident],
) -> str:
    if not settings.asi_one_api_key:
        return _fallback_patch_plan(root_cause, recommendation, repository_context)

    client = OpenAI(api_key=settings.asi_one_api_key, base_url=settings.asi_one_base_url)

    try:
        response = client.chat.completions.create(
            model=settings.asi_one_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer. Return a safe code "
                        "recommendation only. Do not claim a PR was created."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_patch_prompt(
                        root_cause=root_cause,
                        recommendation=recommendation,
                        repository_context=repository_context,
                        recent_incidents=recent_incidents,
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=1600,
            extra_body={"web_search": False},
        )
        return response.choices[0].message.content or _fallback_patch_plan(
            root_cause,
            recommendation,
            repository_context,
        )
    except Exception as exc:
        return (
            _fallback_patch_plan(root_cause, recommendation, repository_context)
            + f"\nMODEL NOTE:\nPatch model unavailable, used fallback: {exc}\n"
        )


def _build_patch_prompt(
    root_cause: str,
    recommendation: str,
    repository_context: RepositoryContext,
    recent_incidents: list[RecentIncident],
) -> str:
    recent_alerts = "\n".join(
        f"- {incident.title} [{incident.severity}/{incident.status}]"
        for incident in recent_incidents
    ) or "- No recent alerts supplied."

    files = "\n\n".join(
        f"FILE: {file.path}\n{file.content}"
        for file in repository_context.files
    ) or "No repository files were loaded."

    return f"""
Root cause:
{root_cause}

Investigation recommendation:
{recommendation}

Recent Sentry context:
{recent_alerts}

Repository context summary:
{repository_context.summary}

Repository files:
{files}

Return exactly these sections:
PATCH SUMMARY:
CODE RECOMMENDATION:
CODE PATCH:
RISK:
TESTS TO RUN:
"""


def _fallback_patch_plan(
    root_cause: str,
    recommendation: str,
    repository_context: RepositoryContext,
) -> str:
    file_hint = repository_context.files[0].path if repository_context.files else "UNKNOWN_FILE"

    return f"""PATCH SUMMARY:
Investigate {file_hint} for the suspected failure and make the smallest defensive change.

CODE RECOMMENDATION:
{recommendation}

CODE PATCH:
--- {file_hint}
+++ {file_hint}
@@
- existing failing path
+ add explicit validation, guard, or fallback handling around: {root_cause}

RISK:
Low to medium. The exact code needs developer review because repository context was limited.

TESTS TO RUN:
- Reproduce the Sentry request locally
- Run the route or unit test covering {file_hint}
"""
