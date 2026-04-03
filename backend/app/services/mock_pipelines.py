"""
Mock real-time data pipelines simulating live ingestion of:
  1. GST filing velocity & timeliness
  2. UPI transaction cadence & flow patterns
  3. E-way bill volume trends

Each pipeline generates time-series data for a GSTIN, handling sparse data
(new businesses may have only 3 months of history).

Pipeline parameters are derived deterministically from the GSTIN hash so that
every entity gets a unique but reproducible business profile.  The model scores
whatever features emerge — there is no pre-determined outcome.
"""

import hashlib
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional


# ──────────────────────────────────────────────────────────
#  DETERMINISTIC PROFILE DERIVATION
# ──────────────────────────────────────────────────────────

def _gstin_rng(gstin: str, salt: str = "") -> random.Random:
    """Return a seeded Random instance derived from the GSTIN + salt via SHA-256."""
    digest = hashlib.sha256(f"{gstin}:{salt}".encode()).hexdigest()
    seed = int(digest[:12], 16)
    return random.Random(seed)


def _profile_gstin(gstin: str) -> str:
    """Strip scheduler epoch salt so demo profiles stay stable across ingestions."""
    return gstin.split(":epoch", 1)[0]


def _lerp(t: float, low: float, high: float) -> float:
    return low + t * (high - low)


# ── Demo calibration profiles (exact GSTIN match) ────────
# These provide reproducible showcase data for the three demo
# walk-through entities.  Any GSTIN not listed here gets a
# unique profile derived from its hash.

_DEMO_GST_PROFILES: Dict[str, Dict[str, Any]] = {
    "29CLEAN5678B1Z2": {
        "months_active": 24,
        "avg_delay_days": 3,
        "filings_per_month": 1.0,
        "itc_variance_trend": "stable",
        "e_invoice_count_base": 85,
    },
    "27ARJUN1234A1Z5": {
        "months_active": 6,
        "avg_delay_days": 18,
        "filings_per_month": 0.7,
        "itc_variance_trend": "increasing",
        "e_invoice_count_base": 12,
    },
    "09NEWCO1234A1Z9": {
        "months_active": 3,
        "avg_delay_days": 6,
        "filings_per_month": 1.0,
        "itc_variance_trend": "stable",
        "e_invoice_count_base": 18,
    },
}

_DEMO_UPI_PROFILES: Dict[str, Dict[str, Any]] = {
    "29CLEAN5678B1Z2": {
        "months_active": 18,
        "avg_daily_txns": 15,
        "avg_txn_amount": 18000,
        "inflow_outflow_ratio": 1.1,
        "round_amount_pct": 0.12,
        "unique_counterparties": 45,
        "circular_risk_bias": 0.08,
    },
    "27ARJUN1234A1Z5": {
        "months_active": 6,
        "avg_daily_txns": 4,
        "avg_txn_amount": 25000,
        "inflow_outflow_ratio": 0.6,
        "round_amount_pct": 0.45,
        "unique_counterparties": 8,
        "circular_risk_bias": 0.95,
    },
    "09NEWCO1234A1Z9": {
        "months_active": 3,
        "avg_daily_txns": 7,
        "avg_txn_amount": 22000,
        "inflow_outflow_ratio": 1.05,
        "round_amount_pct": 0.18,
        "unique_counterparties": 14,
        "circular_risk_bias": 0.15,
    },
}

_DEMO_EWAY_PROFILES: Dict[str, Dict[str, Any]] = {
    "29CLEAN5678B1Z2": {
        "months_active": 24,
        "avg_bills_per_month": 45,
        "avg_bill_value": 320000,
        "interstate_pct": 0.6,
        "cancellation_rate": 0.03,
    },
    "27ARJUN1234A1Z5": {
        "months_active": 6,
        "avg_bills_per_month": 8,
        "avg_bill_value": 180000,
        "interstate_pct": 0.2,
        "cancellation_rate": 0.15,
    },
    "09NEWCO1234A1Z9": {
        "months_active": 3,
        "avg_bills_per_month": 11,
        "avg_bill_value": 210000,
        "interstate_pct": 0.35,
        "cancellation_rate": 0.05,
    },
}

