from reporting.slack_reporter import send_slack
from reporting.email_reporter import send_email
from reporting.sms_reporter import send_sms
from agents.llm_summarizer import summarize_for_sms
from agents.llm_insights import generate_travel_insights


def notify(report: str, channels: list, best_day: str, top3: str, daily: str):
    """
    Unified notification handler for Slack, Email, SMS.
    """

    # Generate insights once
    insights = generate_travel_insights(best_day, top3, daily)

    # Slack → Insights + full report
    if "slack" in channels:
        slack_message = insights + "\n\n" + report
        send_slack(slack_message)

    # Email → Insights + full report
    if "email" in channels:
        email_body = insights + "\n\n" + report
        send_email("Flight Tracker Report", email_body)

    # SMS → Short LLM summary
    if "sms" in channels:
        sms_summary = summarize_for_sms(best_day, top3)
        send_sms(sms_summary)
