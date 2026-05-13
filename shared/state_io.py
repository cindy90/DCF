"""
state_io.py — _State sheet 读写
Read/write the _State metadata sheet that stores key cell references,
phase completion flags, and other model metadata.
"""
import json
from typing import Dict, Any, Optional


def read_state(wb) -> Dict[str, str]:
    """
    Read all key: value pairs from the _State sheet.
    Returns a dict of string key → string value.
    """
    ws = wb['_State']
    state = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] and ': ' in str(row[0]):
            k, v = str(row[0]).split(': ', 1)
            state[k.strip()] = v.strip()
    return state


def write_state_key(wb, key: str, value: str):
    """
    Write or update a single key: value pair in _State.
    If the key exists, update it; otherwise append a new row.
    """
    ws = wb['_State']
    for row in ws.iter_rows():
        if row[0].value and str(row[0].value).startswith(key + ': '):
            row[0].value = f'{key}: {value}'
            return
    ws.append([f'{key}: {value}'])


def read_key_cells(state: Dict[str, str]) -> Dict[str, Dict[str, int]]:
    """
    Parse KEY_CELLS_IS, KEY_CELLS_BS, KEY_CELLS_CF from state dict.
    Returns {'IS': {...}, 'BS': {...}, 'CF': {...}}.
    """
    result = {}
    for key, short in [('KEY_CELLS_IS', 'IS'),
                       ('KEY_CELLS_BS', 'BS'),
                       ('KEY_CELLS_CF', 'CF')]:
        raw = state.get(key, '{}')
        result[short] = json.loads(raw)
    return result


def get_key_row(key_cells: Dict, sheet: str, metric: str,
                default: Optional[int] = None) -> int:
    """
    Get a specific row number from key_cells.
    Example: get_key_row(kc, 'IS', 'Revenue_row')
    """
    val = key_cells.get(sheet, {}).get(metric, default)
    if val is None:
        raise KeyError(f"Key row '{metric}' not found in KEY_CELLS_{sheet}")
    return int(val)
