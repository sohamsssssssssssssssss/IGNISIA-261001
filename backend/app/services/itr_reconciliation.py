from app.models.itr import ITR6, Form26AS
from typing import Dict, Any

class ITRReconciliationService:
    @staticmethod
    def cross_validate_26as_vs_itr(itr: ITR6, form26: Form26AS) -> Dict[str, Any]:
        """
        Cross-validates TDS credits against ITR-6 Schedule BP/Gross Receipts.
        Mismatch > 20% feeds the 26as_mismatch concept node.
        """
        total_26as_amount = sum(e.amount_paid for e in form26.tds_entries)
        gross_receipts = itr.gross_receipts
        
        if gross_receipts == 0:
            variance = 1.0 if total_26as_amount > 0 else 0.0
        else:
            variance = abs(total_26as_amount - gross_receipts) / gross_receipts
            
        mismatch_pct = variance * 100
        flag = None
        if mismatch_pct > 20:
            flag = "26AS_MISMATCH (HIGH)"
            
        return {
            "gross_receipts": gross_receipts,
            "total_26as_amount": total_26as_amount,
            "mismatch_pct": mismatch_pct,
            "flag": flag,
            "concept_node_update": {
                "26as_mismatch": 1.0 if flag else 0.0
            }
        }
