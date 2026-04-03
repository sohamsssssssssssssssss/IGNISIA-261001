from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any

class BorrowerFeatureVector(BaseModel):
    # Unique identifier
    gstin: str
    pan: str
    
    # Financial indicators (approx 85 dims ultimately - truncating for prototype)
    gross_receipts: float = 0.0
    net_profit: float = 0.0
    depreciation: float = 0.0
    
    # GST / Return signals
    gstr_variance_pct_max: float = 0.0
    circular_trading_flag: int = 0  # 1 for True, 0 for False
    late_gst_filings_count: int = 0
    
    # Bank signals
    bank_avg_balance: float = 0.0
    bank_nach_bounces: int = 0
    bank_emi_count: int = 0
    
    # ITR / 26AS mismatch
    itr_26as_mismatch_flag: int = 0
    
    # MSME data
    msme_classification: str = "NON-MSME"
    
    # Network / Web data
    director_din_count_max: int = 0
    litigation_active_cases: int = 0
    rbi_watchlist_flag: int = 0
    news_sentiment_score_avg: float = 0.0
    
    # Concept Node Inputs (for Pillar 3 CBM Model)
    # The 22 concept nodes map between 0.0 and 1.0 mapped from these raw features
    concept_nodes: Dict[str, float] = Field(default_factory=dict)
    
    model_config = ConfigDict(extra='allow')
