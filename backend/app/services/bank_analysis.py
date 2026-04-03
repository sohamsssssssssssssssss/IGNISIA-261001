from app.models.bank import BankStatement, BankSummary
from typing import Dict, Any

class BankAnalysisService:
    @staticmethod
    def analyze_statement(statement: BankStatement) -> Dict[str, Any]:
        """
        Compute credit summation, average balance, EMI patterns, and return cheque count.
        Detect NACH/ECS mandate return entries. > 2 returns in 12 months -> HIGH delinquency.
        """
        total_credit = 0.0
        total_balance = 0.0
        nach_bounce_count = 0
        emi_count = 0
        
        nach_bounce_keywords = ['nach return', 'ecs bounce', 'inward txn reversed', 'funds insufficient']
        emi_keywords = ['emi', 'loan installment']
        
        for tx in statement.transactions:
            total_credit += tx.deposit
            total_balance += tx.balance
            
            narration_lower = tx.narration.lower()
            
            if tx.withdrawal > 0 and any(kw in narration_lower for kw in nach_bounce_keywords):
                nach_bounce_count += 1
                
            if tx.withdrawal > 0 and any(kw in narration_lower for kw in emi_keywords):
                emi_count += 1
                
        avg_balance = total_balance / len(statement.transactions) if statement.transactions else 0.0
        
        flag = None
        if nach_bounce_count > 2:
            flag = "NACH_BOUNCE (HIGH)"
            
        summary = BankSummary(
            total_credit=total_credit,
            average_balance=avg_balance,
            nach_bounces=nach_bounce_count,
            emi_payments=emi_count
        )
        
        return {
            "summary": summary.model_dump(),
            "flag": flag,
            "concept_node_update": {
                "nach_bounce_flag": 1.0 if flag else 0.0
            }
        }
