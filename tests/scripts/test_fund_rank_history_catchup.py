"""The nightly fund-rank append fills the days it missed instead of leaving a hole.

Dates are the 2026-09 Kite outage: stock lenses last scored Tue 8 Sept, then caught up
through Mon 28 Sept. No DB — ``catchup_start`` is the date rule alone.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "foundation"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_fund_rank_history as frh  # noqa: E402  # pyright: ignore[reportMissingImports]

pytestmark = pytest.mark.unit


def test_a_normal_night_ranks_only_the_newest_lens_date() -> None:
    # Ranked through Thu 24 Sept, lenses through Fri 25 Sept: just the Friday.
    assert frh.catchup_start(date(2026, 9, 25), date(2026, 9, 24)) == date(2026, 9, 25)


def test_after_an_outage_it_ranks_from_the_day_after_the_last_ranked_date() -> None:
    assert frh.catchup_start(date(2026, 9, 28), date(2026, 9, 8)) == date(2026, 9, 9)


def test_a_rerun_on_the_same_night_reranks_the_newest_date() -> None:
    assert frh.catchup_start(date(2026, 9, 28), date(2026, 9, 28)) == date(2026, 9, 28)


def test_an_empty_history_starts_at_the_newest_lens_date() -> None:
    assert frh.catchup_start(date(2026, 9, 28), None) == date(2026, 9, 28)
