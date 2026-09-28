#!/usr/bin/env python3
"""Atlas daily six-lens scoring — the step that was MISSING from the nightly.

Root cause of the lens-journal staleness (atlas_lens_scores_daily lagged the MVs):
run_pipeline() only ran via the manual historical backfill, never in cron. This thin
daily wrapper scores the latest NSE session so the journal advances every night.
Idempotent: run_pipeline upserts the date then purges that date's stale rows.

Before the target session it also scores every session missed since the journal's newest
date, oldest first. Scoring only "today" turned the 2026-09 Kite outage into a permanent
hole: 9-25 Sept would never have been scored, and the paper portfolios would have replayed
those days with no composite at all. The nightly passes --as-of $EOD, so the catch-up lives
on that path too; a historical --as-of (older than the journal) catches up nothing.

    python scripts/lens_daily.py                 # latest session (+ any missed before it)
    python scripts/lens_daily.py --as-of 2026-06-24
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy.engine import Engine

from atlas.db import get_engine
from atlas.lenses.data.adapters import last_scored_date, latest_trading_day, sessions_after
from atlas.lenses.pipeline import run_pipeline

# A nightly catch-up, not a backfill: an older gap is left for an explicit --as-of run.
MAX_CATCHUP_SESSIONS = 30


def catchup_plan(missed: list[date]) -> list[date] | None:
    """The sessions to score, oldest first — or None for the ordinary single-session night.

    *missed* is every session after the journal's newest date, up to the latest one.
    """
    if len(missed) <= 1:
        return None
    return missed[-MAX_CATCHUP_SESSIONS:]


def _score(as_of: date | None, engine: Engine | None = None) -> int:
    result = run_pipeline(as_of=as_of, engine=engine)
    print(f"lens_daily complete: {result}", flush=True)
    # run_pipeline logs zero-scored without purging; treat 0 scored as a failure so cron alerts.
    scored = result.get("scored") if isinstance(result, dict) else None
    return 0 if (scored is None or scored > 0) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlas daily six-lens scoring")
    ap.add_argument(
        "--as-of",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="NSE session to score (YYYY-MM-DD). Default: latest real session.",
    )
    args = ap.parse_args()

    eng = get_engine()
    last = last_scored_date(eng)
    through = args.as_of or latest_trading_day(eng)
    plan = catchup_plan(sessions_after(eng, last, through) if last else [])
    if plan is None:
        return _score(args.as_of)  # the ordinary night, unchanged

    print(f"lens_daily: catching up {len(plan)} sessions, {plan[0]} → {plan[-1]}", flush=True)
    rc = 0
    for d in plan:
        # One bad day must not cost the rest, least of all the newest: log it, fail the step.
        try:
            rc = max(rc, _score(d, eng))
        except Exception as e:
            print(f"lens_daily: {d} FAILED: {type(e).__name__}: {e}", flush=True)
            rc = 1
    if args.as_of is not None and args.as_of not in plan:
        rc = max(rc, _score(args.as_of, eng))  # a non-session --as-of still refuses, as before
    return rc


if __name__ == "__main__":
    sys.exit(main())
