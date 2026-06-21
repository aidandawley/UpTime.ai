from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.asi_one_api_key, base_url=settings.asi_one_base_url)


def generate_patch_plan(root_cause: str, recommendation: str) -> str:
    response = client.chat.completions.create(
        model=settings.asi_one_model,
        messages=[
            {
                "role": "system",
                "content": "You are a senior software engineer. Generate safe minimal patches.",
            },
            {
                "role": "user",
                "content": f"""
                Root cause:
                {root_cause}

                Recommendation:
                {recommendation}

                Return:
                1. likely file
                2. patch strategy
                3. risk
                4. test suggestion
                """,
            },
        ],
        temperature=0.2,
        max_tokens=1200,
        extra_body={
            "web_search": False
        },
    )

    return response.choices[0].message.content or "No patch recommendation was generated."