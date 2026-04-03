"""
FastAPI endpoint for the RAG pipeline.
Accepts multipart form data with borrower documents and runs the full 3-level pipeline.
"""

from fastapi import APIRouter, UploadFile, File, Form
import tempfile, shutil, json
from ..rag.pipeline import RAGPipeline

router = APIRouter(prefix="/rag", tags=["RAG Pipeline"])


@router.post("/run")
async def run_rag_pipeline(
    company_name:    str = Form(...),
    promoter_name:   str = Form(...),
    industry:        str = Form(...),
    gstin:           str = Form(...),
    gstr3b:          UploadFile = File(...),
    gstr2a:          UploadFile = File(...),
    annual_report:   UploadFile = File(...),
    bank_statement:  UploadFile = File(...),
    alm:             UploadFile = File(None),
    shareholding:    UploadFile = File(None),
    borrowing_profile: UploadFile = File(None),
    portfolio_cuts:  UploadFile = File(None),
):
    pipeline = RAGPipeline(company_name, promoter_name, industry, gstin)

    gstr3b_data = json.loads(await gstr3b.read())
    gstr2a_data = json.loads(await gstr2a.read())

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_tmp:
        shutil.copyfileobj(annual_report.file, pdf_tmp)
        pdf_path = pdf_tmp.name

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as csv_tmp:
        shutil.copyfileobj(bank_statement.file, csv_tmp)
        csv_path = csv_tmp.name

    # Save optional files
    alm_path = None
    if alm:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            shutil.copyfileobj(alm.file, tmp)
            alm_path = tmp.name

    sh_path = None
    if shareholding:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            shutil.copyfileobj(shareholding.file, tmp)
            sh_path = tmp.name

    bp_path = None
    if borrowing_profile:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            shutil.copyfileobj(borrowing_profile.file, tmp)
            bp_path = tmp.name

    port_path = None
    if portfolio_cuts:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            shutil.copyfileobj(portfolio_cuts.file, tmp)
            port_path = tmp.name

    result = pipeline.run_full(
        gstr3b_data, gstr2a_data, pdf_path, csv_path,
        alm_csv=alm_path,
        shareholding_csv=sh_path,
        borrowing_csv=bp_path,
        portfolio_csv=port_path,
    )

    response_payload = {
        "chunks_indexed": result.chunks_indexed,
        "overall_contradiction_risk": result.contradiction_report.overall_risk,
        "primary_contradiction": result.contradiction_report.primary_driver,
        "contradictions": [vars(c) for c in result.contradiction_report.contradictions],
        "litigation_found": result.web_intel_report.litigation_found,
        "adverse_media": result.web_intel_report.adverse_media,
        "rbi_watchlist_hit": result.web_intel_report.rbi_watchlist_hit,
        "web_findings": result.web_intel_report.key_findings,
        "cam_sections": {
            k: {
                "answer": v.answer,
                "confidence": v.confidence,
                "provenance": v.provenance_trail
            }
            for k, v in result.cam_sections.items()
        },
        "concept_narratives": {
            k.capitalize(): v.answer for k, v in result.cam_sections.items()
        },
        "concept_flags": {
            "Character": (
                f"Active litigation found: {result.web_intel_report.key_findings}" 
                if result.web_intel_report.litigation_found else None
            ),
            "Capacity": (
                f"Contradiction: {result.contradiction_report.primary_driver}" 
                if result.contradiction_report.primary_driver else None
            ),
            "Capital": None,
            "Collateral": None,
            "Conditions": (
                f"Adverse Media/Watchlist: RBI Hit? {result.web_intel_report.rbi_watchlist_hit}"
                if result.web_intel_report.adverse_media or result.web_intel_report.rbi_watchlist_hit else None
            )
        }
    }

    # Clean up empty flags
    response_payload["concept_flags"] = {k: v for k, v in response_payload["concept_flags"].items() if v}
    return response_payload
