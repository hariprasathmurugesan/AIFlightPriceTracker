# src/agents/llm_insights.py

from langchain_openai import ChatOpenAI
from utils.config import Config


def generate_travel_insights(best_day_ascii: str, top3_ascii: str, daily_ascii: str) -> str:
    """
    Generates a human-friendly travel insights section using the LLM.
    """

    llm = ChatOpenAI(
        api_key=Config.openai_api_key(),
        base_url=Config.openai_api_base(),
        model=Config.openai_model(),
        temperature=0.4,
    )

    prompt = f"""
You are a travel analyst. Based on the following flight data, write a clear,
insightful, human-friendly "Travel Insights" section.

Keep it under 200 words. Avoid ASCII tables. Focus on:

- Price patterns
- Airline consistency
- Layover quality
- Best-value days
- Any anomalies or interesting observations
- A short recommendation at the end

BEST DAY SUMMARY:
{best_day_ascii}

TOP 3 OVERALL:
{top3_ascii}

DAILY DETAILS:
{daily_ascii}

Write the insights in a friendly, expert tone.
"""

    response = llm.invoke(prompt).content
    return response.strip()
