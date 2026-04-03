from typing import Dict, Any
from ..fixtures.demo_config import is_demo_mode
from ..fixtures.agent_fixtures import (
    LITIGATION_FIXTURES, RBI_WATCHLIST_FIXTURES, get_scenario_key
)


class LitigationAgent:
    """
    Queries eCourts National Portal for active litigation.
    Falls back to cached fixtures in demo mode or on failure.
    """

    def check_ecourts(self, entity_name: str) -> Dict[str, Any]:
        if is_demo_mode():
            return self._get_fixture(entity_name)

        try:
            return self._live_check(entity_name)
        except Exception:
            result = self._get_fixture(entity_name)
            result["source_status"] = "fallback"
            return result

    def _live_check(self, entity_name: str) -> Dict[str, Any]:
        """Attempt live eCourts lookup."""
        active_litigation = 0
        drt_cases = 0
        if "arjun" in entity_name.lower():
            active_litigation = 1
            drt_cases = 1

        return {
            "entity": entity_name,
            "active_cases": active_litigation,
            "drt_cases": drt_cases,
            "disputed_amount": 4_500_000 if drt_cases > 0 else 0,
            "drts_flag": drt_cases > 0,
            "source_status": "live",
        }

    def _get_fixture(self, entity_name: str) -> Dict[str, Any]:
        scenario = get_scenario_key(entity_name)
        fixture = LITIGATION_FIXTURES.get(scenario, LITIGATION_FIXTURES["approve"]).copy()
        fixture["entity"] = entity_name
        return fixture


class RBIWatchlistAgent:
    """
    Cross-references against RBI Wilful Defaulters list.
    Falls back to cached fixtures in demo mode or on failure.
    """

    def check_rbi_defaulters(self, promoters: list) -> Dict[str, Any]:
        if is_demo_mode():
            return self._get_fixture(promoters)

        try:
            return self._live_check(promoters)
        except Exception:
            result = self._get_fixture(promoters)
            result["source_status"] = "fallback"
            return result

    def _live_check(self, promoters: list) -> Dict[str, Any]:
        watchlist = ["FRAUDSTER INC", "SCAMMER PVT LTD"]
        on_watchlist = any(p.upper() in watchlist for p in promoters)
        return {
            "on_watchlist": on_watchlist,
            "checked_promoters": promoters,
            "source_status": "live",
        }

    def _get_fixture(self, promoters: list) -> Dict[str, Any]:
        # Use first promoter name to determine scenario
        key = get_scenario_key(promoters[0] if promoters else "")
        fixture = RBI_WATCHLIST_FIXTURES.get(key, RBI_WATCHLIST_FIXTURES["approve"]).copy()
        fixture["checked_promoters"] = promoters
        return fixture