LEGITIMATE_GSTIN_POOL: List[str] = [
    "29CLEAN5678B1Z2",
    "24MERCX1020A1Z5",
    "27SUPLY2040B1Z6",
    "07TRADE3060C1Z7",
    "33LOGIS4080D1Z8",
    "19FABRI5100E1Z9",
    "06WHOLE6120F1Z1",
    "09RETAL7140G1Z2",
    "32TOOLS8160H1Z3",
    "21SERVE9180J1Z4",
    "30MOTOR1200K1Z5",
    "08BUILD2300L1Z6",
    "10FOODS3400M1Z7",
    "18PACKS4500N1Z8",
    "23METAL5600P1Z9",
    "36CHEMX6700Q1Z1",
    "05PHARM7800R1Z2",
    "11CARGO8900S1Z3",
    "20TIMBR9010T1Z4",
    "26TEXTL0120U1Z5",
    "31PLAST1220V1Z6",
    "34ELECX2320W1Z7",
    "17AUTOX3420X1Z8",
    "22MACHI4520Y1Z9",
    "13STORE5620Z1Z1",
    "28PRINT6720A1Z2",
    "15AGROX7820B1Z3",
    "12STEEL8920C1Z4",
    "16CABLE9021D1Z5",
    "14PAPER0121E1Z6",
    "35CERAM1221F1Z7",
    "25GLASS2321G1Z8",
    "03MINER3421H1Z9",
    "04RUBBR4521J1Z1",
    "37HVACX5621K1Z2",
]

FRAUD_RINGS: Dict[str, List[str]] = {
    "ring_alpha": ["27ARJUN1234A1Z5", "29CYCAL5678B1Z3", "07FRAUD9012C1Z1"],
    "ring_beta": ["33SHELL1111D1Z2", "24GHOST2222E1Z4", "19EMPTY3333F1Z6", "06CYCLE4444G1Z8"],
}


def _ring_for_gstin(gstin: str) -> List[str] | None:
    base_gstin = _profile_gstin(gstin)
    for members in FRAUD_RINGS.values():
        if base_gstin in members:
            return members
    return None


def get_counterparty_gstin(source_gstin: str, rng: random.Random) -> str:
    source_gstin = _profile_gstin(source_gstin)
    ring_members = _ring_for_gstin(source_gstin)
    if ring_members:
        if rng.random() < 0.6:
            return rng.choice([member for member in ring_members if member != source_gstin])
        legit_choices = [gst for gst in LEGITIMATE_GSTIN_POOL if gst != source_gstin]
        return rng.choice(legit_choices)

    legit_choices = [gst for gst in LEGITIMATE_GSTIN_POOL if gst != source_gstin]
    return rng.choice(legit_choices)


def _derive_gst_profile(gstin: str) -> Dict[str, Any]:
    """Derive GST filing profile from GSTIN hash."""
    profile_gstin = _profile_gstin(gstin)
    if profile_gstin in _DEMO_GST_PROFILES:
        return _DEMO_GST_PROFILES[profile_gstin]

    rng = _gstin_rng(gstin, "gst")
    maturity = rng.random()
    discipline = rng.random()
    volume = rng.random()

    months = max(3, int(_lerp(maturity, 3, 36)))
    return {
        "months_active": months,
        "avg_delay_days": round(_lerp(1 - discipline, 2, 22), 1),
        "filings_per_month": round(_lerp(discipline, 0.5, 1.0), 2),
        "itc_variance_trend": "increasing" if discipline < 0.35 else "stable",
        "e_invoice_count_base": max(8, int(_lerp(volume, 8, 100))),
    }


