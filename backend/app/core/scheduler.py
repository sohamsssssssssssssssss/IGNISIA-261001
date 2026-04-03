"""
Background pipeline workers that simulate real-time data ingestion.

Three independent workers — GST velocity, UPI cadence, e-way bill — run on a
configurable schedule (default 15 min).  Each worker iterates over all monitored
GSTINs, generates a new data snapshot with an incremented epoch, and writes it
to the pipeline_data table.  The scoring API reads from this table instead of
generating data on the fly.

The epoch counter ensures that successive runs produce evolving data: the mock
pipeline generators receive the epoch as a time-shift salt, so the random seed
changes each run while remaining deterministic within a run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

from apscheduler.schedulers.background import BackgroundScheduler

from .entity_graph import get_entity_graph_service
from .settings import get_settings
from .storage import get_storage
from ..services.mock_pipelines import (
    generate_eway_bill_volume,
    generate_gst_velocity,
    generate_upi_cadence,
)

logger = logging.getLogger("intellicredit.pipeline")

_scheduler: BackgroundScheduler | None = None

# Demo GSTINs that are pre-registered on startup
DEMO_GSTINS = [
    ("29CLEAN5678B1Z2", "CleanTech Manufacturing Ltd."),
    ("27ARJUN1234A1Z5", "Arjun Textiles Pvt. Ltd."),
    ("09NEWCO1234A1Z9", "New Startup Pvt. Ltd."),
]

PIPELINE_GENERATORS: Dict[str, Callable[[str], Dict[str, Any]]] = {
    "gst": generate_gst_velocity,
    "gst_velocity": generate_gst_velocity,
    "upi": generate_upi_cadence,
    "upi_cadence": generate_upi_cadence,
    "eway": generate_eway_bill_volume,
    "eway_bill": generate_eway_bill_volume,
}

PIPELINE_CANONICAL_NAMES = {
    "gst": "gst_velocity",
    "gst_velocity": "gst_velocity",
    "upi": "upi_cadence",
    "upi_cadence": "upi_cadence",
    "eway": "eway_bill",
    "eway_bill": "eway_bill",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_single_pipeline(
    gstin: str,
    pipeline_type: str,
    generator: Callable[[str], Dict[str, Any]],
    epoch: int,
) -> Dict[str, Any]:
    """Run one pipeline generator and persist the result."""
    # Inject epoch into the GSTIN salt so successive runs produce different data
    # while remaining deterministic within a run.
    salted_gstin = f"{gstin}:epoch{epoch}" if epoch > 0 else gstin
    data = generator(salted_gstin)
    # Restore the real GSTIN in the output
    data["gstin"] = gstin
    return data


def _ingest_single_pipeline_for_gstin(
    gstin: str,
    pipeline_type: str,
    generator: Callable[[str], Dict[str, Any]],
) -> None:
    storage = get_storage()
    epoch = storage.get_pipeline_epoch(gstin, pipeline_type) + 1
    data = _run_single_pipeline(gstin, pipeline_type, generator, epoch)
    storage.store_pipeline_data(
        gstin=gstin,
        pipeline_type=pipeline_type,
        epoch=epoch,
        data=data,
        ingested_at=_now_iso(),
    )
    if pipeline_type == "upi_cadence":
        get_entity_graph_service().register_transactions(
            gstin,
            data.get("transactions", []),
        )


def ingest_gst_velocity() -> None:
    """Background worker: GST filing velocity pipeline."""
    storage = get_storage()
    gstins = storage.get_monitored_gstins()
    ts = _now_iso()
    for gstin in gstins:
        epoch = storage.get_pipeline_epoch(gstin, "gst_velocity") + 1
        data = _run_single_pipeline(gstin, "gst_velocity", generate_gst_velocity, epoch)
        storage.store_pipeline_data(
            gstin=gstin,
            pipeline_type="gst_velocity",
            epoch=epoch,
            data=data,
            ingested_at=ts,
        )
    logger.info("GST velocity pipeline ingested %d GSTINs (epoch +1)", len(gstins))


def ingest_upi_cadence() -> None:
    """Background worker: UPI transaction cadence pipeline."""
    storage = get_storage()
    gstins = storage.get_monitored_gstins()
    ts = _now_iso()
    for gstin in gstins:
        epoch = storage.get_pipeline_epoch(gstin, "upi_cadence") + 1
        data = _run_single_pipeline(gstin, "upi_cadence", generate_upi_cadence, epoch)
        storage.store_pipeline_data(
            gstin=gstin,
            pipeline_type="upi_cadence",
            epoch=epoch,
            data=data,
            ingested_at=ts,
        )
        get_entity_graph_service().register_transactions(gstin, data.get("transactions", []))
    logger.info("UPI cadence pipeline ingested %d GSTINs (epoch +1)", len(gstins))


def ingest_eway_bills() -> None:
    """Background worker: e-way bill volume pipeline."""
    storage = get_storage()
    gstins = storage.get_monitored_gstins()
    ts = _now_iso()
    for gstin in gstins:
        epoch = storage.get_pipeline_epoch(gstin, "eway_bill") + 1
        data = _run_single_pipeline(gstin, "eway_bill", generate_eway_bill_volume, epoch)
        storage.store_pipeline_data(
            gstin=gstin,
            pipeline_type="eway_bill",
            epoch=epoch,
            data=data,
            ingested_at=ts,
        )
    logger.info("E-way bill pipeline ingested %d GSTINs (epoch +1)", len(gstins))


def seed_demo_gstins() -> None:
    """Register demo GSTINs so background workers can ingest them on schedule."""
    storage = get_storage()
    for gstin, name in DEMO_GSTINS:
        storage.register_gstin(gstin, name)
    logger.info("Registered %d demo GSTINs for background ingestion", len(DEMO_GSTINS))


def trigger_immediate_ingestion(gstin: str, company_name: str | None = None) -> None:
    """
    Register a GSTIN and enqueue one-shot background ingestion jobs when possible.
    The request path does not write pipeline data directly.
    """
    storage = get_storage()
    storage.register_gstin(gstin, company_name)
    if _scheduler is None or not _scheduler.running:
        logger.info("Registered %s for ingestion; scheduler is not running", gstin)
        return

    run_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    for ptype, gen in [
        ("gst_velocity", generate_gst_velocity),
        ("upi_cadence", generate_upi_cadence),
        ("eway_bill", generate_eway_bill_volume),
    ]:
        _scheduler.add_job(
            _ingest_single_pipeline_for_gstin,
            "date",
            run_date=run_at,
            id=f"bootstrap:{ptype}:{gstin}",
            replace_existing=True,
            kwargs={
                "gstin": gstin,
                "pipeline_type": ptype,
                "generator": gen,
            },
        )
    logger.info("Registered %s and scheduled background bootstrap ingestion", gstin)


def refresh_gstin_now(gstin: str, company_name: str | None = None) -> None:
    """Force an immediate refresh of all three pipeline streams for a GSTIN."""
    storage = get_storage()
    storage.register_gstin(gstin, company_name)
    for pipeline_type, generator in [
        ("gst_velocity", generate_gst_velocity),
        ("upi_cadence", generate_upi_cadence),
        ("eway_bill", generate_eway_bill_volume),
    ]:
        _ingest_single_pipeline_for_gstin(gstin, pipeline_type, generator)
    logger.info("Forced immediate pipeline refresh for %s", gstin)


def refresh_pipeline_stream(
    gstin: str,
    stream: str,
    company_name: str | None = None,
) -> str:
    """Force an immediate refresh of a single pipeline stream for a GSTIN."""
    canonical = PIPELINE_CANONICAL_NAMES.get(stream)
    generator = PIPELINE_GENERATORS.get(stream)
    if canonical is None or generator is None:
        raise ValueError(f"Unsupported pipeline stream: {stream}")

    storage = get_storage()
    storage.register_gstin(gstin, company_name)
    _ingest_single_pipeline_for_gstin(gstin, canonical, generator)
    logger.info("Forced immediate %s refresh for %s", canonical, gstin)
    return canonical


def start_scheduler() -> None:
    """Start the three background pipeline workers on the configured interval."""
    global _scheduler
    if _scheduler is not None:
        return

    settings = get_settings()
    if not settings.pipeline_auto_start:
        logger.info("Pipeline scheduler disabled (PIPELINE_AUTO_START=false)")
        return

    interval = settings.pipeline_interval_seconds

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(ingest_gst_velocity, "interval", seconds=interval, id="gst_velocity_worker")
    _scheduler.add_job(ingest_upi_cadence, "interval", seconds=interval, id="upi_cadence_worker")
    _scheduler.add_job(ingest_eway_bills, "interval", seconds=interval, id="eway_bill_worker")
    _scheduler.start()
    # Demo bootstrap: preload monitored GSTINs so scoring and fraud graph are warm
    ingest_gst_velocity()
    ingest_upi_cadence()
    ingest_eway_bills()
    logger.info("Pipeline scheduler started — 3 workers at %ds interval", interval)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler
