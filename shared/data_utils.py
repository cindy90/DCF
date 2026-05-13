"""
data_utils.py — 数据处理工具函数
Numeric conversion, statistical helpers, exchange name mapping.
"""
from typing import Optional, Callable, List
import json


def nv(v, dec: int = 2) -> Optional[float]:
    """
    Safe float conversion. Returns None for NaN / None / unparseable.
    Rounds to `dec` decimal places.
    """
    try:
        f = float(v)
        return None if f != f else round(f, dec)  # NaN check
    except (TypeError, ValueError):
        return None


def stat(vals: list, fn: Callable, dec: int = 2) -> Optional[float]:
    """
    Apply an aggregation function to a list of nullable values.
    Filters out None, returns None if empty.
    """
    vv = [v for v in vals if v is not None]
    return round(float(fn(vv)), dec) if vv else None


def exch(code: str) -> str:
    """Map stock ticker suffix to exchange display name."""
    if code.endswith('.SH'):
        return '上交所(SH)'
    if code.endswith('.SZ'):
        return '深交所(SZ)'
    if code.endswith('.BJ'):
        return '北交所(BJ)'
    return '—'


def load_json(path: str, encoding='utf-8') -> dict:
    """Load and return a JSON file."""
    with open(path, encoding=encoding) as f:
        return json.load(f)


def filter_positive(values: list, lower: float = 0,
                    upper: float = float('inf')) -> list:
    """Filter a list to keep only values in (lower, upper) exclusive."""
    return [v for v in values if v is not None and lower < v < upper]
