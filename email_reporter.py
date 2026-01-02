import smtplib
from email.mime.text import MIMEText
from utils.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


def send_email(subject: str, body: str):
    """
    Sends an email with monospaced formatting to preserve ASCII table alignment.
    Supports multiple recipients via comma-separated EMAIL_TO.
    """

    # Convert comma-separated string → clean list of emails
    recipients = [
        email.strip()
        for email in Config.EMAIL_TO.replace("[", "").replace("]", "").replace('"', "").split(",")
        if email.strip()
    ]

    # Wrap body in <pre> with monospace font for perfect alignment
    html_body = f"<pre style='font-family: monospace'>{body}</pre>"

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = Config.EMAIL_FROM
    msg["To"] = ", ".join(recipients)  # Display only

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(Config.EMAIL_FROM, Config.EMAIL_APP_PASSWORD)
            server.sendmail(
                Config.EMAIL_FROM,
                recipients,  # MUST be a clean list
                msg.as_string()
            )

        logger.info(f"Email sent successfully to: {recipients}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