def _derive_upi_profile(gstin: str) -> Dict[str, Any]:
    """Derive UPI cadence profile from GSTIN hash."""
    profile_gstin = _profile_gstin(gstin)
    if profile_gstin in _DEMO_UPI_PROFILES:
        return _DEMO_UPI_PROFILES[profile_gstin]

    rng = _gstin_rng(gstin, "upi")
    activity = rng.random()
    cashflow_health = rng.random()
    diversity = rng.random()
    fraud_surface = rng.random()

    return {
        "months_active": max(3, int(_lerp(activity, 3, 24))),
        "avg_daily_txns": max(2, int(_lerp(activity, 2, 20))),
        "avg_txn_amount": int(_lerp(activity, 12000, 30000)),
        "inflow_outflow_ratio": round(_lerp(cashflow_health, 0.5, 1.2), 2),
        "round_amount_pct": round(_lerp(1 - cashflow_health, 0.08, 0.50), 2),
        "unique_counterparties": max(5, int(_lerp(diversity, 5, 50))),
        "circular_risk_bias": round(_lerp(fraud_surface, 0.05, 0.95), 2),
    }


def _derive_eway_profile(gstin: str) -> Dict[str, Any]:
    """Derive e-way bill profile from GSTIN hash."""
    profile_gstin = _profile_gstin(gstin)
    if profile_gstin in _DEMO_EWAY_PROFILES:
        return _DEMO_EWAY_PROFILES[profile_gstin]

    rng = _gstin_rng(gstin, "eway")
    maturity = rng.random()
    scale = rng.random()
    discipline = rng.random()

    return {
        "months_active": max(3, int(_lerp(maturity, 3, 30))),
        "avg_bills_per_month": max(3, int(_lerp(scale, 5, 60))),
        "avg_bill_value": int(_lerp(scale, 150000, 400000)),
        "interstate_pct": round(_lerp(scale, 0.15, 0.65), 2),
        "cancellation_rate": round(_lerp(1 - discipline, 0.02, 0.18), 3),
    }


# ──────────────────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────────────────

def _months_range(months: int, end_date: Optional[datetime] = None) -> List[str]:
    """Generate a list of YYYY-MM strings going back `months` months."""
    end = end_date or datetime.now(timezone.utc)
    return [
        (end - timedelta(days=30 * i)).strftime("%Y-%m")
        for i in range(months - 1, -1, -1)
    ]


# ──────────────────────────────────────────────────────────
#  1. GST FILING VELOCITY PIPELINE
# ──────────────────────────────────────────────────────────

def generate_gst_velocity(gstin: str) -> Dict[str, Any]:
    """
    Simulate GST filing velocity data for a GSTIN.

    Returns:
        - filing_history: month-by-month filings with delay_days, filed (bool)
        - velocity_metrics: filings_per_month, avg_delay, on_time_pct
        - e_invoice_velocity: monthly e-invoice counts showing acceleration/deceleration
        - itc_variance_trend: month-on-month ITC claim variance
    """
    profile = _derive_gst_profile(gstin)
    rng = _gstin_rng(gstin, "gst_gen")
    months = profile["months_active"]
    periods = _months_range(months)

    filing_history = []
    e_invoice_counts = []
    itc_variances = []

    for i, period in enumerate(periods):
        filed = rng.random() < profile["filings_per_month"]
        delay = max(0, int(rng.gauss(profile["avg_delay_days"], 5))) if filed else None

        # E-invoice count with growth trend
        growth = 1.0 + (i / max(months, 1)) * 0.3  # 30% growth over period
        noise = rng.uniform(0.7, 1.3)
        e_inv_count = int(profile["e_invoice_count_base"] * growth * noise)

        # ITC variance
        if profile["itc_variance_trend"] == "increasing":
            base_var = 5 + (i / max(months, 1)) * 15
        else:
            base_var = 3 + rng.uniform(-1, 1)
        itc_var = round(max(0, base_var + rng.gauss(0, 2)), 1)

        filing_history.append({
            "period": period,
            "filed": filed,
            "delay_days": delay,
            "due_date": f"{period}-11",
            "e_invoice_count": e_inv_count,
            "itc_variance_pct": itc_var,
        })
        if filed:
            e_invoice_counts.append(e_inv_count)
        itc_variances.append(itc_var)

    filed_months = [f for f in filing_history if f["filed"]]
    total_filed = len(filed_months)
    on_time = len([f for f in filed_months if f["delay_days"] is not None and f["delay_days"] <= 10])

    return {
        "gstin": gstin,
        "months_active": months,
        "filing_history": filing_history,
        "velocity_metrics": {
            "filings_per_month": round(total_filed / max(months, 1), 2),
            "avg_delay_days": round(
                sum(f["delay_days"] for f in filed_months if f["delay_days"] is not None) / max(total_filed, 1), 1
            ),
            "on_time_pct": round(on_time / max(total_filed, 1) * 100, 1),
            "total_e_invoices": sum(e_invoice_counts),
            "e_invoice_trend": "accelerating" if len(e_invoice_counts) >= 3 and e_invoice_counts[-1] > e_invoice_counts[0] else "decelerating",
        },
        "itc_variance_trend": itc_variances,
        "data_freshness": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sparse_data": months < 6,
    }


