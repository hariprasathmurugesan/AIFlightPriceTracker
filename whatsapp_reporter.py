from twilio.rest import Client
from utils.config import Config

def send_whatsapp_message(message: str):
    client = Client(Config.TWILIO_SID, Config.TWILIO_TOKEN)

    client.messages.create(
        body=message,
        from_=f"whatsapp:{Config.TWILIO_WHATSAPP_FROM}",
        to=f"whatsapp:{Config.TWILIO_WHATSAPP_TO}",
    )
