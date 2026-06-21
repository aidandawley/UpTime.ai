from uagents import Agent, Context
from app.agents.models import PullRequestResult, ValidationResult
from app.agents.addresses import VALIDATION_SEED

validation_agent = Agent(
    name="validation_agent",
    seed=VALIDATION_SEED,
    port=8005,
    endpoint="http://127.0.0.1:8005/submit",
)


@validation_agent.on_message(model=PullRequestResult)
async def validate_pr(ctx: Context, sender: str, msg: PullRequestResult):
    ctx.logger.info(f"Validating PR: {msg.pr_url}")

    result = ValidationResult(
        incident_id=msg.incident_id,
        repo_full_name=msg.repo_full_name,
        pr_url=msg.pr_url,
        tests_passed=True,
        validation_summary="Demo validation passed. PR was created successfully.",
    )

    ctx.logger.info(result.model_dump_json())


if __name__ == "__main__":
    print("Validation address:", validation_agent.address)
    validation_agent.run()