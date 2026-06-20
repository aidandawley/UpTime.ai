import httpx

from app.config import settings


async def analyze_incident_with_agent(payload: dict):
    url = f"{settings.fetch_ai_agent_url}/analyze-incident"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()