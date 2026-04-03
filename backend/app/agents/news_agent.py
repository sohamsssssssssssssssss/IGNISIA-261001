import os
from typing import Dict, Any
from ..fixtures.demo_config import is_demo_mode
from ..fixtures.agent_fixtures import NEWS_FIXTURES, get_scenario_key


class NewsAgent:
    """
    Uses Tavily to search recent news and compute sentiment.
    Falls back to cached fixtures in demo mode or on failure.
    """

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")

    def get_news_sentiment(self, entity_name: str) -> Dict[str, Any]:
        if is_demo_mode():
            return self._get_fixture(entity_name)

        try:
            return self._live_check(entity_name)
        except Exception:
            result = self._get_fixture(entity_name)
            result["source_status"] = "fallback"
            return result

    def _live_check(self, entity_name: str) -> Dict[str, Any]:
        """Attempt live Tavily search."""
        from tavily import TavilyClient

        client = TavilyClient(api_key=self.api_key)
        response = client.search(
            query=f"{entity_name} financial fraud news",
            search_depth="basic",
        )

        negative_keywords = ['fraud', 'scam', 'default', 'arrest', 'raid', 'ED', 'CBI']
        negative_hits = 0

        for article in response.get("results", []):
            content = article.get("content", "").lower()
            if any(kw in content for kw in negative_keywords):
                negative_hits += 1

        score = max(-1.0, 1.0 - (negative_hits * 0.5))

        return {
            "entity": entity_name,
            "sentiment_score": score,
            "negative_news_flag": score < 0,
            "source_status": "live",
        }

    def _get_fixture(self, entity_name: str) -> Dict[str, Any]:
        scenario = get_scenario_key(entity_name)
        fixture = NEWS_FIXTURES.get(scenario, NEWS_FIXTURES["approve"]).copy()
        fixture["entity"] = entity_name
        return fixture
