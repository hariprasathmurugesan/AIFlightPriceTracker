from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from core.processor import build_full_report

from utils.config import Config
from api.amadeus_client import AmadeusClient
from core.processor import (
    extract_flights,
    compute_best_day,
    build_best_day_section,
    build_top3_overall_section,
    build_daily_sections,
)


# ---------------------------------------------------------
# LLM DATE EXTRACTION (FUTURE-ONLY)
# ---------------------------------------------------------

def llm_extract_dates(user_request: str):
    """
    Extracts a future start/end date from the user's request.
    If unclear, defaults to a 5-day window starting tomorrow.
    """

    llm = ChatOpenAI(
        api_key=Config.openai_api_key(),
        base_url=Config.openai_api_base(),
        model=Config.openai_model(),
        temperature=0,
    )

    prompt = f"""
    Extract a start date and end date from this request:

    "{user_request}"

    RULES:
    - Dates MUST be in the future relative to today ({datetime.now().date()}).
    - If the request does not specify dates, choose a 5-day window starting tomorrow.
    - Respond ONLY in this JSON format:

    {{
        "start": "YYYY-MM-DD",
        "end": "YYYY-MM-DD"
    }}
    """

    response = llm.invoke(prompt).content

    import json
    try:
        data = json.loads(response)
        start = datetime.strptime(data["start"], "%Y-%m-%d").date()
        end = datetime.strptime(data["end"], "%Y-%m-%d").date()

        # Force future dates
        today = datetime.now().date()
        if start <= today:
            start = today + timedelta(days=1)
        if end <= start:
            end = start + timedelta(days=4)

        return str(start), str(end)

    except:
        # fallback: tomorrow + 5 days
        tomorrow = datetime.now().date() + timedelta(days=1)
        return str(tomorrow), str(tomorrow + timedelta(days=4))


# ---------------------------------------------------------
# MAIN PIPELINE (NO AGENTS)
# ---------------------------------------------------------

def run_pipeline_llm_routed(user_request: str):
    """
    AI pipeline with fixed date range (March 20–24, 2026),
    same filters as classic mode.
    """

    # Fixed date range
    start_date = datetime(2026, 3, 20)
    end_date = datetime(2026, 3, 31)

    client = AmadeusClient()

    all_days = []
    daily_raw = {}

    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")

        raw = client.search_flights("YYZ", "MAA", date_str)

        # Skip invalid responses
        if not raw or "errors" in raw:
            current += timedelta(days=1)
            continue

        carriers = raw.get("dictionaries", {}).get("carriers", {})
        flights = extract_flights(raw, carriers)

        # Exclude unwanted airlines globally
        excluded = {"CX", "AI"}
        flights = [
            f for f in flights
            if f["airline"].split(" — ")[0] not in excluded
        ]

        # Same filter as classic mode
        flights = [f for f in flights if float(f["layover_hours"]) <= 6]


        all_days.append({"date": date_str, "flights": flights})
        daily_raw[date_str] = flights

        current += timedelta(days=1)

    # If no valid days
    if not all_days:
        return (
            "No valid flight data found for March 20–24, 2026.\n"
            "Try again later."
        )

    # Compute best-day summary
    summary = compute_best_day(all_days)

    final_report = build_full_report(
    summary,
    summary["top3_overall"],
    daily_raw
    )

    best_day_ascii = build_best_day_section(summary)
    top3_ascii = build_top3_overall_section(summary["top3_overall"])
    daily_ascii = build_daily_sections(daily_raw)


    return final_report, best_day_ascii, top3_ascii, daily_ascii



