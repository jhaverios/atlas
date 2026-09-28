"""The nightly lens run scores every session it missed, not just the newest one.

Sessions are the NSE days of the 2026-09 Kite outage (journal last scored Tue 8 Sept).
No DB — ``catchup_plan`` is the selection rule alone.
"""

from __future__ import annotations

from datetime import date

import pytest

from scripts.lens_daily import MAX_CATCHUP_SESSIONS, catchup_plan

pytestmark = pytest.mark.unit

OUTAGE = [date(2026, 9, d) for d in (9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25, 28)]


def test_an_ordinary_night_keeps_the_single_session_path() -> None:
    assert catchup_plan([date(2026, 9, 28)]) is None


def test_a_rerun_with_nothing_missed_keeps_the_single_session_path() -> None:
    assert catchup_plan([]) is None


def test_after_an_outage_every_missed_session_is_scored_oldest_first() -> None:
    assert catchup_plan(OUTAGE) == OUTAGE


def test_the_catchup_is_bounded_and_keeps_the_newest_sessions() -> None:
    long_gap = [date(2026, 7, 1 + i) for i in range(20)] + OUTAGE
    plan = catchup_plan(long_gap)
    assert plan is not None
    assert len(plan) == MAX_CATCHUP_SESSIONS
    assert plan[-1] == date(2026, 9, 28)
