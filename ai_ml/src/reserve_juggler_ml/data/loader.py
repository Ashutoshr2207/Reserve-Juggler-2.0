"""Data loaders for committee dataset and operational history."""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from reserve_juggler_ml.data.schemas import HistoryObservation

DEFAULT_DATASET_PATH = r"C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv"
EXPECTED_SHA256 = (
    "2e7c1d2e5b678e9975250211e7e0017022049c510e1dd90cd7f29e931837b0c5"
)


def compute_file_sha256(filepath: str | Path) -> str:
    """Compute SHA-256 hash of a file efficiently in 64KB blocks."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def get_dataset_path(custom_path: Optional[str] = None) -> Path:
    """Get verified dataset path from argument, environment, or default location."""
    path_str = (
        custom_path
        or os.environ.get("RESERVE_JUGGLER_DATASET_PATH")
        or DEFAULT_DATASET_PATH
    )
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Committee dataset not found at: {path}")
    return path


def audit_committee_dataset(
    custom_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform integrity check and metadata extraction on the committee dataset."""
    path = get_dataset_path(custom_path)
    file_size = path.stat().st_size
    actual_sha256 = compute_file_sha256(path)

    df = pd.read_csv(path)
    return {
        "filepath": str(path),
        "file_size_bytes": file_size,
        "sha256": actual_sha256,
        "sha256_verified": actual_sha256 == EXPECTED_SHA256,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "currency": "USD",  # D07 is USD denominated
        "has_nulls": bool(df.isnull().any().any()),
        "time_start": str(df["timestamp"].iloc[0]),
        "time_end": str(df["timestamp"].iloc[-1]),
    }


def load_committee_dataset(
    custom_path: Optional[str] = None,
    verify_checksum: bool = True,
) -> pd.DataFrame:
    """
    Load the external committee dataset into a pandas DataFrame without modifying or copying it.
    Explicitly labels columns and preserves USD denomination.
    """
    path = get_dataset_path(custom_path)
    if verify_checksum:
        actual_hash = compute_file_sha256(path)
        if actual_hash != EXPECTED_SHA256:
            raise ValueError(
                f"Checksum mismatch for {path}. Expected {EXPECTED_SHA256}, got {actual_hash}"
            )

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def parse_history_records(
    records: List[Dict[str, Any]],
) -> List[HistoryObservation]:
    """Validate and parse a list of hourly history records."""
    if len(records) < 168:
        raise ValueError(
            f"History must contain at least 168 rows (7 days), got {len(records)}"
        )
    if len(records) > 5000:
        raise ValueError(
            f"History must contain at most 5000 rows, got {len(records)}"
        )

    observations = []
    for r in records:
        ts = str(r["timestamp"])
        dep = float(r["deposits"])
        wdr = float(r["withdrawals"])
        observations.append(
            HistoryObservation(timestamp=ts, deposits=dep, withdrawals=wdr)
        )
    return observations
