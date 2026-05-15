"""Macro data convenience functions — thin wrappers over DataGateway.

These functions are kept for backward compatibility.
New code should use DataGateway().get_macro() directly.
"""
from src.data.gateway import DataGateway


def get_all_macro_data() -> dict:
    """Get all macro data via Gateway."""
    return DataGateway().get_macro()


def get_macro_data_for_analyzer() -> dict:
    """Get macro data formatted for MacroAnalyzer."""
    return get_all_macro_data()
