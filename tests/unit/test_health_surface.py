"""The Admin "Data status" tab must show EXACTLY the tables the freshness guard watches.

Same anti-drift idea as test_producer_registry, one layer up: the data-health tab reads two
hand-maintained lists in health.ts (FOUNDATION_TABLES = derived, SOURCE_TABLES = raw feeds).
If a new producer is added to the guard but not surfaced here (or a dropped table lingers),
the operator dashboard silently lies about coverage. This asserts the tab's union equals the
guard's KEY_TABLES + BOARD_TABLES, so that drift is a red CI check, not a stale dashboard.

Pure filesystem — parses health.ts, no DB, no network.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HEALTH_TS = _REPO / "frontend" / "src" / "lib" / "queries" / "health.ts"


def _guard_tables() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "freshness_guard", _REPO / "scripts" / "ops" / "freshness_guard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {t for t, _c, _l in mod.KEY_TABLES + mod.BOARD_TABLES}


def _ts_array_body(const: str) -> str:
    """The [...] literal body of `const <NAME> ... = [ ... ]` in health.ts."""
    m = re.search(rf"const {const}\b.*?=\s*\[(.*?)\n\]", _HEALTH_TS.read_text(), re.S)
    assert m, f"{const} not found in health.ts"
    return m.group(1)


def _data_status_surface() -> set[str]:
    foundation = set(re.findall(r"table:\s*'([a-z0-9_]+)'", _ts_array_body("FOUNDATION_TABLES")))
    source = set(re.findall(r"name:\s*'([a-z0-9_]+)'", _ts_array_body("SOURCE_TABLES")))
    return foundation | source


@pytest.mark.unit
def test_data_status_tab_shows_exactly_the_guarded_tables():
    guard, surface = _guard_tables(), _data_status_surface()
    missing = guard - surface  # guarded but not shown on the tab (the silent-lie case)
    extra = surface - guard  # shown but not guarded (dropped/renamed table lingering)
    assert not missing, f"data-status tab is missing guarded table(s): {sorted(missing)}"
    assert not extra, f"data-status tab lists non-guarded table(s): {sorted(extra)}"


def _snapshot():
    """India's write_health_snapshot module (it imports _db: put scripts/foundation on the path)."""
    import sys

    sys.path.insert(0, str(_REPO / "scripts" / "foundation"))
    spec = importlib.util.spec_from_file_location(
        "write_health_snapshot", _REPO / "scripts" / "ops" / "write_health_snapshot.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snapshot_gates() -> dict[str, str]:
    return _snapshot()._GATE_VALIDATORS


@pytest.mark.unit
def test_the_health_status_reads_every_nightly_gate_under_the_name_it_is_written():
    """A gate the snapshot never records can fail with /health green; a name the status reads
    that nothing writes is a card saying "No data" forever. The retired M3-M5 were the second
    kind, and their last results kept every page's health dot red for three months."""
    orchestrator = (_REPO / "scripts" / "ops" / "atlas_daily.sh").read_text()
    gates = set(re.findall(r'^gate "([A-Za-z0-9_]+)"', orchestrator, re.M))
    written = _snapshot_gates()
    assert gates == set(written), f"gates vs snapshot map: {sorted(gates ^ set(written))}"
    read = set(re.findall(r"key:\s*'([A-Za-z0-9_]+)'", _ts_array_body("GATE_VALIDATORS")))
    assert read == set(written.values()), (
        f"status reads {sorted(read)}, snapshot writes {sorted(written.values())}"
    )


@pytest.mark.unit
def test_a_failure_reason_reaches_the_public_board_without_its_credentials():
    """The reason is rendered on the open board. The first line is the real one that sat in a
    box log from 9 to 25 Sept 2026; it must survive untouched. The other two are the shapes a
    traceback leaks in (requests' URL with its key, a driver's DSN)."""
    redact = _snapshot().redact
    real = "rc=1: ModuleNotFoundError: No module named 'pyotp'"
    assert redact(real) == real
    fred = "403 for url: https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=abc123&file_type=json"
    assert redact(fred).endswith("series_id=DGS10&api_key=***&file_type=json")
    dsn = "could not connect: postgresql://postgres.ref:hunter2@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    assert "hunter2" not in redact(dsn) and "postgres.ref:***@aws-1" in redact(dsn)
