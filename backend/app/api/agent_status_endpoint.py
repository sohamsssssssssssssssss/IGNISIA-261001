"""
Agent status and analyst override endpoints.
Provides source status badges (live/cached/fallback) and HITL override capabilities.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from ..core.security import require_role
from ..core.storage import get_storage
from ..fixtures.demo_config import is_demo_mode
from ..agents.mca_agent import MCAAgent
from ..agents.litigation_agent import LitigationAgent, RBIWatchlistAgent
from ..agents.news_agent import NewsAgent

router = APIRouter(prefix="/api", tags=["Agent Status & Overrides"])


@router.get("/agent-status/{company_name}")
async def get_agent_status(
    company_name: str,
    _: Any = Depends(require_role("viewer")),
) -> Dict[str, Any]:
    """
    Run all agents and return their results with source status badges.
    Each agent response includes source_status: live | cached | fallback
    """
    mca = MCAAgent()
    litigation = LitigationAgent()
    rbi = RBIWatchlistAgent()
    news = NewsAgent()

    mca_result = mca.run_mca_check(company_name)
    lit_result = litigation.check_ecourts(company_name)
    rbi_result = rbi.check_rbi_defaulters([company_name])
    news_result = news.get_news_sentiment(company_name)

    return {
        "demo_mode": is_demo_mode(),
        "agents": {
            "mca": {
                "data": mca_result,
                "source_status": mca_result.get("source_status", "unknown"),
                "last_synced": mca_result.get("last_synced"),
            },
            "ecourts": {
                "data": lit_result,
                "source_status": lit_result.get("source_status", "unknown"),
                "last_synced": lit_result.get("last_synced"),
            },
            "rbi_watchlist": {
                "data": rbi_result,
                "source_status": rbi_result.get("source_status", "unknown"),
                "last_synced": rbi_result.get("last_synced"),
            },
            "news": {
                "data": news_result,
                "source_status": news_result.get("source_status", "unknown"),
                "last_synced": news_result.get("last_synced"),
            },
        },
    }


class AnalystOverride(BaseModel):
    """Analyst override request for a concept score."""
    concept: str
    original_score: float
    adjusted_score: float
    reason: str
    action: str = "ADJUST"  # ADJUST | FLAG_NA | APPROVE | SEND_BACK | ESCALATE


class AnalystReviewRequest(BaseModel):
    """Full analyst review submission."""
    session_id: str
    company_name: str
    original_score: float
    overrides: list[AnalystOverride] = []
    management_quality: Optional[int] = None
    factory_utilization: Optional[float] = None
    field_notes: Optional[str] = None
    action: str = "APPROVE"  # APPROVE | SEND_BACK | ESCALATE


@router.post("/analyst/review")
async def submit_analyst_review(
    review: AnalystReviewRequest,
    _: Any = Depends(require_role("analyst")),
) -> Dict[str, Any]:
    """
    Submit analyst review with concept overrides.
    Records audit trail and recalculates adjusted score.
    """
    # Calculate score adjustments
    total_adjustment = 0.0
    override_details = []

    for override in review.overrides:
        delta = override.adjusted_score - override.original_score
        total_adjustment += delta
        override_details.append({
            "concept": override.concept,
            "original": override.original_score,
            "adjusted": override.adjusted_score,
            "delta": round(delta, 2),
            "reason": override.reason,
            "action": override.action,
        })

    # DD adjustments
    dd_adjustment = 0.0
    if review.management_quality is not None:
        dd_adjustment += (review.management_quality - 3) * 2.0  # Baseline 3
    if review.factory_utilization is not None:
        dd_adjustment += 1.0 if review.factory_utilization >= 60 else -2.0

    adjusted_score = round(review.original_score + total_adjustment + dd_adjustment, 1)
    adjusted_score = max(0, min(100, adjusted_score))

    # Determine if verdict changes
    original_verdict = "APPROVE" if review.original_score >= 60 else "REJECT"
    adjusted_verdict = "APPROVE" if adjusted_score >= 60 else "REJECT"

    # Record audit entry
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_id": review.session_id,
        "company_name": review.company_name,
        "analyst_action": review.action,
        "original_score": review.original_score,
        "adjusted_score": adjusted_score,
        "total_adjustment": round(total_adjustment + dd_adjustment, 2),
        "verdict_changed": original_verdict != adjusted_verdict,
        "original_verdict": original_verdict,
        "adjusted_verdict": adjusted_verdict,
        "overrides": override_details,
        "management_quality": review.management_quality,
        "factory_utilization": review.factory_utilization,
        "field_notes": review.field_notes,
    }
    get_storage().record_analyst_review(audit_entry)

    return {
        "status": "recorded",
        "audit_entry": audit_entry,
        "adjusted_score": adjusted_score,
        "adjusted_verdict": adjusted_verdict,
        "requires_branch_head_approval": abs(total_adjustment + dd_adjustment) > 10,
    }


@router.get("/analyst/audit-trail/{session_id}")
async def get_audit_trail(
    session_id: str,
    _: Any = Depends(require_role("analyst")),
) -> Dict[str, Any]:
    """Retrieve audit trail for a session."""
    entries = get_storage().get_analyst_reviews(session_id)
    return {"session_id": session_id, "entries": entries}
