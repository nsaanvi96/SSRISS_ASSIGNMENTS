"""
assignments/08_scheduling/scheduler.py
Assignment 8 — Scheduled Local Run

Wraps the generic run_source() runner with APScheduler so sources
execute automatically at defined intervals without manual triggering.

Design decisions:
    - Scheduler owns *only* job registration and timing.
    - No selectors, parsers, or source logic live here.
    - max_instances=1 prevents overlapping runs of the same source.
    - A job failure is logged and reported; the scheduler keeps running.
    - The fixture source runs every 30 s in demo mode so results are
      visible quickly. The real IISER Pune source is registered but
      commented out — uncomment when live crawling is appropriate.

APScheduler version pinned: 3.10.4
"""

import sys
import time
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow imports from src/ and sources/ regardless of where this script
# is invoked from.
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "sources"))
sys.path.insert(0, str(ROOT / "assignments" / "08_scheduling"))

from runner import run_source          # noqa: E402 — after path setup
from logging_config import get_logger  # noqa: E402
from fixture_source import SOURCE as FIXTURE_SOURCE  # noqa: E402

# Uncomment to also schedule the real IISER Pune source.
# from iiser_pune import SOURCE as IISER_SOURCE

logger = get_logger("scheduler")

# ── Event listener ────────────────────────────────────────────────────────────

def _on_job_event(event):
    """
    APScheduler fires this after every job execution.
    Logs success or failure without crashing the scheduler.
    """
    if event.exception:
        logger.error(
            "JOB FAILED job_id=%s exception=%s",
            event.job_id,
            event.exception,
        )
    else:
        retval = event.retval or {}
        logger.info(
            "JOB OK job_id=%s new=%s unchanged=%s updated=%s errors=%s duration_ms=%s",
            event.job_id,
            retval.get("new", "?"),
            retval.get("unchanged", "?"),
            retval.get("updated", "?"),
            retval.get("errors", "?"),
            retval.get("duration_ms", "?"),
        )


# ── Job wrapper ───────────────────────────────────────────────────────────────

def _run_with_logging(source_config: dict):
    """
    Thin wrapper so APScheduler can call run_source with a named config.
    Any uncaught exception is re-raised so the event listener sees it.
    """
    logger.info("SCHEDULED RUN starting source=%s", source_config["name"])
    return run_source(source_config)


# ── Main ──────────────────────────────────────────────────────────────────────

def build_scheduler() -> BlockingScheduler:
    """
    Register all sources and return a configured (but not started) scheduler.
    Separating build from start makes the scheduler testable.
    """
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # ── Fixture source — runs every 30 seconds (demo cadence) ─────────────────
    scheduler.add_job(
        func=_run_with_logging,
        args=[FIXTURE_SOURCE],
        trigger="interval",
        seconds=30,
        id="fixture_events",
        name="Fixture Events (local demo)",
        max_instances=1,   # <-- prevents overlapping runs
        misfire_grace_time=10,
        replace_existing=True,
    )
    logger.info("REGISTERED job=fixture_events interval=30s")

    # ── Real IISER Pune source — runs every 6 hours ────────────────────────────
    # Uncomment when live crawling is appropriate.
    #
    # scheduler.add_job(
    #     func=_run_with_logging,
    #     args=[IISER_SOURCE],
    #     trigger="interval",
    #     hours=6,
    #     id="iiserpune_events",
    #     name="IISER Pune Events",
    #     max_instances=1,
    #     misfire_grace_time=120,
    #     replace_existing=True,
    # )
    # logger.info("REGISTERED job=iiserpune_events interval=6h")

    return scheduler


if __name__ == "__main__":
    logger.info("SCHEDULER starting up (APScheduler 3.10.4)")
    logger.info("Running fixture source — press Ctrl+C to stop after ~2 runs")

    scheduler = build_scheduler()

    # Fire the fixture job once immediately so results appear without waiting
    # the first full interval.
    scheduler.add_job(
        func=_run_with_logging,
        args=[FIXTURE_SOURCE],
        trigger="date",
        id="fixture_events_immediate",
        name="Fixture Events (immediate fire)",
        max_instances=1,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("SCHEDULER shutting down — goodbye")
