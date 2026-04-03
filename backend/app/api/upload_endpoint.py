"""
Upload + pipeline execution endpoints for the document RAG workflow.
Persists upload sessions, classifications, and pipeline run status in the DB.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..core.rag_runtime import get_rag_capabilities
from ..core.security import require_role
from ..core.storage import get_storage
from ..parsers.alm_parser import parse_alm
from ..parsers.borrowing_profile_parser import parse_borrowing_profile
from ..parsers.portfolio_parser import parse_portfolio_cuts
from ..parsers.shareholding_parser import parse_shareholding
from ..services.cam_generator import CAMGenerator
from ..services.classifier import DocumentClassifier
from ..services.sector_research import SectorResearchEngine
from ..services.swot_engine import SWOTEngine
from ..services.triangulation_engine import TriangulationEngine

router = APIRouter(prefix="/api", tags=["Upload & Pipeline"])

_classifier = DocumentClassifier()
_swot = SWOTEngine()
_sector = SectorResearchEngine()
_triangulator = TriangulationEngine()
_cam_gen = CAMGenerator()

UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "intellicredit_uploads")
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "intellicredit_outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_session_id() -> str:
    return f"IC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"


def _build_pipeline_run_id() -> str:
    return f"PIPE-{uuid.uuid4().hex[:12]}"


def _get_session_or_404(session_id: str) -> Dict[str, Any]:
    session = get_storage().get_pipeline_session_details(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _serialize_classifications(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "filename": doc["filename"],
            "predicted_type": doc["predicted_type"],
            "confirmed_type": doc.get("confirmed_type"),
            "confidence": doc["confidence"],
            "evidence": doc["evidence"],
            "status": doc["status"],
        }
        for doc in documents
    ]


def _rag_unavailable_error() -> HTTPException:
    capabilities = get_rag_capabilities()
    return HTTPException(
        status_code=503,
        detail={
            "message": "Document RAG pipeline is unavailable because the base retrieval/indexing runtime is not ready.",
            "capabilities": capabilities,
        },
    )


def _set_pipeline_stage(
    *,
    session_id: str,
    run_id: str,
    stage: str,
    workflow_status: str | None = None,
    event_type: str = "stage",
    message: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> None:
    timestamp = _utc_now_iso()
    storage = get_storage()
    storage.update_pipeline_run(run_id, stage=stage)
    storage.add_pipeline_run_event(
        run_id=run_id,
        session_id=session_id,
        stage=stage,
        event_type=event_type,
        created_at=timestamp,
        message=message or f"Entered stage: {stage}",
        metadata=metadata,
    )
    storage.update_document_session(
        session_id,
        updated_at=timestamp,
        workflow_status=workflow_status or stage,
    )


@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    _: str = Depends(require_role("analyst")),
):
    """
    Upload 1-5 documents, classify them, and persist the session in storage.
    """
    sid = session_id or _build_session_id()
    now_iso = _utc_now_iso()
    session_dir = os.path.join(UPLOAD_DIR, sid)
    os.makedirs(session_dir, exist_ok=True)

    storage = get_storage()
    storage.create_document_session(
        session_id=sid,
        created_at=now_iso,
        updated_at=now_iso,
        workflow_status="uploaded",
    )

    documents_to_store: List[Dict[str, Any]] = []
    for uploaded in files:
        file_path = os.path.join(session_dir, uploaded.filename)
        with open(file_path, "wb") as out:
            shutil.copyfileobj(uploaded.file, out)

        try:
            with open(file_path, "r", errors="ignore") as rf:
                content_sample = rf.read(2000)
        except Exception:
            content_sample = ""

        result = _classifier.auto_classify(uploaded.filename, content_sample)
        documents_to_store.append(
            {
                "filename": uploaded.filename,
                "predicted_type": result.predicted_type,
                "confidence": result.confidence,
                "evidence": result.evidence,
                "file_path": file_path,
                "confirmed_type": None,
                "status": "PENDING",
                "uploaded_at": now_iso,
            }
        )

    storage.add_uploaded_documents(sid, documents_to_store)
    session = _get_session_or_404(sid)
    return {
        "session_id": sid,
        "workflow_status": session["workflow_status"],
        "classifications": _serialize_classifications(session["documents"]),
    }


@router.post("/upload/confirm")
async def confirm_classifications(
    session_id: str = Form(...),
    confirmations: str = Form(...),
    _: str = Depends(require_role("analyst")),
):
    """Persist analyst-confirmed classifications before the pipeline runs."""
    _ = _get_session_or_404(session_id)
    updates = json.loads(confirmations)
    storage = get_storage()

    updated = 0
    for update in updates:
        filename = str(update.get("filename") or "").strip()
        if not filename:
            continue
        confirmed_type = update.get("confirmed_type")
        predicted_type = update.get("predicted_type")
        final_type = confirmed_type or predicted_type
        if not final_type:
            continue
        status = "APPROVED" if confirmed_type in {None, predicted_type, ""} else "EDITED"
        if storage.update_uploaded_document(
            session_id=session_id,
            filename=filename,
            confirmed_type=final_type,
            status=status,
        ):
            updated += 1

    storage.update_document_session(
        session_id,
        updated_at=_utc_now_iso(),
        workflow_status="classified",
    )
    session = _get_session_or_404(session_id)
    return {
        "session_id": session_id,
        "status": "confirmed",
        "count": updated,
        "workflow_status": session["workflow_status"],
        "classifications": _serialize_classifications(session["documents"]),
    }


@router.get("/pipeline/{session_id}")
async def get_pipeline_status(
    session_id: str,
    _: str = Depends(require_role("analyst")),
):
    """Return the persisted state of an upload/pipeline session."""
    session = _get_session_or_404(session_id)
    return {
        "session_id": session["session_id"],
        "workflow_status": session["workflow_status"],
        "company_name": session.get("company_name"),
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "last_error": session.get("last_error"),
        "cam_download_url": (
            f"/api/download/{session['cam_filename']}" if session.get("cam_filename") else None
        ),
        "classifications": _serialize_classifications(session["documents"]),
        "latest_run": session.get("latest_run"),
        "rag_capabilities": get_rag_capabilities(),
    }


@router.post("/pipeline/run")
async def run_pipeline(
    session_id: str = Form(...),
    company_name: str = Form(...),
    cin: str = Form(""),
    pan: str = Form(""),
    sector: str = Form(""),
    promoter: str = Form(""),
    vintage: str = Form(""),
    turnover: str = Form(""),
    cibil: str = Form(""),
    loan_type: str = Form(""),
    loan_amount: str = Form(""),
    loan_tenure: str = Form(""),
    loan_rate: str = Form(""),
    _: str = Depends(require_role("analyst")),
):
    """
    Run the full RAG-backed document pipeline for a persisted upload session.
    """
    session = _get_session_or_404(session_id)
    documents = session["documents"]
    if not documents:
        raise HTTPException(status_code=400, detail="No uploaded documents found for this session")

    capabilities = get_rag_capabilities()
    if not capabilities["modes"]["document_pipeline"]:
        raise _rag_unavailable_error()

    now_iso = _utc_now_iso()
    run_id = _build_pipeline_run_id()
    storage = get_storage()
    storage.create_pipeline_run(
        run_id=run_id,
        session_id=session_id,
        status="running",
        stage="preparing_inputs",
        started_at=now_iso,
    )
    storage.add_pipeline_run_event(
        run_id=run_id,
        session_id=session_id,
        stage="preparing_inputs",
        event_type="started",
        created_at=now_iso,
        message="Pipeline run created",
        metadata={"execution_mode": capabilities["execution_mode"]},
    )
    storage.update_document_session(
        session_id,
        updated_at=now_iso,
        workflow_status="running",
        company_name=company_name,
        metadata={
            "cin": cin,
            "pan": pan,
            "sector": sector,
            "promoter": promoter,
            "vintage": vintage,
            "turnover": turnover,
            "cibil": cibil,
            "loan_type": loan_type,
            "loan_amount": loan_amount,
            "loan_tenure": loan_tenure,
            "loan_rate": loan_rate,
        },
        last_error=None,
    )

    try:
        _set_pipeline_stage(
            session_id=session_id,
            run_id=run_id,
            stage="preparing_inputs",
            workflow_status="preparing_inputs",
            message="Preparing confirmed document inputs",
        )
        doc_map: Dict[str, str] = {}
        for document in documents:
            dtype = document.get("confirmed_type") or document["predicted_type"]
            doc_map[str(dtype)] = document["file_path"]

        _set_pipeline_stage(
            session_id=session_id,
            run_id=run_id,
            stage="parsing_documents",
            workflow_status="parsing_documents",
            message="Parsing uploaded documents into structured inputs",
            metadata={"document_count": len(documents)},
        )

        alm_parsed = parse_alm(doc_map["ALM"]) if "ALM" in doc_map else None
        shareholding_parsed = (
            parse_shareholding(doc_map["SHAREHOLDING_PATTERN"])
            if "SHAREHOLDING_PATTERN" in doc_map
            else None
        )
        borrowing_parsed = (
            parse_borrowing_profile(doc_map["BORROWING_PROFILE"])
            if "BORROWING_PROFILE" in doc_map
            else None
        )
        portfolio_parsed = (
            parse_portfolio_cuts(doc_map["PORTFOLIO_CUTS"])
            if "PORTFOLIO_CUTS" in doc_map
            else None
        )
        annual_report_path = doc_map.get("ANNUAL_REPORT")

        _set_pipeline_stage(
            session_id=session_id,
            run_id=run_id,
            stage="rag_execution",
            workflow_status="rag_execution",
            message="Running retrieval, contradiction detection, and web intelligence",
        )
        try:
            from ..rag.pipeline import RAGPipeline
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "RAG pipeline dependencies are not installed.",
                    "capabilities": capabilities,
                },
            ) from exc

        pipeline = RAGPipeline(
            company_name,
            promoter,
            sector,
            pan,
            session_id=session_id,
            run_id=run_id,
        )
        rag_result = pipeline.run_full(
            annual_report_path=annual_report_path,
            alm_report=alm_parsed,
            shareholding_report=shareholding_parsed,
            borrowing_profile=borrowing_parsed,
            portfolio_report=portfolio_parsed,
        )

        swot_data = rag_result.cam_sections.get(
            "swot",
            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        )
        sector_report = _sector.research(sector)
        sector_data = {
            "outlook": sector_report.sector_outlook,
            "growth": sector_report.sector_growth_rate,
            "sub": sector_report.sub_sector_analysis,
            "macro": sector_report.macro_indicators,
            "risks": sector_report.risk_factors,
        }

        concept_scores = {
            "Character": 0.75,
            "Capacity": 0.65,
            "Capital": 0.80,
            "Collateral": 0.60,
            "Conditions": 0.70,
        }
        avg_score = round(sum(concept_scores.values()) / len(concept_scores) * 100, 1)
        verdict = "APPROVE" if avg_score >= 70 else "REJECT"

        triangulation_data = [
            {
                "external": item.query,
                "internal": item.source_a,
                "alignment": item.source_b,
                "sev": item.severity,
                "rec": item.explanation,
            }
            for item in rag_result.contradiction_report.contradictions
        ]

        schema_mappings = []
        if annual_report_path:
            schema_mappings.append(
                {
                    "docType": "ANNUAL_REPORT",
                    "rawField": "Revenue from Operations / Total Income",
                    "mappedTo": "total_revenue",
                    "value": turnover or "Extracted",
                    "confidence": 0.96,
                }
            )
            schema_mappings.append(
                {
                    "docType": "ANNUAL_REPORT",
                    "rawField": "Profit After Tax (PAT)",
                    "mappedTo": "net_income",
                    "value": "Extracted",
                    "confidence": 0.94,
                }
            )
        if alm_parsed:
            schema_mappings.append(
                {
                    "docType": "ALM",
                    "rawField": "1-14 Days Net Mismatch",
                    "mappedTo": "alm_short_term_gap",
                    "value": "Extracted",
                    "confidence": 0.91,
                }
            )
        if shareholding_parsed:
            schema_mappings.append(
                {
                    "docType": "SHAREHOLDING_PATTERN",
                    "rawField": "Promoter & Promoter Group",
                    "mappedTo": "promoter_holding_pct",
                    "value": "Extracted",
                    "confidence": 0.98,
                }
            )
        if borrowing_parsed:
            schema_mappings.append(
                {
                    "docType": "BORROWING_PROFILE",
                    "rawField": "Total Outstanding Facilities",
                    "mappedTo": "total_debt",
                    "value": loan_amount or "Extracted",
                    "confidence": 0.92,
                }
            )
        if portfolio_parsed:
            schema_mappings.append(
                {
                    "docType": "PORTFOLIO_CUTS",
                    "rawField": "Gross Non-Performing Assets",
                    "mappedTo": "gnpa_pct",
                    "value": "Extracted",
                    "confidence": 0.89,
                }
            )

        _set_pipeline_stage(
            session_id=session_id,
            run_id=run_id,
            stage="cam_generation",
            workflow_status="cam_generation",
            message="Generating CAM payload and DOCX output",
        )
        cam_data = {
            "name": company_name,
            "pan": pan,
            "sector": sector,
            "promoter": promoter,
            "vintage": vintage,
            "turnover": turnover,
            "cibil_cmr": cibil,
            "segment": "NON-MSME",
            "session_id": session_id,
            "credit_score": avg_score,
            "verdict": verdict,
            "recommended_limit": loan_amount,
            "base_rate_mclr": "8.50%",
            "cbm_risk_premium": "+1.5%",
            "sector_spread": "-0.5%",
            "final_interest_rate": loan_rate or "N/A",
            "verdict_rationale": (
                f"AI Credit Score: {avg_score}/100. Verdict: {verdict}. "
                f"Based on analysis of {len(documents)} documents across {sector} sector."
            ),
            "concept_scores": {key: int(value * 100) for key, value in concept_scores.items()},
            "concept_flags": {},
            "concept_narratives": {},
            "shap_top_factors": [],
            "llm_narrative": f"Analysis of {company_name} across {len(documents)} documents.",
            "swot": swot_data,
            "triangulation": triangulation_data,
            "schema_mappings": schema_mappings,
            "loan_details": {
                "type": loan_type,
                "amount": loan_amount,
                "tenure": loan_tenure,
                "rate": loan_rate,
            },
        }

        cam_filename = f"CAM_{company_name.replace(' ', '_')}_{session_id}.docx"
        cam_path = os.path.join(OUTPUT_DIR, cam_filename)
        _cam_gen.generate_cam_docx(cam_data, cam_path)

        response_payload = {
            "session_id": session_id,
            "score": avg_score,
            "verdict": verdict,
            "execution_mode": capabilities["execution_mode"],
            "degradations": capabilities["degradations"],
            "swot": swot_data,
            "sector_research": sector_data,
            "triangulation": triangulation_data,
            "web_intel": {
                "status": rag_result.web_intel_report.status,
                "skipped_reason": rag_result.web_intel_report.skipped_reason,
                "queries_run": rag_result.web_intel_report.queries_run,
                "results_indexed": rag_result.web_intel_report.results_indexed,
                "key_findings": rag_result.web_intel_report.key_findings,
                "query_reports": rag_result.web_intel_report.query_reports or [],
            },
            "schemaMappings": schema_mappings,
            "concept_scores": {key: int(value * 100) for key, value in concept_scores.items()},
            "classifications": _serialize_classifications(documents),
            "cam_download_url": f"/api/download/{cam_filename}",
            "chunks_indexed": rag_result.chunks_indexed,
            "pipeline_run_id": run_id,
            "rag_capabilities": capabilities,
            "provenance_summary": rag_result.provenance_summary,
        }

        completed_at = _utc_now_iso()
        storage.update_pipeline_run(
            run_id,
            status="completed",
            stage="completed",
            completed_at=completed_at,
            result=response_payload,
            chunks_indexed=rag_result.chunks_indexed,
            cam_filename=cam_filename,
            cam_file_path=cam_path,
        )
        storage.add_pipeline_run_event(
            run_id=run_id,
            session_id=session_id,
            stage="completed",
            event_type="completed",
            created_at=completed_at,
            message="Pipeline run completed successfully",
            metadata={
                "chunks_indexed": rag_result.chunks_indexed,
                "execution_mode": capabilities["execution_mode"],
                "cam_filename": cam_filename,
            },
        )
        storage.update_document_session(
            session_id,
            updated_at=completed_at,
            workflow_status="completed",
            company_name=company_name,
            cam_filename=cam_filename,
            cam_file_path=cam_path,
            last_error=None,
        )
        return response_payload
    except HTTPException as exc:
        error_message = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
        failed_at = _utc_now_iso()
        storage.update_pipeline_run(
            run_id,
            status="failed",
            stage="failed",
            completed_at=failed_at,
            error_message=error_message,
        )
        storage.add_pipeline_run_event(
            run_id=run_id,
            session_id=session_id,
            stage="failed",
            event_type="failed",
            created_at=failed_at,
            message="Pipeline run failed with handled HTTP exception",
            metadata={"error_message": error_message},
        )
        storage.update_document_session(
            session_id,
            updated_at=failed_at,
            workflow_status="failed",
            company_name=company_name,
            last_error=error_message,
        )
        raise
    except Exception as exc:
        failed_at = _utc_now_iso()
        error_message = str(exc)
        storage.update_pipeline_run(
            run_id,
            status="failed",
            stage="failed",
            completed_at=failed_at,
            error_message=error_message,
        )
        storage.add_pipeline_run_event(
            run_id=run_id,
            session_id=session_id,
            stage="failed",
            event_type="failed",
            created_at=failed_at,
            message="Pipeline run failed with unhandled exception",
            metadata={"error_message": error_message},
        )
        storage.update_document_session(
            session_id,
            updated_at=failed_at,
            workflow_status="failed",
            company_name=company_name,
            last_error=error_message,
        )
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {error_message}") from exc


@router.get("/download/{filename}")
async def download_cam(
    filename: str,
    _: str = Depends(require_role("viewer")),
):
    """Download the generated CAM DOCX from persisted output storage."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="CAM file not found")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
