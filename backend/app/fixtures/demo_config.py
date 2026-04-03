"""
Central demo mode configuration.
Controls whether agents use live APIs or return fixture data.
"""

from ..core.settings import get_settings


def is_demo_mode() -> bool:
    return get_settings().demo_mode
