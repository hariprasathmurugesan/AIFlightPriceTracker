# src/agents/llm_summarizer.py

from langchain_openai import ChatOpenAI
from utils.config import Config


def summarize_for_sms(best_day_ascii: str, top3_ascii: str) -> str:
    """
    Summarizes the best-day and top-3 ASCII tables into a short,
    SMS-friendly message using the LLM.
    """

    llm = ChatOpenAI(
        api_key=Config.openai_api_key(),
        base_url=Config.openai_api_base(),
        model=Config.openai_model(),
        temperature=0.2,
    )

    prompt = f"""
Summarize the following flight analysis into a short, SMS-friendly message.
Keep it under 800 characters. Make it clear, concise, and useful for a traveler.
Avoid ASCII tables. Use plain text only.

BEST DAY SUMMARY:
{best_day_ascii}

TOP 3 OVERALL:
{top3_ascii}
"""

    response = llm.invoke(prompt).content
    return response.strip()
