from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()

# Global dict to hold WS connections for real-time progress (Prototype only)
active_connections: dict[str, WebSocket] = {}

async def process_pipeline(borrower_id: str):
    """
    Mock pipeline execution demonstrating the 3 Pillars integration 
    with WebSocket live progress feedback to the React UI.
    """
    ws = active_connections.get(borrower_id)
    
    async def notify(msg: str):
        if ws:
            try:
                await ws.send_text(json.dumps({"status": msg}))
            except:
                pass
                
    await notify("Pillar 1: Parsing documents (GSTR, ITR, Banks)...")
    await asyncio.sleep(2)
    
    await notify("Pillar 1: Running GSTR-2A vs 3B Reconciliation...")
    await asyncio.sleep(1)
    
    await notify("Pillar 2: Initializing LinUCB Agents...")
    await asyncio.sleep(1)
    
    await notify("Pillar 2: eCourts Litigation Check - 0 cases.")
    await asyncio.sleep(1)
    
    await notify("Pillar 3: Formatting Concept Bottleneck Vector...")
    await asyncio.sleep(1)
    
    await notify("Pillar 3: Final CAM Score generated. Creating DOCX...")
    await asyncio.sleep(1)
    
    await notify("DONE")

@router.post("/upload")
async def upload_documents(
    borrower_id: str = Form(...),
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # Enqueue processing task (Simulates Celery)
    background_tasks.add_task(process_pipeline, borrower_id)
    return {"message": "Processing started", "borrower_id": borrower_id}

@router.websocket("/ws/{borrower_id}")
async def websocket_endpoint(websocket: WebSocket, borrower_id: str):
    await websocket.accept()
    active_connections[borrower_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        del active_connections[borrower_id]
        
@router.post("/dd_notes")
async def submit_dd_notes(payload: dict):
    # Recalculates feature vector concepts based on officer notes
    return {
        "score_update": 74.5,
        "new_concepts": {
            "management_quality": payload.get("management_quality", 3) / 5.0
        }
    }

@router.get("/results/{borrower_id}")
async def get_results(borrower_id: str):
    return {
        "borrower_id": borrower_id,
        "final_score": 76.2,
        "recommended_limit": 50000000,
        "concept_radar": {
            "Character": 0.8,
            "Capacity": 0.7,
            "Capital": 0.9,
            "Collateral": 0.6,
            "Conditions": 0.5
        },
        "concept_narratives": {
            "Character": "Promoter has a clean regulatory record with no major litigations flagged in eCourts.",
            "Capacity": "DSCR is healthy at 1.45x, showing adequate debt servicing capacity.",
            "Capital": "TNW is stable, but TOL/TNW is slightly elevated at 2.8x.",
            "Collateral": "Primary security offered covers 1.3x of the proposed limit.",
            "Conditions": "Sector outlook is stable with no immediate negative RBI headwinds."
        },
        "concept_flags": {
            "Capital": "TOL/TNW is near the 3.0x threshold, requires monitoring."
        },
        "shap": [
            {"feature": "High DSCR", "contribution": "+12 pts"},
            {"feature": "Zero late GSTs", "contribution": "+8 pts"},
            {"feature": "Negative news sentiment", "contribution": "-5 pts"}
        ]
    }
