from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from ..core.gstin import is_valid_gstin, normalize_gstin
from ..core.security import require_role
from ..services.apriori_service import get_apriori_service


router = APIRouter(prefix="/api/insights", tags=["Behavioral Pattern Insights"])


def _filter_rules(
    rules: List[Dict[str, Any]],
    *,
    outcome: Optional[str],
    min_confidence: Optional[float],
    min_lift: Optional[float],
) -> List[Dict[str, Any]]:
    filtered = rules
    if outcome in {"repaid", "defaulted"}:
        filtered = [rule for rule in filtered if rule["consequent"] == outcome]
    if min_confidence is not None:
        filtered = [rule for rule in filtered if float(rule["confidence"]) >= min_confidence]
    if min_lift is not None:
        filtered = [rule for rule in filtered if float(rule["lift"]) >= min_lift]
    return sorted(filtered, key=lambda rule: (-float(rule["lift"]), -float(rule["confidence"])))


@router.get("/rules")
async def get_behavioral_rules(
    outcome: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_lift: Optional[float] = Query(None, ge=0.0),
    force_refresh: bool = Query(False),
    _: Any = Depends(require_role("viewer")),
) -> Dict[str, Any]:
    service = get_apriori_service()
    rules = service.get_rules(force_refresh=force_refresh)
    filtered = _filter_rules(
        rules,
        outcome=outcome,
        min_confidence=min_confidence,
        min_lift=min_lift,
    )
    has_rules = len(filtered) > 0
    minimum = service.has_minimum_records()
    status = "ok" if has_rules else (
        "Not enough historical data to mine patterns yet. Patterns will appear once more scored businesses have outcomes recorded."
        if not minimum else "No behavioral patterns matched the current filters."
    )
    return {
        "status": status,
        "rules": filtered,
        "metadata": {
            "assessment_count": service.storage.count_assessments(),
            "outcome_labeled_count": service.storage.count_outcome_labeled_records(),
            "outcome_labeled_gstins": service.storage.count_distinct_outcome_labeled_gstins(),
            "required_assessments": 50,
            "last_updated": service.get_cache_metadata().get("generated_at"),
            "not_enough_data": not minimum,
        },
    }


@router.get("/rules/match")
async def get_matching_behavioral_rules(
    gstin: str = Query(...),
    outcome: Optional[str] = Query(None),
    top_n: int = Query(2, ge=1, le=5),
    _: Any = Depends(require_role("viewer")),
) -> Dict[str, Any]:
    normalized_gstin = normalize_gstin(gstin)
    if not is_valid_gstin(normalized_gstin):
        return {
            "status": "Invalid GSTIN format",
            "rules": [],
        }
    rules = get_apriori_service().get_matching_rules_for_gstin(
        normalized_gstin,
        outcome=outcome,
        top_n=top_n,
    )
    return {
        "status": "ok" if rules else "No historical patterns available for this business yet.",
        "rules": rules,
    }
