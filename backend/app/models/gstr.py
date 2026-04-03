from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date, datetime

class InvoiceItem(BaseModel):
    txval: float = Field(..., description="Taxable value")
    iamt: float = Field(0.0, description="IGST amount")
    camt: float = Field(0.0, description="CGST amount")
    samt: float = Field(0.0, description="SGST amount")
    rt: float = Field(..., description="Rate of tax")

class Invoice(BaseModel):
    inum: str = Field(..., description="Invoice number")
    idt: str = Field(..., description="Invoice date (DD-MM-YYYY)")
    val: float = Field(..., description="Invoice value")
    itms: List[InvoiceItem]

class B2BData(BaseModel):
    ctin: str = Field(..., description="GSTIN of receiver/supplier")
    inv: List[Invoice]

class GSTR1(BaseModel):
    gstin: str
    fp: str = Field(..., description="Financial period MMYYYY")
    b2b: Optional[List[B2BData]] = []
    
class GSTR2A_B2B(BaseModel):
    ctin: str
    inv: List[Invoice]

class GSTR2A(BaseModel):
    gstin: str
    fp: str
    b2b: Optional[List[GSTR2A_B2B]] = []

class GSTR3B_ITC_Details(BaseModel):
    iamt: float = 0.0
    camt: float = 0.0
    samt: float = 0.0

class GSTR3B_ITC(BaseModel):
    itc_avl: List[GSTR3B_ITC_Details] = Field(default_factory=list, description="ITC Available")

class GSTR3B(BaseModel):
    gstin: str
    ret_period: str = Field(..., description="Return period MMYYYY")
    filling_date: Optional[str] = Field(None, description="Date of filing")
    itc_elg: Optional[GSTR3B_ITC] = None
    
    @field_validator("filling_date")
    def validate_filling_date(cls, v):
        # We can implement late filing check per period internally or in service layer
        return v
