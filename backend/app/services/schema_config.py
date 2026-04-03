"""
Dynamic Schema Configuration Service.
Allows analysts to define/modify extraction schemas per document type.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import copy


@dataclass
class FieldDef:
    name: str
    field_type: str     # "string", "number", "boolean", "date", "currency"
    required: bool
    description: str


DEFAULT_SCHEMAS: Dict[str, List[FieldDef]] = {
    "ALM": [
        FieldDef("maturity_bucket", "string", True, "Maturity time bucket label"),
        FieldDef("total_assets", "currency", True, "Total assets in this bucket (INR Lakhs)"),
        FieldDef("total_liabilities", "currency", True, "Total liabilities in this bucket (INR Lakhs)"),
        FieldDef("gap", "currency", True, "Assets minus Liabilities"),
        FieldDef("cumulative_gap", "currency", True, "Running cumulative gap"),
        FieldDef("interest_rate_risk", "string", False, "Risk classification: LOW/MODERATE/HIGH"),
        FieldDef("liquidity_coverage_ratio", "number", False, "LCR if available"),
    ],
    "SHAREHOLDING_PATTERN": [
        FieldDef("category", "string", True, "Shareholder category"),
        FieldDef("holding_pct", "number", True, "Percentage holding"),
        FieldDef("shares", "number", True, "Number of shares"),
        FieldDef("pledged_pct", "number", False, "Percentage of shares pledged"),
        FieldDef("promoter_holding", "number", True, "Total promoter group holding %"),
        FieldDef("fii_holding", "number", False, "Foreign Institutional Investor holding %"),
        FieldDef("dii_holding", "number", False, "Domestic Institutional Investor holding %"),
    ],
    "BORROWING_PROFILE": [
        FieldDef("lender", "string", True, "Name of lending institution"),
        FieldDef("facility_type", "string", True, "Type: Term Loan, CC/OD, LC, BG"),
        FieldDef("sanctioned_limit", "currency", True, "Sanctioned limit (INR)"),
        FieldDef("outstanding", "currency", True, "Current outstanding (INR)"),
        FieldDef("rate_of_interest", "number", False, "Interest rate %"),
        FieldDef("overdue_amount", "currency", False, "Overdue/arrears amount"),
        FieldDef("is_npa", "boolean", False, "NPA classification flag"),
        FieldDef("maturity_date", "date", False, "Facility maturity date"),
        FieldDef("security_details", "string", False, "Collateral/security description"),
    ],
    "ANNUAL_REPORT": [
        FieldDef("revenue", "currency", True, "Total revenue / turnover"),
        FieldDef("ebitda", "currency", True, "EBITDA"),
        FieldDef("pat", "currency", True, "Profit After Tax"),
        FieldDef("net_worth", "currency", True, "Net worth / shareholder equity"),
        FieldDef("total_debt", "currency", True, "Total borrowings"),
        FieldDef("current_ratio", "number", False, "Current ratio"),
        FieldDef("debt_equity", "number", False, "Debt-to-Equity ratio"),
        FieldDef("dscr", "number", False, "Debt Service Coverage Ratio"),
        FieldDef("cash_flow_operations", "currency", False, "Cash flow from operations"),
    ],
    "PORTFOLIO_CUTS": [
        FieldDef("segment", "string", True, "Product segment or vintage bucket"),
        FieldDef("aum", "currency", True, "Assets Under Management (INR)"),
        FieldDef("gross_npa_pct", "number", True, "Gross NPA percentage"),
        FieldDef("net_npa_pct", "number", False, "Net NPA percentage"),
        FieldDef("collection_efficiency", "number", False, "Collection efficiency %"),
        FieldDef("provision_coverage", "number", False, "Provision coverage ratio %"),
        FieldDef("write_off_amount", "currency", False, "Write-off amount"),
    ],
}


class SchemaManager:
    """
    Manages extraction schemas per document type.
    Uses in-memory storage for prototype. Production would use Redis/DB.
    """

    def __init__(self):
        self._schemas: Dict[str, List[FieldDef]] = copy.deepcopy(DEFAULT_SCHEMAS)

    def get_schema(self, doc_type: str) -> List[FieldDef]:
        """Returns the current schema for a document type."""
        if doc_type not in self._schemas:
            raise ValueError(f"Unknown document type: {doc_type}. Valid: {list(self._schemas.keys())}")
        return self._schemas[doc_type]

    def get_all_schemas(self) -> Dict[str, List[dict]]:
        """Returns all schemas as serializable dicts."""
        return {
            doc_type: [
                {"name": f.name, "type": f.field_type, "required": f.required, "description": f.description}
                for f in fields
            ]
            for doc_type, fields in self._schemas.items()
        }

    def update_schema(self, doc_type: str, fields: List[dict]) -> List[FieldDef]:
        """Replace the schema for a given doc type with new field definitions."""
        if doc_type not in self._schemas:
            raise ValueError(f"Unknown document type: {doc_type}")

        new_fields = [
            FieldDef(
                name=f["name"],
                field_type=f.get("type", "string"),
                required=f.get("required", False),
                description=f.get("description", ""),
            )
            for f in fields
        ]
        self._schemas[doc_type] = new_fields
        return new_fields

    def add_field(self, doc_type: str, field_def: dict) -> FieldDef:
        """Add a single field to a document type schema."""
        if doc_type not in self._schemas:
            raise ValueError(f"Unknown document type: {doc_type}")

        new_field = FieldDef(
            name=field_def["name"],
            field_type=field_def.get("type", "string"),
            required=field_def.get("required", False),
            description=field_def.get("description", ""),
        )
        self._schemas[doc_type].append(new_field)
        return new_field

    def remove_field(self, doc_type: str, field_name: str) -> bool:
        """Remove a field from a document type schema by name."""
        if doc_type not in self._schemas:
            raise ValueError(f"Unknown document type: {doc_type}")

        original_len = len(self._schemas[doc_type])
        self._schemas[doc_type] = [f for f in self._schemas[doc_type] if f.name != field_name]
        return len(self._schemas[doc_type]) < original_len

    def reset_schema(self, doc_type: str) -> List[FieldDef]:
        """Reset a schema back to default."""
        if doc_type not in DEFAULT_SCHEMAS:
            raise ValueError(f"Unknown document type: {doc_type}")
        self._schemas[doc_type] = copy.deepcopy(DEFAULT_SCHEMAS[doc_type])
        return self._schemas[doc_type]
