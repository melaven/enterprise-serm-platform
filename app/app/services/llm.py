import os

from openai import AsyncOpenAI


_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def generate_review_response(review_text: str, rating: int) -> str:
    response = await _client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "Write a concise, professional response to a customer review in Russian.",
            },
            {
                "role": "user",
                "content": f"Rating: {rating}/5\nReview: {review_text}",
            },
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content or ""
