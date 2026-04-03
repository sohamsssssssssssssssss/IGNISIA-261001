from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class MonthProjection(BaseModel):
    month: int
    score: int
    actions: List[str]
    crosses_threshold: bool


class TopIssue(BaseModel):
    feature: str
    label: str
    shap_impact: float


class SimulationResponse(BaseModel):
    gstin: str
    base_score: int
    approval_threshold: int
    top_issues: List[TopIssue]
    trajectory: List[MonthProjection]
    crossed_threshold_month: Optional[int]
    final_eligible_amount: int
