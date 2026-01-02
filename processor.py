from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import os

# ============================================================
# DATA MODELS (for ASCII tables)
# ============================================================

@dataclass
class FlightOption:
    option_number: int
    airline: str
    price: float
    duration: str
    stops: int
    layover_city: str
    layover_hours: float
    departure: str
    arrival: str


@dataclass
class DayFlights:
    date: str
    options: List[FlightOption]


@dataclass
class BestDayCategory:
    category: str
    date: str
    price: float
    airline: str
    layover_city: str
    layover_hours: float


@dataclass
class OverallBestDay:
    date: str
    score: float
    price: float
    airline: str
    duration: str
    layover_city: str
    layover_hours: float


# ============================================================
# CONSTANTS / CONFIG
# ============================================================

PRICE_HISTORY_FILE = "price_history.json"
EXCLUDED_AIRLINES = {"CX", "AI"}  # Cathay Pacific, Air India


# ============================================================
# LOW-LEVEL UTILS
# ============================================================

def _pad(text: str, width: int, align: str = "left") -> str:
    """
    Pad text to a given width with alignment.
    """
    if len(text) > width:
        return text[:width]
    if align == "right":
        return text.rjust(width)
    if align == "center":
        return text.center(width)
    return text.ljust(width)


def render_ascii_block(table: str) -> str:
    """
    Wraps an ASCII table in triple backticks for monospace rendering.
    Useful for Slack, Markdown, and email formatting.
    """
    return f"```\n{table}\n```"


def auto_column_widths(headers: List[str], rows: List[List[Any]], padding: int = 2) -> List[int]:
    """
    Calculates column widths based on the longest value in each column.
    Adds optional padding to each column.
    """
    num_cols = len(headers)
    max_lengths = [len(h) for h in headers]

    for row in rows:
        for i in range(num_cols):
            if i < len(row):
                max_lengths[i] = max(max_lengths[i], len(str(row[i])))

    return [length + padding for length in max_lengths]

def build_etihad_table(etihad_rows):
    if not etihad_rows:
        return "No Etihad flights found for this date range."

    header = ["DATE", "PRICE", "DURATION", "LAYOVER"]
    rows = [
        [
            r["date"],
            f"${r['price']}",
            r["duration"],
            r["layover"]
        ]
        for r in etihad_rows
    ]

    return build_table(header, rows, title="Etihad Airways — March 20 to March 31")

def make_table(headers: List[str], rows: List[List[Any]], widths: List[int], aligns: Optional[List[str]] = None) -> str:
    """
    Build a generic ASCII table with headers, rows, and column widths.
    """
    if aligns is None:
        aligns = ["left"] * len(headers)

    def format_row(row: List[Any]) -> str:
        return "| " + " | ".join(
            _pad(str(cell), widths[i], aligns[i]) for i, cell in enumerate(row)
        ) + " |"

    border = "+-" + "-+-".join("-" * w for w in widths) + "-+"

    lines = [border, format_row(headers), border]
    for row in rows:
        lines.append(format_row(row))
    lines.append(border)

    return "\n".join(lines)


def parse_duration_to_minutes(duration_str: str) -> int:
    """
    Converts '22h 30m' → 1350 minutes.
    """
    hours = 0
    minutes = 0

    parts = duration_str.lower().replace(" ", "")
    if "h" in parts:
        h = parts.split("h")[0]
        if h:
            hours = int(h)
        parts = parts.split("h")[1]
    if "m" in parts:
        m = parts.split("m")[0]
        if m:
            minutes = int(m)

    return hours * 60 + minutes


# ============================================================
# PRICE HISTORY / DROP DETECTION
# ============================================================

