from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date

class BankTransaction(BaseModel):
    date: date
    narration: str
    withdrawal: float = 0.0
    deposit: float = 0.0
    balance: float = 0.0

class BankStatement(BaseModel):
    bank_name: str
    account_number: str
    period_start: date
    period_end: date
    transactions: List[BankTransaction]

class BankSummary(BaseModel):
    total_credit: float = 0.0
    average_balance: float = 0.0
    nach_bounces: int = 0
    emi_payments: int = 0