# ──────────────────────────────────────────────────────────
#  2. UPI TRANSACTION CADENCE PIPELINE
# ──────────────────────────────────────────────────────────

def _should_inject_rotation(gstin: str, profile: Dict[str, Any]) -> bool:
    """
    Decide whether to inject circular fund rotation patterns based on the
    entity's fraud surface trait.  No scenario label is consulted — the
    decision is driven entirely by the GSTIN-derived profile.
    """
    rng = _gstin_rng(gstin, "fraud_gate")
    return _ring_for_gstin(gstin) is not None or rng.random() < profile.get("circular_risk_bias", 0.1)


def _generate_linked_rotation_transactions(
    gstin: str,
    period: str,
    linked_entities: List[str],
    base_amount: float,
    repetitions: int,
) -> List[Dict[str, Any]]:
    """Generate explicit multi-entity circular fund flows for fraud testing."""
    ring = [gstin, *linked_entities]
    txns: List[Dict[str, Any]] = []

    for idx in range(repetitions):
        day = f"{period}-{(idx % 20) + 1:02d}"
        amount = round(max(10000, base_amount + (idx % 3) * 5000), -4)

        for node_index, src in enumerate(ring):
            dst = ring[(node_index + 1) % len(ring)]
            counterparty = dst if src == gstin else src
            txns.append({
                "date": day,
                "src_vpa": src,
                "dst_vpa": dst,
                "counterparty_vpa": counterparty,
                "amount": amount,
                "direction": "DR" if src == gstin else ("CR" if dst == gstin else "NETWORK"),
                "is_round_amount": True,
                "topology_tag": "linked_msme_cycle",
            })

    return txns


