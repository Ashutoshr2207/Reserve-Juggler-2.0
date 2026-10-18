"""Unit tests for data loading and dataset verification."""

import pytest
import os
from pathlib import Path
from reserve_juggler_ml.data.loader import (
    audit_committee_dataset,
    compute_file_sha256,
    get_dataset_path,
    parse_history_records,
)


@pytest.mark.skipif(
    os.environ.get("RJ_ML_PRIVATE_DATA_AUDIT") != "true",
    reason="Private dataset audit is opt-in; integration tests use synthetic fixtures.",
)
def test_get_dataset_path_verifies_existence():
    path = get_dataset_path()
    assert path.is_file()
    assert path.name == "treasury_4tier_dataset.csv"


@pytest.mark.skipif(
    os.environ.get("RJ_ML_PRIVATE_DATA_AUDIT") != "true",
    reason="Full-year private dataset includes the reserved partition; not read in integration validation.",
)
def test_committee_dataset_audit():
    audit = audit_committee_dataset()
    assert audit["file_size_bytes"] == 1067472
    assert (
        audit["sha256"]
        == "2e7c1d2e5b678e9975250211e7e0017022049c510e1dd90cd7f29e931837b0c5"
    )
    assert audit["sha256_verified"] is True
    assert audit["row_count"] == 8760
    assert audit["column_count"] == 16
    assert audit["currency"] == "USD"
    assert audit["has_nulls"] is False


def test_parse_history_records_row_limits():
    valid_records = [
        {"timestamp": f"2026-10-01T{i%24:02d}:00:00Z", "deposits": 100.0, "withdrawals": 80.0}
        for i in range(168)
    ]
    obs = parse_history_records(valid_records)
    assert len(obs) == 168

    # Below 168 rows must fail
    with pytest.raises(ValueError, match="at least 168 rows"):
        parse_history_records(valid_records[:167])

    # Above 5000 rows must fail
    too_many = [
        {"timestamp": "2026-10-01T00:00:00Z", "deposits": 100.0, "withdrawals": 80.0}
        for _ in range(5001)
    ]
    with pytest.raises(ValueError, match="at most 5000 rows"):
        parse_history_records(too_many)
