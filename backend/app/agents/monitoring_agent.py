from uagents import Agent, Context
from app.agents.models import IncidentMessage
from app.agents.addresses import MONITORING_SEED, INVESTIGATION_AGENT_ADDRESS

monitoring_agent = Agent(
    name="monitoring_agent",
    seed=MONITORING_SEED,
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"],
)

@monitoring_agent.on_message(model=IncidentMessage)
async def handle_incident(ctx: Context, sender: str, msg: IncidentMessage):
    ctx.logger.info(f"Received incident: {msg.title}")

    ctx.logger.info(
        f"Forwarding incident {msg.incident_id} to investigation agent"
    )
    
    await ctx.send(INVESTIGATION_AGENT_ADDRESS, msg)
    

if __name__ == "__main__":
    print("Monitoring address:", monitoring_agent.address)
    monitoring_agent.run()