def generate_upi_cadence(gstin: str) -> Dict[str, Any]:
    """
    Simulate UPI transaction cadence data.

    Returns:
        - monthly_summary: txn counts, volumes, inflow/outflow by month
        - cadence_metrics: regularity score, peak days, avg daily txns
        - flow_pattern: inflow_outflow_ratio, round_amount_pct
        - counterparty_analysis: unique counterparties, concentration
        - transactions: sample transaction list for fraud detection
    """
    profile = _derive_upi_profile(gstin)
    rng = _gstin_rng(gstin, "upi_gen")
    months = profile["months_active"]
    periods = _months_range(min(months, 12))  # Cap at 12 months of UPI data

    monthly_summary = []
    all_transactions = []
    counterparty_ids = [f"UPI_{rng.randint(1000, 9999)}" for _ in range(profile["unique_counterparties"])]
    inject_rotation = _should_inject_rotation(gstin, profile)
    ring_members = _ring_for_gstin(gstin)
    linked_entities = [member for member in (ring_members or []) if member != _profile_gstin(gstin)]
    if inject_rotation and not linked_entities:
        linked_entities = rng.sample(
            [candidate for candidate in LEGITIMATE_GSTIN_POOL if candidate != _profile_gstin(gstin)],
            k=3,
        )

    for i, period in enumerate(periods):
        days_in_month = 30
        daily_txns = max(1, int(rng.gauss(profile["avg_daily_txns"], 3)))
        total_txns = daily_txns * days_in_month

        inflow_count = int(total_txns * profile["inflow_outflow_ratio"] / (1 + profile["inflow_outflow_ratio"]))
        outflow_count = total_txns - inflow_count

        inflow_vol = sum(
            rng.gauss(profile["avg_txn_amount"], profile["avg_txn_amount"] * 0.3)
            for _ in range(inflow_count)
        )
        outflow_vol = sum(
            rng.gauss(profile["avg_txn_amount"], profile["avg_txn_amount"] * 0.3)
            for _ in range(outflow_count)
        )

        # Round amount detection
        round_txns = int(total_txns * profile["round_amount_pct"])

        monthly_summary.append({
            "period": period,
            "total_txns": total_txns,
            "inflow_count": inflow_count,
            "outflow_count": outflow_count,
            "inflow_volume": round(max(0, inflow_vol)),
            "outflow_volume": round(max(0, outflow_vol)),
            "net_flow": round(max(0, inflow_vol) - max(0, outflow_vol)),
            "round_amount_txns": round_txns,
            "unique_counterparties": min(len(counterparty_ids), total_txns),
        })

        # Generate sample transactions for this month (for fraud graph)
        for j in range(min(total_txns, 50)):  # Cap at 50 samples per month
            is_inflow = j < inflow_count
            counterparty = get_counterparty_gstin(gstin, rng)
            amount = rng.gauss(profile["avg_txn_amount"], profile["avg_txn_amount"] * 0.3)
            if j < round_txns:
                amount = round(amount / 10000) * 10000  # Make it a round number

            src = counterparty if is_inflow else _profile_gstin(gstin)
            dst = _profile_gstin(gstin) if is_inflow else counterparty
            all_transactions.append({
                "date": f"{period}-{rng.randint(1, 28):02d}",
                "counterparty_vpa": counterparty,
                "src_vpa": src,
                "dst_vpa": dst,
                "amount": round(max(100, amount)),
                "direction": "CR" if is_inflow else "DR",
                "is_round_amount": j < round_txns,
            })

        if inject_rotation and i >= max(0, len(periods) - 3):
            all_transactions.extend(
                _generate_linked_rotation_transactions(
                    gstin=gstin,
                    period=period,
                    linked_entities=linked_entities,
                    base_amount=profile["avg_txn_amount"] * 2.4,
                    repetitions=4,
                )
            )

    total_inflow = sum(m["inflow_volume"] for m in monthly_summary)
    total_outflow = sum(m["outflow_volume"] for m in monthly_summary)
    total_txns_all = sum(m["total_txns"] for m in monthly_summary)

    # Cadence regularity: std dev of daily txn count (lower = more regular)
    daily_counts = [m["total_txns"] / 30 for m in monthly_summary]
    cadence_std = (sum((d - sum(daily_counts) / len(daily_counts))**2 for d in daily_counts) / max(len(daily_counts), 1)) ** 0.5
    regularity_score = round(max(0, min(100, 100 - cadence_std * 10)), 1)

    return {
        "gstin": gstin,
        "months_active": len(periods),
        "monthly_summary": monthly_summary,
        "cadence_metrics": {
            "avg_daily_txns": round(sum(daily_counts) / max(len(daily_counts), 1), 1),
            "regularity_score": regularity_score,
            "total_transactions": total_txns_all,
            "peak_month": max(monthly_summary, key=lambda m: m["total_txns"])["period"] if monthly_summary else None,
        },
        "flow_pattern": {
            "inflow_outflow_ratio": round(total_inflow / max(total_outflow, 1), 2),
            "round_amount_pct": round(
                sum(m["round_amount_txns"] for m in monthly_summary) / max(total_txns_all, 1) * 100, 1
            ),
            "net_cash_position": round(total_inflow - total_outflow),
        },
        "counterparty_analysis": {
            "unique_counterparties": len({txn["counterparty_vpa"] for txn in all_transactions}),
            "top_5_concentration_pct": round(min(80, 5 / max(len(counterparty_ids), 1) * 100 * 3), 1),
            "linked_msme_count": len(linked_entities),
        },
        "transactions": all_transactions[-100:],  # Last 100 for fraud detection
        "data_freshness": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sparse_data": len(periods) < 6,
    }


