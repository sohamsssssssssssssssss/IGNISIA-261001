from __future__ import annotations

MIN_OUTCOME_LABELED_RECORDS = 50
APRIORI_MIN_SUPPORT = 0.1
APRIORI_MIN_CONFIDENCE = 0.6
APRIORI_CACHE_TTL_SECONDS = 30 * 60
APRIORI_TOP_RULES_LIMIT = 30
APRIORI_SCHEDULER_INTERVAL_SECONDS = 60 * 60

MOCK_REPAY_HIGH_SCORE_THRESHOLD = 700
MOCK_REPAY_MID_SCORE_THRESHOLD = 500
MOCK_REPAY_HIGH_SCORE_PROBABILITY = 0.85
MOCK_REPAY_MID_SCORE_PROBABILITY = 0.60
MOCK_REPAY_LOW_SCORE_PROBABILITY = 0.25

GST_HIGH_THRESHOLD = 0.80
GST_LOW_THRESHOLD = 0.50

UPI_REGULAR_THRESHOLD = 0.70
UPI_IRREGULAR_THRESHOLD = 0.40

BUSINESS_NEW_THRESHOLD_MONTHS = 6
BUSINESS_MATURE_THRESHOLD_MONTHS = 18

EWB_HIGH_ACTIVITY_THRESHOLD = 25.0

CREDIT_HIGH_SCORE_THRESHOLD = 700
CREDIT_MEDIUM_SCORE_THRESHOLD = 500

ITEM_DESCRIPTION_MAP = {
    "high_gst_compliance": "file GST consistently",
    "medium_gst_compliance": "maintain moderate GST compliance",
    "low_gst_compliance": "struggle with GST compliance",
    "regular_upi_cadence": "show regular UPI transaction cadence",
    "moderate_upi_cadence": "show moderately regular UPI transaction cadence",
    "irregular_upi_cadence": "show irregular UPI transaction cadence",
    "mature_business": "have over 18 months of operating history",
    "established_business": "have between 6 and 18 months of operating history",
    "new_business": "are under 6 months old",
    "fraud_flagged": "carry fraud warning signals",
    "clean_profile": "show a clean fraud profile",
    "high_ewb_activity": "show strong e-way bill activity",
    "low_ewb_activity": "show limited e-way bill activity",
    "high_score": "have strong credit scores",
    "medium_score": "have mid-range credit scores",
    "low_score": "have weak credit scores",
}
