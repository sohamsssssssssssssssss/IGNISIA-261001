from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel


class CounterfactualRecommendation(BaseModel):
    feature_key: str
    feature_name: str
    current_value: float
    current_value_display: str
    target_value: float
    target_value_display: str
    estimated_score_improvement: int
    confidence: Literal["high", "medium"]
    action: str
    timeframe_days: str


class SimulationResponse(BaseModel):
    gstin: str
    base_score: int
    combined_projected_score: int
    combined_score_improvement: int
    naive_sum_score_improvement: int
    recommendations: List[CounterfactualRecommendation]
