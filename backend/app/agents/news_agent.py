import os
from typing import Dict, Any
from ..fixtures.demo_config import is_demo_mode
from ..fixtures.agent_fixtures import NEWS_FIXTURES, get_scenario_key
from .source_utils import enrich_agent_result


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

        if not self.api_key:
            return enrich_agent_result(
                self._get_fixture(entity_name),
                source_name="tavily_news",
                source_status="unavailable",
                source_url="https://app.tavily.com/",
                confidence=0.0,
                error_message="TAVILY_API_KEY is not configured",
            )

        try:
            return self._live_check(entity_name)
        except Exception as exc:
            result = self._get_fixture(entity_name)
            result["source_status"] = "fallback"
            result["error_message"] = str(exc)
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

        return enrich_agent_result({
            "entity": entity_name,
            "sentiment_score": score,
            "negative_news_flag": score < 0,
            "articles": response.get("results", []),
        },
            source_name="tavily_news",
            source_status="live",
            source_url="https://app.tavily.com/",
            confidence=0.7,
            raw_payload=response,
        )

    def _get_fixture(self, entity_name: str) -> Dict[str, Any]:
        scenario = get_scenario_key(entity_name)
        fixture = NEWS_FIXTURES.get(scenario, NEWS_FIXTURES["approve"]).copy()
        fixture["entity"] = entity_name
        return enrich_agent_result(
            fixture,
            source_name="tavily_news",
            source_status=fixture.get("source_status", "cached"),
            source_url="https://app.tavily.com/",
            confidence=0.6,
        )
