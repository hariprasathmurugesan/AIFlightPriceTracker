from twilio.rest import Client
from utils.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_SEGMENT_LENGTH = 160  # Twilio trial limit


def split_message(message: str, max_length: int = MAX_SEGMENT_LENGTH) -> list:
    """
    Splits a long message into multiple SMS-safe segments.
    """
    segments = []
    while message:
        segment = message[:max_length]
        segments.append(segment)
        message = message[max_length:]
    return segments


def send_sms(message: str):
    """
    Sends SMS in multiple segments with numbering (e.g., 1/3, 2/3).
    """

    # Debug print
    print("FULL SMS LENGTH:", len(message))
    print("FULL SMS BODY:", message)

    client = Client(Config.TWILIO_SID, Config.TWILIO_TOKEN)

    # Split into raw segments
    raw_segments = split_message(message)

    total = len(raw_segments)
    numbered_segments = []

    # Add numbering prefix to each segment
    for idx, seg in enumerate(raw_segments, start=1):
        prefix = f"{idx}/{total} "
        numbered_segments.append(prefix + seg)

    # Send each numbered segment
    for idx, segment in enumerate(numbered_segments, start=1):
        try:
            print(f"\n--- Sending segment {idx}/{total} ---")
            print("SEGMENT LENGTH:", len(segment))
            print("SEGMENT BODY:", segment)

            client.messages.create(
                body=segment,
                from_=Config.TWILIO_SMS_FROM,
                to=Config.TWILIO_SMS_TO
            )

            logger.info(f"SMS segment {idx}/{total} sent successfully.")

        except Exception as e:
            logger.error(f"Failed to send SMS segment {idx}: {e}")
