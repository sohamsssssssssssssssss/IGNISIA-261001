from pydantic import BaseModel, Field
from typing import Optional

class ScheduleBP(BaseModel):
    net_profit: float = Field(..., description="Net profit before tax")
    depreciation: float = Field(0.0, description="Depreciation allowed")
    
class ITR6(BaseModel):
    pan: str
    assessment_year: str
    gross_receipts: float = Field(..., description="Gross receipts from profession/business")
    schedule_bp: ScheduleBP

class Form26AS_TDS(BaseModel):
    deductor_tan: str
    amount_paid: float
    tds_deducted: float

class Form26AS(BaseModel):
    pan: str
    financial_year: str
    tds_entries: list[Form26AS_TDS]
