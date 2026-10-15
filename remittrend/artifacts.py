"""Reading and writing the JSON files that pass results from the pipeline to the web app."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def to_plain(value):
    """Convert numpy and pandas values to plain Python; NaN becomes None (null in JSON)."""
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray, pd.Series, pd.Index)):
        return [to_plain(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(value) or math.isinf(value) else float(value)
    if isinstance(value, (pd.Period, pd.Timestamp)):
        return str(value)
    return value


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(value), allow_nan=False, indent=1), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
