from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import borrower
from app.api.classification_endpoint import router as classification_router
from app.api.upload_endpoint import router as upload_router
from app.api.agent_status_endpoint import router as agent_status_router
from app.api.scoring_endpoint import router as scoring_router
from app.core.entity_graph import get_entity_graph_service
from app.core.chroma_client import ensure_chroma_collections
from app.core.migrations import run_database_migrations
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    StructuredLoggingMiddleware,
)
from app.core.rag_runtime import get_rag_capabilities
from app.core.scheduler import seed_demo_gstins, start_scheduler, stop_scheduler
from app.core.settings import get_settings
from app.core.storage import get_storage
from app.core.xgboost_model import get_scorer
from app.fixtures.demo_config import is_demo_mode
from app.services.embedding_service import get_embedding_service
from app.services.retrieval_service import get_retrieval_service

settings = get_settings()
logger = logging.getLogger("intellicredit.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed demo GSTINs and start background pipeline workers
    if settings.auto_migrate_database:
        run_database_migrations()
    ensure_chroma_collections()
    static_embedding_status = get_embedding_service().bootstrap_static_documents()
    logger.info("Static embedding bootstrap complete: %s", static_embedding_status)
    retrieval_seed_status = get_retrieval_service().seed_synthetic_history_if_empty(min_cases=100)
    logger.info("Retrieval history bootstrap complete: %s", retrieval_seed_status)
    seed_demo_gstins()
    start_scheduler()
    yield
    # Shutdown: stop background workers
    stop_scheduler()


app = FastAPI(title=settings.app_name, version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(borrower.router, prefix="/api/borrower", tags=["borrower"])
app.include_router(classification_router)
app.include_router(upload_router)
app.include_router(agent_status_router)
app.include_router(scoring_router)

@app.get("/health")
def health_check():
    storage = get_storage()
    from app.core.scheduler import get_scheduler
    sched = get_scheduler()
    return {
        "status": "ok",
        "environment": settings.app_env,
        "demo_mode": is_demo_mode(),
        "storage": storage.health_summary(),
        "model": get_scorer().health_summary(),
        "pipeline_scheduler": {
            "running": sched is not None and sched.running if sched else False,
            "interval_seconds": settings.pipeline_interval_seconds,
            "monitored_gstins": len(storage.get_monitored_gstins()),
        },
        "entity_graph": get_entity_graph_service().health_summary(),
        "rag": get_rag_capabilities(),
    }
