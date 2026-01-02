import requests
from utils.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


def format_slack_message(flights):
    """
    Creates a Slack-friendly summary with bold text and emojis.
    """

    if not flights:
        return ":warning: No flights found that match your criteria."

    flights = sorted(flights, key=lambda f: float(f["price"]))
    best = flights[0]

    message = (
        f":airplane: *Best Flight Found!*\n"
        f"*Airline:* {best['airline']}\n"
        f"*Price:* CAD {best['price']}\n"
        f"*Duration:* {best['duration']}\n"
        f"*Stops:* {best['stops']}\n"
        f"*Layover:* {best['layover_city']} — {round(best['layover_hours'], 1)}h\n"
        f"*Departure:* {best['departure']}\n"
        f"*Arrival:* {best['arrival']}\n"
        "------------------------------\n"
        "*Top 3 Options:*"
    )

    for idx, f in enumerate(flights[:3], start=1):
        message += (
            f"\n• *Option {idx}:* {f['airline']} — CAD {f['price']} "
            f"({f['duration']}, {f['stops']} stop, layover {round(f['layover_hours'], 1)}h)"
        )

    return message


def send_slack(message):
    """
    Sends a formatted message to Slack.
    """
    try:
        response = requests.post(Config.SLACK_WEBHOOK_URL, json={"text": message})
        if response.status_code != 200:
            logger.error(f"Slack error: {response.text}")
    except Exception as e:
        logger.error(f"Slack send failed: {e}")
