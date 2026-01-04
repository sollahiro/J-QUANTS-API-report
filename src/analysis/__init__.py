"""
分析モジュール
"""

from .individual import (
    IndividualAnalyzer,
    evaluate_roe_eps_bps_pattern,
    evaluate_per_pbr_roe_pattern,
    evaluate_roe_eps_bps_pattern_by_cagr,
    evaluate_per_pbr_roe_pattern_by_cagr
)
from .calculator import (
    calculate_metrics_flexible,
    calculate_yoy_growth,
    calculate_cagr,
    calculate_growth_rate
)

__all__ = [
    "IndividualAnalyzer",
    "evaluate_roe_eps_bps_pattern",
    "evaluate_per_pbr_roe_pattern",
    "evaluate_roe_eps_bps_pattern_by_cagr",
    "evaluate_per_pbr_roe_pattern_by_cagr",
    "calculate_metrics_flexible",
    "calculate_yoy_growth",
    "calculate_cagr",
    "calculate_growth_rate",
]

