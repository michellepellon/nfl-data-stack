# ABOUTME: Shared fixtures for the field tests.
# ABOUTME: Everything runs against the committed, sha256-verified nflverse snapshot.
import pytest

from nflds.snapshot import load_snapshot


@pytest.fixture(scope="session")
def snapshot():
    return load_snapshot()
