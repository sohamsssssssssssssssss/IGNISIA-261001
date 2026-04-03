"""
FastAPI endpoints for document classification (HITL) and schema configuration.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import List
from ..services.classifier import DocumentClassifier, ClassificationResult
from ..services.schema_config import SchemaManager
from ..core.security import require_role

router = APIRouter(prefix="/api", tags=["Classification & Schema"])

# Singletons for prototype
_classifier = DocumentClassifier()
_schema_mgr = SchemaManager()

# In-memory store for pending classifications
_pending_classifications: dict = {}


# ── Document Classification ────────────────────────────────────────

@router.post("/classify")
async def classify_document(
    file: UploadFile = File(...),
    _: str = Depends(require_role("analyst")),
):
    """Auto-classify an uploaded file. Returns predicted type + confidence."""
    file_bytes = await file.read()
    result = _classifier.auto_classify(file_bytes, file.filename)

    _pending_classifications[file.filename] = result

    return {
        "filename": result.filename,
        "predicted_type": result.predicted_type,
        "confidence": result.confidence,
        "evidence": result.evidence,
        "status": result.status,
    }


@router.post("/classify/batch")
async def classify_batch(
    files: List[UploadFile] = File(...),
    _: str = Depends(require_role("analyst")),
):
    """Classify multiple files at once."""
    results = []
    for file in files:
        file_bytes = await file.read()
        result = _classifier.auto_classify(file_bytes, file.filename)
        _pending_classifications[file.filename] = result
        results.append({
            "filename": result.filename,
            "predicted_type": result.predicted_type,
            "confidence": result.confidence,
            "evidence": result.evidence,
            "status": result.status,
        })
    return {"classifications": results}


@router.post("/classify/confirm")
async def confirm_classification(
    payload: dict,
    _: str = Depends(require_role("analyst")),
):
    """
    Analyst confirms, edits, or rejects a classification.
    Expected payload: { "filename": "...", "action": "APPROVE|EDIT|REJECT", "corrected_type": "..." }
    """
    filename = payload.get("filename")
    action = payload.get("action", "APPROVE").upper()
    corrected_type = payload.get("corrected_type")

    if filename not in _pending_classifications:
        return {"error": f"No pending classification for '{filename}'"}

    result = _pending_classifications[filename]

    if action == "APPROVE":
        result.status = "APPROVED"
    elif action == "EDIT" and corrected_type:
        result.predicted_type = corrected_type
        result.status = "EDITED"
        result.confidence = 1.0
        result.evidence = f"Manually reclassified by analyst to {corrected_type}"
    elif action == "REJECT":
        result.status = "REJECTED"
    else:
        return {"error": "Invalid action. Use APPROVE, EDIT, or REJECT."}

    _pending_classifications[filename] = result

    return {
        "filename": result.filename,
        "final_type": result.predicted_type,
        "status": result.status,
        "confidence": result.confidence,
    }


@router.get("/classify/pending")
async def get_pending_classifications(_: str = Depends(require_role("analyst"))):
    """Return all pending classifications awaiting analyst review."""
    return {
        "pending": [
            {
                "filename": r.filename,
                "predicted_type": r.predicted_type,
                "confidence": r.confidence,
                "evidence": r.evidence,
                "status": r.status,
            }
            for r in _pending_classifications.values()
            if r.status == "PENDING"
        ]
    }


# ── Schema Configuration ──────────────────────────────────────────

@router.get("/schema")
async def get_all_schemas(_: str = Depends(require_role("viewer"))):
    """Get extraction schemas for all document types."""
    return _schema_mgr.get_all_schemas()


@router.get("/schema/{doc_type}")
async def get_schema(
    doc_type: str,
    _: str = Depends(require_role("viewer")),
):
    """Get extraction schema for a specific document type."""
    try:
        fields = _schema_mgr.get_schema(doc_type)
        return {
            "doc_type": doc_type,
            "fields": [
                {"name": f.name, "type": f.field_type, "required": f.required, "description": f.description}
                for f in fields
            ]
        }
    except ValueError as e:
        return {"error": str(e)}


@router.put("/schema/{doc_type}")
async def update_schema(
    doc_type: str,
    payload: dict,
    _: str = Depends(require_role("admin")),
):
    """
    Replace extraction schema for a document type.
    Payload: { "fields": [{"name": "...", "type": "...", "required": true, "description": "..."}] }
    """
    try:
        fields = _schema_mgr.update_schema(doc_type, payload.get("fields", []))
        return {
            "doc_type": doc_type,
            "updated_fields": len(fields),
            "message": f"Schema for {doc_type} updated successfully",
        }
    except ValueError as e:
        return {"error": str(e)}


@router.post("/schema/{doc_type}/field")
async def add_field(
    doc_type: str,
    payload: dict,
    _: str = Depends(require_role("admin")),
):
    """Add a single field to a document type schema."""
    try:
        new_field = _schema_mgr.add_field(doc_type, payload)
        return {
            "doc_type": doc_type,
            "added_field": new_field.name,
            "message": f"Field '{new_field.name}' added to {doc_type}",
        }
    except ValueError as e:
        return {"error": str(e)}


@router.delete("/schema/{doc_type}/field/{field_name}")
async def remove_field(
    doc_type: str,
    field_name: str,
    _: str = Depends(require_role("admin")),
):
    """Remove a field from a document type schema."""
    try:
        removed = _schema_mgr.remove_field(doc_type, field_name)
        return {
            "doc_type": doc_type,
            "removed": removed,
            "message": f"Field '{field_name}' {'removed' if removed else 'not found'} in {doc_type}",
        }
    except ValueError as e:
        return {"error": str(e)}


@router.post("/schema/{doc_type}/reset")
async def reset_schema(
    doc_type: str,
    _: str = Depends(require_role("admin")),
):
    """Reset a schema back to its default configuration."""
    try:
        fields = _schema_mgr.reset_schema(doc_type)
        return {
            "doc_type": doc_type,
            "fields_count": len(fields),
            "message": f"Schema for {doc_type} reset to default",
        }
    except ValueError as e:
        return {"error": str(e)}
