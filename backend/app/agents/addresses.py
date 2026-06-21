from uagents import Agent

MONITORING_SEED = "monitoring-agent-secret-seed"
INVESTIGATION_SEED = "investigation-agent-secret-seed"
PATCH_SEED = "patch-agent-secret-seed"
GITHUB_SEED = "github-agent-secret-seed"
VALIDATION_SEED = "validation-agent-secret-seed"

MONITORING_AGENT_ADDRESS = Agent(name="monitoring_agent", seed=MONITORING_SEED).address
INVESTIGATION_AGENT_ADDRESS = Agent(name="investigation_agent", seed=INVESTIGATION_SEED).address
PATCH_AGENT_ADDRESS = Agent(name="patch_agent", seed=PATCH_SEED).address
GITHUB_AGENT_ADDRESS = Agent(name="github_agent", seed=GITHUB_SEED).address
VALIDATION_AGENT_ADDRESS = Agent(name="validation_agent", seed=VALIDATION_SEED).address