def _load_price_history() -> Dict[str, float]:
    if not os.path.exists(PRICE_HISTORY_FILE):
        return {}
    try:
        with open(PRICE_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_price_history(history: Dict[str, float]) -> None:
    with open(PRICE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f)


def detect_price_drop(date_str: str, current_price: float) -> Optional[str]:
    """
    Simple file-based price drop detection.
    Stores the last seen price per date and compares.
    """
    history = _load_price_history()
    prev_price = history.get(date_str)

    history[date_str] = float(current_price)
    _save_price_history(history)

    if prev_price is None:
        return None

    prev_price = float(prev_price)
    current_price = float(current_price)

    if current_price < prev_price:
        diff = prev_price - current_price
        return f"🔥 Price drop on {date_str}: was ${prev_price:.2f}, now ${current_price:.2f} (↓ ${diff:.2f})"

    return None


# ============================================================
# CORE BUSINESS LOGIC (COMPUTE BEST DAYS)
# ============================================================

def extract_flights(raw: Dict[str, Any], carrier_lookup: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Extracts normalized flight data from Amadeus flight-offer response.
    """
    if not raw or "data" not in raw:
        return []

    flights: List[Dict[str, Any]] = []

    for offer in raw["data"]:
        try:
            itineraries = offer.get("itineraries", [])
            if not itineraries:
                continue

            # We only consider the first itinerary (outbound)
            itin = itineraries[0]
            segments = itin.get("segments", [])
            if not segments:
                continue

            # Airline = carrier of first segment
            airline_code = segments[0].get("carrierCode", "")
            airline_name = carrier_lookup.get(airline_code, "")
            airline = f"{airline_code} — {airline_name}" if airline_name else airline_code

            # Price
            price = float(offer["price"]["total"])

            # Total duration (PT17H50M → 17h 50m)
            duration_iso = itin.get("duration", "")
            duration = duration_iso.replace("PT", "").lower().replace("h", "h ").replace("m", "m")

            # Stops
            stops = len(segments) - 1

            # Layover city + hours
            layover_city = ""
            layover_hours = 0.0

            if len(segments) > 1:
                first_arrival = segments[0]["arrival"]["at"]
                second_departure = segments[1]["departure"]["at"]

                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%S"

                t1 = datetime.strptime(first_arrival, fmt)
                t2 = datetime.strptime(second_departure, fmt)

                layover_hours = round((t2 - t1).total_seconds() / 3600, 1)
                layover_city = segments[0]["arrival"]["iataCode"]

            # Departure / Arrival
            departure = segments[0]["departure"]["at"]
            arrival = segments[-1]["arrival"]["at"]

            flights.append({
                "airline": airline,
                "price": price,
                "duration": duration,
                "stops": stops,
                "layover_city": layover_city,
                "layover_hours": layover_hours,
                "departure": departure,
                "arrival": arrival,
            })

        except Exception as e:
            print("Error parsing flight:", e)
            continue

    return flights


def compute_best_day(all_days: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    all_days = [
        { "date": "2026-03-20", "flights": [...] },
        ...
    ]
    Returns structured summary + text_summary for Slack.
    """
    cheapest = None
    shortest_duration = None
    shortest_layover = None
    scored_flights: List[Dict[str, Any]] = []

    for day in all_days:
        date = day["date"]
        flights = day["flights"]
        if not flights:
            continue

        # Normalize and compute helpers
        norm_flights = []
        for f in flights:
            price_val = float(f["price"])
            layover_val = float(f["layover_hours"])
            duration_str = f["duration"]
            duration_val = parse_duration_to_minutes(duration_str)

            norm_flights.append({
                **f,
                "price_val": price_val,
                "layover_val": layover_val,
                "duration_val": duration_val,
            })

        # Cheapest
        flights_sorted_price = sorted(norm_flights, key=lambda x: x["price_val"])
        cheapest_flight = flights_sorted_price[0]
        if cheapest is None or cheapest_flight["price_val"] < cheapest["price"]:
            cheapest = {
                "date": date,
                "price": cheapest_flight["price_val"],
                "airline": cheapest_flight["airline"],
                "layover_city": cheapest_flight["layover_city"],
                "layover_hours": cheapest_flight["layover_val"],
            }

        # Shortest duration
        flights_sorted_duration = sorted(norm_flights, key=lambda x: x["duration_val"])
        shortest_duration_flight = flights_sorted_duration[0]
        shortest_duration_minutes = shortest_duration_flight["duration_val"]

        if (
            shortest_duration is None
            or shortest_duration_minutes < shortest_duration["duration_minutes"]
        ):
            shortest_duration = {
                "date": date,
                "price": shortest_duration_flight["price_val"],
                "airline": shortest_duration_flight["airline"],
                "duration": shortest_duration_flight["duration"],
                "duration_minutes": shortest_duration_minutes,
                "layover_city": shortest_duration_flight["layover_city"],
                "layover_hours": shortest_duration_flight["layover_val"],
            }

        # Shortest layover
        flights_sorted_layover = sorted(norm_flights, key=lambda x: x["layover_val"])
        shortest_layover_flight = flights_sorted_layover[0]
        if (
            shortest_layover is None
            or shortest_layover_flight["layover_val"] < shortest_layover["layover_hours"]
        ):
            shortest_layover = {
                "date": date,
                "price": shortest_layover_flight["price_val"],
                "airline": shortest_layover_flight["airline"],
                "layover_city": shortest_layover_flight["layover_city"],
                "layover_hours": shortest_layover_flight["layover_val"],
            }

        # Scoring for top 3 overall
        for f in norm_flights:
            score = (
                (f["price_val"] / 1000.0)
                + (f["duration_val"] / 1000.0)
                + (f["layover_val"] / 10.0)
            )
            scored_flights.append({
                "date": date,
                "score": score,
                "price": f["price_val"],
                "airline": f["airline"],
                "duration": f["duration"],
                "layover_city": f["layover_city"],
                "layover_hours": f["layover_val"],
            })

    top3_sorted = sorted(scored_flights, key=lambda x: x["score"])[:3]

    # Slack text summary
    text_summary_parts = []
    if cheapest:
        text_summary_parts.append(
            f"Cheapest Day: {cheapest['date']} — ${cheapest['price']:.2f}"
        )
    if shortest_duration:
        text_summary_parts.append(
            f"Shortest Duration: {shortest_duration['date']} — {shortest_duration['duration']}"
        )
    if shortest_layover:
        text_summary_parts.append(
            f"Shortest Layover: {shortest_layover['date']} — {shortest_layover['layover_hours']:.1f}h"
        )
    text_summary = "\n".join(text_summary_parts)

    return {
        "cheapest": cheapest,
        "shortest_duration": shortest_duration,
        "shortest_layover": shortest_layover,
        "top3_overall": top3_sorted,
        "text_summary": text_summary,
    }


# ============================================================
# PARSERS INTO DATA MODELS
# ============================================================

def parse_flight_option(option_number: int, raw: Dict[str, Any]) -> FlightOption:
    return FlightOption(
        option_number=option_number,
        airline=str(raw.get("airline", "")),
        price=float(raw.get("price", 0.0)),
        duration=str(raw.get("duration", "")),
        stops=int(raw.get("stops", 1)),
        layover_city=str(raw.get("layover_city", "")),
        layover_hours=float(raw.get("layover_hours", 0.0)),
        departure=str(raw.get("departure", "")),
        arrival=str(raw.get("arrival", "")),
    )


def parse_day_flights(date: str, raw_options: List[Dict[str, Any]]) -> DayFlights:
    options: List[FlightOption] = []
    for idx, raw in enumerate(raw_options, start=1):
        options.append(parse_flight_option(idx, raw))
    return DayFlights(date=date, options=options)


def parse_best_day_category(raw: Dict[str, Any]) -> BestDayCategory:
    return BestDayCategory(
        category=raw.get("category", ""),
        date=raw.get("date", ""),
        price=float(raw.get("price", 0.0)),
        airline=raw.get("airline", ""),
        layover_city=raw.get("layover_city", ""),
        layover_hours=float(raw.get("layover_hours", 0.0)),
    )


def parse_overall_best_day(raw: Dict[str, Any]) -> OverallBestDay:
    return OverallBestDay(
        date=raw.get("date", ""),
        score=float(raw.get("score", 0.0)),
        price=float(raw.get("price", 0.0)),
        airline=raw.get("airline", ""),
        duration=raw.get("duration", ""),
        layover_city=raw.get("layover_city", ""),
        layover_hours=float(raw.get("layover_hours", 0.0)),
    )


def parse_best_overall_days(raw: List[Dict[str, Any]]) -> List[OverallBestDay]:
    """
    raw is a LIST of dicts (top3_overall from compute_best_day).
    """
    days: List[OverallBestDay] = []
    for entry in raw:
        days.append(parse_overall_best_day(entry))
    return days


# ============================================================
# ASCII TABLE BUILDERS
# ============================================================

def build_best_day_summary_table(categories: List[BestDayCategory]) -> str:
    headers = ["Category", "Date", "Price", "Airline", "Layover"]

    rows: List[List[Any]] = []
    for c in categories:
        layover_str = f"{c.layover_city} — {c.layover_hours:.1f}h"
        rows.append([
            c.category,
            c.date,
            f"{c.price:.2f}",
            c.airline,
            layover_str,
        ])

    widths = auto_column_widths(headers, rows)
    aligns = ["left", "left", "right", "left", "left"]

    return make_table(headers, rows, widths, aligns)


def build_top3_overall_table(overall_days: List[OverallBestDay]) -> str:
    headers = ["Date", "Score", "Price", "Airline", "Duration", "Layover Hours", "Layover City"]

    rows: List[List[Any]] = []
    for d in overall_days:
        rows.append([
            d.date,
            f"{d.score:.2f}",
            f"{d.price:.2f}",
            d.airline,
            d.duration,
            f"{d.layover_hours:.1f}h",
            d.layover_city,
        ])

    widths = auto_column_widths(headers, rows)
    aligns = ["left", "right", "right", "left", "left", "right", "left"]

    return make_table(headers, rows, widths, aligns)


def build_daily_flights_table(day_flights: DayFlights) -> str:
    headers = [
        "Option", "Airline", "Price", "Duration", "Stops",
        "Layover City", "Layover Hours", "Departure", "Arrival",
    ]

    filtered: List[FlightOption] = []
    for opt in day_flights.options:
        airline_code = opt.airline.split(" — ")[0]
        if airline_code not in EXCLUDED_AIRLINES:
            filtered.append(opt)

    options = filtered[:10]

    rows: List[List[Any]] = []
    for opt in options:
        rows.append([
            str(opt.option_number),
            opt.airline,
            f"{opt.price:.2f}",
            opt.duration,
            str(opt.stops),
            opt.layover_city,
            f"{opt.layover_hours:.1f}h",
            opt.departure,
            opt.arrival,
        ])

    widths = auto_column_widths(headers, rows)
    aligns = ["right", "left", "right", "left", "right", "left", "right", "left", "left"]

    table = make_table(headers, rows, widths, aligns)
    return f"📅 {day_flights.date}\n{table}"


# ============================================================
# SECTION BUILDERS
# ============================================================

def build_best_day_section(best_days_raw: Dict[str, Dict[str, Any]]) -> str:
    """
    Build the 'Best Day to Fly' summary section with an ASCII table.
    """
    categories: List[BestDayCategory] = []

    cheapest = best_days_raw.get("cheapest")
    if cheapest:
        c = cheapest.copy()
        c["category"] = "Cheapest Day"
        categories.append(parse_best_day_category(c))

    shortest_duration = best_days_raw.get("shortest_duration")
    if shortest_duration:
        c = shortest_duration.copy()
        c["category"] = "Shortest Duration"
        categories.append(parse_best_day_category(c))

    shortest_layover = best_days_raw.get("shortest_layover")
    if shortest_layover:
        c = shortest_layover.copy()
        c["category"] = "Shortest Layover"
        categories.append(parse_best_day_category(c))

    if not categories:
        return "No best-day summary available."

    table = build_best_day_summary_table(categories)
    return "🌟 BEST DAY TO FLY SUMMARY 🌟\n\n" + render_ascii_block(table)


def build_top3_overall_section(overall_days_raw: List[Dict[str, Any]]) -> str:
    """
    Build the 'Top 3 Best Overall Days' section with an ASCII table.
    overall_days_raw is a LIST of dicts (top3_overall from compute_best_day).
    """
    overall_days = parse_best_overall_days(overall_days_raw)

    if not overall_days:
        return "No top-3 overall days available."

    table = build_top3_overall_table(overall_days)
    return "🌍 TOP 3 BEST OVERALL DAYS 🌍\n\n" + render_ascii_block(table)


def build_daily_sections(daily_raw: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Build all daily sections (one table per date).
    """
    parts: List[str] = []
    for date in sorted(daily_raw.keys()):
        day_flights = parse_day_flights(date, daily_raw[date])
        parts.append(build_daily_flights_table(day_flights))
        parts.append("")
    return "\n".join(parts).rstrip()


def build_full_report(
    
    best_days_raw: Dict[str, Dict[str, Any]],
    overall_raw: List[Dict[str, Any]],
    daily_raw: Dict[str, List[Dict[str, Any]]],
) -> str:
    """
    Build the full report combining:
    - Best day summary
    - Top 3 overall days
    - Etihad-only table (NEW)
    - Daily flight options
    """

    sections: List[str] = []

    # --------------------------------------------------------
    # 1. Best Day Summary
    # --------------------------------------------------------
    best_section = build_best_day_section(best_days_raw)
    sections.append(best_section)
    sections.append("")

    # --------------------------------------------------------
    # 2. Top 3 Overall Days
    # --------------------------------------------------------
    overall_section = build_top3_overall_section(overall_raw)
    sections.append(overall_section)
    sections.append("")

    # --------------------------------------------------------
    # 3. NEW — Etihad-only table
    # --------------------------------------------------------
    # --------------------------------------------------------
# 3. NEW — Etihad-only table
# --------------------------------------------------------
    # --------------------------------------------------------
# 3. NEW — Etihad-only table
# --------------------------------------------------------
    # --------------------------------------------------------
# 3. NEW — Etihad-only table
# --------------------------------------------------------
    etihad_rows = []

    for date, flights in daily_raw.items():
        for f in flights:
            airline_name = f["airline"].lower()
            airline_name = airline_name.replace("—", "-").replace("–", "-")

            if "etihad" in airline_name:
                etihad_rows.append({
                    "date": date,
                    "price": f["price"],
                    "duration": f["duration"],
                    "layover_hours": f["layover_hours"],
                })

    print("DEBUG_ETIHAD_ROWS:", etihad_rows)  # TEMP DEBUG

    # --------------------------------------------------------
    # Sort Etihad rows by price (lowest first)
    # --------------------------------------------------------
    etihad_rows = sorted(etihad_rows, key=lambda r: r["price"])

    # --------------------------------------------------------
    # Build Etihad ASCII table inline
    # --------------------------------------------------------
    if etihad_rows:
        headers = ["Date", "Price", "Duration", "Layover"]
        rows = [
            [
                r["date"],
                f"{r['price']:.2f}",
                r["duration"],
                f"{r['layover_hours']:.1f}h",
            ]
            for r in etihad_rows
        ]

        widths = auto_column_widths(headers, rows)
        aligns = ["left", "right", "left", "right"]

        etihad_table = make_table(headers, rows, widths, aligns)
        etihad_section = "✈️ ETIHAD AIRWAYS — MARCH 20 TO MARCH 31\n\n" + render_ascii_block(etihad_table)
    else:
        etihad_section = "✈️ ETIHAD AIRWAYS — No flights found for this date range."

    sections.append(etihad_section)
    sections.append("")




    # --------------------------------------------------------
    # 4. Daily Sections
    # --------------------------------------------------------
    daily_section = build_daily_sections(daily_raw)
    sections.append(daily_section)

    return "\n".join(sections)

