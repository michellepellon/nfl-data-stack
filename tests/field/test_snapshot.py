# ABOUTME: Unit tests for the pinned nflverse schedules snapshot loader.
# ABOUTME: Checks the committed extract loads intact and that tampering is detected via sha256.
import json
import shutil

import pytest

from nflds.snapshot import COLUMNS, SNAPSHOT_PATH, load_snapshot, manifest_path


def test_committed_snapshot_loads_with_expected_shape():
    df = load_snapshot()
    assert df.columns == COLUMNS
    assert sorted(df["season"].unique().to_list()) == list(range(2015, 2026))
    assert df["game_id"].n_unique() == df.height
    manifest = json.loads(manifest_path(SNAPSHOT_PATH).read_text())
    assert manifest["rows"] == df.height
    assert set(manifest) == {"sha256", "rows", "retrieved_at_utc", "nflreadpy_version"}


def test_corrupted_parquet_raises_sha256_mismatch(tmp_path):
    copy = tmp_path / SNAPSHOT_PATH.name
    shutil.copy(SNAPSHOT_PATH, copy)
    shutil.copy(manifest_path(SNAPSHOT_PATH), manifest_path(copy))
    raw = bytearray(copy.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    copy.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_snapshot(copy)


def test_wrong_manifest_raises_sha256_mismatch(tmp_path):
    copy = tmp_path / SNAPSHOT_PATH.name
    shutil.copy(SNAPSHOT_PATH, copy)
    manifest = json.loads(manifest_path(SNAPSHOT_PATH).read_text())
    manifest["sha256"] = "0" * 64
    manifest_path(copy).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_snapshot(copy)
