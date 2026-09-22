"""Shared profit estimates and deal scoring for Gold Deal Finder."""

DEFAULT_RECOVERY_RATE = 0.90
TARGET_PROFIT_DOLLARS = 500.0
TARGET_MARGIN_RATE = 0.50


def verification_multiplier(image_status="", text_status=""):
    image_status = str(image_status or "").strip().lower()
    text_status = str(text_status or "").strip().lower()
    if image_status == "image_gold_likely":
        return 1.00
    if image_status == "image_uncertain":
        return 0.75
    if image_status == "image_unverified":
        return 0.65
    if text_status == "text_checked":
        return 0.80
    return 0.60


def calculate_deal_metrics(theoretical_gold_value, total_price,
                           recovery_rate=DEFAULT_RECOVERY_RATE,
                           image_status="", text_status=""):
    """Return estimated resale, profit, margin and a 0-100 Deal Score."""
    theoretical_gold_value = max(float(theoretical_gold_value or 0), 0.0)
    total_price = max(float(total_price or 0), 0.0)
    recovery_rate = min(max(float(recovery_rate), 0.0), 1.0)
    estimated_resale_value = theoretical_gold_value * recovery_rate
    estimated_profit = estimated_resale_value - total_price
    profit_margin_pct = (
        (estimated_profit / total_price) * 100 if total_price > 0 else 0.0
    )

    if estimated_profit <= 0 or estimated_resale_value <= 0:
        deal_score = 0.0
    else:
        margin_rate = estimated_profit / estimated_resale_value
        margin_component = min(margin_rate / TARGET_MARGIN_RATE, 1.0) * 75
        profit_component = min(estimated_profit / TARGET_PROFIT_DOLLARS, 1.0) * 25
        deal_score = (margin_component + profit_component) * verification_multiplier(
            image_status, text_status
        )

    return {
        "recovery_rate": recovery_rate,
        "estimated_resale_value": estimated_resale_value,
        "estimated_profit": estimated_profit,
        "profit_margin_pct": profit_margin_pct,
        "deal_score": min(max(deal_score, 0.0), 100.0),
    }
