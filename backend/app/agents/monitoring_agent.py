from uagents import Agent, Context
from app.agents.models import IncidentMessage
from app.agents.addresses import (
    INVESTIGATION_AGENT_ADDRESS,
    LOCAL_AGENT_RESOLVER,
    MONITORING_AGENT_ENDPOINT,
    MONITORING_SEED,
)

monitoring_agent = Agent(
    name="monitoring_agent",
    seed=MONITORING_SEED,
    port=8001,
    endpoint=[MONITORING_AGENT_ENDPOINT],
    resolve=LOCAL_AGENT_RESOLVER,
)

@monitoring_agent.on_message(model=IncidentMessage)
async def handle_incident(ctx: Context, sender: str, msg: IncidentMessage):
    ctx.logger.info(f"Received incident: {msg.title}")

    ctx.logger.info(
        f"Forwarding incident {msg.incident_id} to investigation agent"
    )
    
    status = await ctx.send(INVESTIGATION_AGENT_ADDRESS, msg)
    ctx.logger.info(f"Investigation agent delivery status: {status.status} - {status.detail}")
    

if __name__ == "__main__":
    print("Monitoring address:", monitoring_agent.address)
    monitoring_agent.run()
