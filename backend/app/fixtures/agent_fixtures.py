"""
Pre-baked fixture responses for all agents.
Keyed by borrower scenario (reject = Arjun Textiles, approve = CleanTech Manufacturing).
"""

MCA_FIXTURES = {
    "reject": {
        "company_name": "Arjun Textiles Pvt. Ltd.",
        "directors": [
            {"name": "Arjun Singhania", "din": "07823456", "connected_entities": 4},
            {"name": "Rajesh Singhania", "din": "08934567", "connected_entities": 2},
        ],
        "shell_company_risk": True,
        "total_din_connections": 6,
        "source_status": "cached",
        "last_synced": "2025-12-15T10:30:00Z",
    },
    "approve": {
        "company_name": "CleanTech Manufacturing Ltd.",
        "directors": [
            {"name": "Vikram Mehta", "din": "06712345", "connected_entities": 1},
        ],
        "shell_company_risk": False,
        "total_din_connections": 1,
        "source_status": "cached",
        "last_synced": "2025-12-15T10:30:00Z",
    },
}

LITIGATION_FIXTURES = {
    "reject": {
        "entity": "Arjun Textiles Pvt. Ltd.",
        "active_cases": 1,
        "drt_cases": 1,
        "disputed_amount": 4_500_000,
        "drts_flag": True,
        "case_details": [
            {
                "case_number": "DRT/MUM/2024/1847",
                "court": "DRT Mumbai",
                "status": "Pending",
                "filed_date": "2024-03-15",
                "disputed_amount": 4_500_000,
                "respondent": "Arjun Textiles Pvt. Ltd.",
            }
        ],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:00:00Z",
    },
    "approve": {
        "entity": "CleanTech Manufacturing Ltd.",
        "active_cases": 0,
        "drt_cases": 0,
        "disputed_amount": 0,
        "drts_flag": False,
        "case_details": [],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:00:00Z",
    },
}

RBI_WATCHLIST_FIXTURES = {
    "reject": {
        "on_watchlist": False,
        "checked_promoters": ["Arjun Singhania", "Rajesh Singhania"],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:15:00Z",
    },
    "approve": {
        "on_watchlist": False,
        "checked_promoters": ["Vikram Mehta"],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:15:00Z",
    },
}

NEWS_FIXTURES = {
    "reject": {
        "entity": "Arjun Textiles Pvt. Ltd.",
        "sentiment_score": -0.5,
        "negative_news_flag": True,
        "articles": [
            {
                "title": "Arjun Textiles faces labour dispute at Surat unit",
                "source": "Economic Times",
                "date": "2025-02-10",
                "sentiment": "negative",
            },
            {
                "title": "Textile sector grapples with rising cotton prices",
                "source": "Business Standard",
                "date": "2025-01-22",
                "sentiment": "neutral",
            },
        ],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:30:00Z",
    },
    "approve": {
        "entity": "CleanTech Manufacturing Ltd.",
        "sentiment_score": 0.8,
        "negative_news_flag": False,
        "articles": [
            {
                "title": "CleanTech Manufacturing wins Rs 8 Cr defence order",
                "source": "Mint",
                "date": "2025-03-05",
                "sentiment": "positive",
            },
            {
                "title": "CNC automation sector sees 14% growth in FY24",
                "source": "Financial Express",
                "date": "2025-01-18",
                "sentiment": "positive",
            },
        ],
        "source_status": "cached",
        "last_synced": "2025-12-15T11:30:00Z",
    },
}


def get_scenario_key(entity_name: str) -> str:
    """Determine which fixture scenario to use based on entity name."""
    name_lower = entity_name.lower()
    if "arjun" in name_lower or "textile" in name_lower:
        return "reject"
    elif "cleantech" in name_lower or "vikram" in name_lower:
        return "approve"
    # Default to approve for unknown entities
    return "approve"
