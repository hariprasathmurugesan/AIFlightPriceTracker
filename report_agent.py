from core.processor import build_full_report

def run_report_agent(best_days_raw: dict, overall_raw: list, daily_raw: dict) -> str:
    """
    Build full ASCII report from analyzed flight data.
    Returns: Formatted report string
    """
    return build_full_report(best_days_raw, overall_raw, daily_raw)
