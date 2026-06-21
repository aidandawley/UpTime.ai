from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.openai_api_key)


def generate_patch_plan(root_cause: str, recommendation: str) -> str:
    response = client.chat.completions.create(
        model="gpt-5.1",
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
                    )

    return response.choices[0].message.content or "No patch recommendation was generated."