# ──────────────────────────────────────────────────────────
#  3. E-WAY BILL VOLUME PIPELINE
# ──────────────────────────────────────────────────────────

def generate_eway_bill_volume(gstin: str) -> Dict[str, Any]:
    """
    Simulate e-way bill volume trends.

    Returns:
        - monthly_volumes: bill counts and values per month
        - trend_metrics: volume momentum, MoM growth, interstate ratio
        - anomaly_flags: cancellation spikes, value anomalies
    """
    profile = _derive_eway_profile(gstin)
    rng = _gstin_rng(gstin, "eway_gen")
    months = profile["months_active"]
    periods = _months_range(min(months, 12))

    monthly_volumes = []

    for i, period in enumerate(periods):
        # Volume with growth trend
        growth_factor = 1 + (i / max(len(periods), 1)) * 0.2
        noise = rng.uniform(0.7, 1.3)
        bill_count = max(1, int(profile["avg_bills_per_month"] * growth_factor * noise))

        # Values
        total_value = sum(
            rng.gauss(profile["avg_bill_value"], profile["avg_bill_value"] * 0.3)
            for _ in range(bill_count)
        )

        interstate = int(bill_count * profile["interstate_pct"] * rng.uniform(0.8, 1.2))
        cancelled = int(bill_count * profile["cancellation_rate"] * rng.uniform(0.5, 2.0))

        monthly_volumes.append({
            "period": period,
            "bill_count": bill_count,
            "total_value": round(max(0, total_value)),
            "avg_value": round(max(0, total_value) / max(bill_count, 1)),
            "interstate_count": min(interstate, bill_count),
            "intrastate_count": bill_count - min(interstate, bill_count),
            "cancelled_count": min(cancelled, bill_count),
        })

    # Trend calculations
    counts = [m["bill_count"] for m in monthly_volumes]
    if len(counts) >= 2:
        mom_growth = [(counts[i] - counts[i-1]) / max(counts[i-1], 1) * 100 for i in range(1, len(counts))]
        avg_mom = round(sum(mom_growth) / len(mom_growth), 1)
    else:
        mom_growth = []
        avg_mom = 0.0

    # Volume momentum: last 3 months vs first 3 months
    if len(counts) >= 6:
        recent = sum(counts[-3:])
        early = sum(counts[:3])
        momentum = round((recent - early) / max(early, 1) * 100, 1)
    else:
        momentum = 0.0

    # Anomaly detection
    anomaly_flags = []
    for m in monthly_volumes:
        if m["cancelled_count"] / max(m["bill_count"], 1) > 0.1:
            anomaly_flags.append({
                "period": m["period"],
                "type": "HIGH_CANCELLATION",
                "detail": f"{m['cancelled_count']}/{m['bill_count']} bills cancelled ({m['cancelled_count']/max(m['bill_count'],1)*100:.0f}%)",
            })

    return {
        "gstin": gstin,
        "months_active": len(periods),
        "monthly_volumes": monthly_volumes,
        "trend_metrics": {
            "total_bills": sum(counts),
            "avg_bills_per_month": round(sum(counts) / max(len(counts), 1), 1),
            "avg_mom_growth_pct": avg_mom,
            "volume_momentum_pct": momentum,
            "interstate_ratio": round(
                sum(m["interstate_count"] for m in monthly_volumes) / max(sum(counts), 1) * 100, 1
            ),
        },
        "anomaly_flags": anomaly_flags,
        "data_freshness": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sparse_data": len(periods) < 6,
    }


# ──────────────────────────────────────────────────────────
#  UNIFIED PIPELINE RUNNER
# ──────────────────────────────────────────────────────────

def run_all_pipelines(gstin: str) -> Dict[str, Any]:
    """Run all three pipelines for a GSTIN and return combined data."""
    return {
        "gstin": gstin,
        "gst_velocity": generate_gst_velocity(gstin),
        "upi_cadence": generate_upi_cadence(gstin),
        "eway_bill": generate_eway_bill_volume(gstin),
        "pipeline_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
