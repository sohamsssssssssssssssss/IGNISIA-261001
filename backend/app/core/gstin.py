"""
GSTIN validation and normalization helpers.
"""

from __future__ import annotations

import re


GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def normalize_gstin(value: str) -> str:
    return (value or "").strip().upper()


def is_valid_gstin(value: str) -> bool:
    return bool(GSTIN_PATTERN.fullmatch(normalize_gstin(value)))
