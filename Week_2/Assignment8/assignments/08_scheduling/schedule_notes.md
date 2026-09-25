# Assignment 8 — Scheduled Local Run: Notes

## What was built

| File | Purpose |
|---|---|
| `scheduler.py` | APScheduler setup; registers jobs and the event listener |
| `fixture_source.py` | Local disk-based source adapter; no network required |
| `fixture_events.html` | 6 fake IISER-style event cards used as fixture data |

One small patch to `src/runner.py`:
- Added optional `"fetcher"` key in source config so a source can supply its own fetch function (disk reader, mock, etc.) instead of the default `fetch()` network call. The generic runner is otherwise unchanged.

---

## APScheduler version

**3.10.4** (pinned). APScheduler 4.x has a completely different API; v3.x is what this project uses.

---

## Schedule configuration

| Job ID | Source | Trigger | Interval | max_instances |
|---|---|---|---|---|
| `fixture_events_immediate` | fixture_events | `date` (one-shot at startup) | — | 1 |
| `fixture_events` | fixture_events | `interval` | 30 s (demo) | 1 |
| `iiserpune_events` | iiserpune_events | `interval` | 6 h (commented out) | 1 |

`max_instances=1` is the key guard. APScheduler will skip a trigger if the
previous run for that job is still in progress, rather than stacking jobs.

---

## Observed log output — live run on Windows (3 interval fires + Ctrl+C)

```
2026-09-25T17:22:17  INFO  scheduler    SCHEDULER starting up (APScheduler 3.10.4)
2026-09-25T17:22:17  INFO  scheduler    Running fixture source — press Ctrl+C to stop after ~2 runs
2026-09-25T17:22:21  INFO  scheduler    REGISTERED job=fixture_events interval=30s

# Fire 1 — immediate (job_id=fixture_events_immediate)
2026-09-25T17:22:21  INFO  scheduler    SCHEDULED RUN starting source=fixture_events
2026-09-25T17:22:21  INFO  web_monitor  START source=fixture_events
2026-09-25T17:22:21  INFO  web_monitor  FETCH url=file://fixture_events.html status=200
2026-09-25T17:22:21  INFO  web_monitor  PARSE records=6 source=fixture_events
2026-09-25T17:22:21  INFO  web_monitor  NORMALIZE records=6 source=fixture_events
2026-09-25T17:22:21  INFO  web_monitor  STORE new=6 unchanged=0 updated=0 errors=0 source=fixture_events
2026-09-25T17:22:21  INFO  web_monitor  END source=fixture_events duration_ms=171
2026-09-25T17:22:21  INFO  scheduler    JOB OK job_id=fixture_events_immediate new=6 unchanged=0 updated=0 errors=0 duration_ms=171

# Fire 2 — interval at t+30s (job_id=fixture_events)
2026-09-25T17:22:51  INFO  scheduler    SCHEDULED RUN starting source=fixture_events
2026-09-25T17:22:51  INFO  web_monitor  START source=fixture_events
2026-09-25T17:22:51  INFO  web_monitor  FETCH url=file://fixture_events.html status=200
2026-09-25T17:22:51  INFO  web_monitor  PARSE records=6 source=fixture_events
2026-09-25T17:22:51  INFO  web_monitor  NORMALIZE records=6 source=fixture_events
2026-09-25T17:22:51  INFO  web_monitor  STORE new=0 unchanged=6 updated=0 errors=0 source=fixture_events
2026-09-25T17:22:51  INFO  web_monitor  END source=fixture_events duration_ms=127
2026-09-25T17:22:51  INFO  scheduler    JOB OK job_id=fixture_events new=0 unchanged=6 updated=0 errors=0 duration_ms=127

# Fire 3 — interval at t+60s (job_id=fixture_events)
2026-09-25T17:23:21  INFO  scheduler    SCHEDULED RUN starting source=fixture_events
2026-09-25T17:23:21  INFO  web_monitor  START source=fixture_events
2026-09-25T17:23:21  INFO  web_monitor  FETCH url=file://fixture_events.html status=200
2026-09-25T17:23:21  INFO  web_monitor  PARSE records=6 source=fixture_events
2026-09-25T17:23:21  INFO  web_monitor  NORMALIZE records=6 source=fixture_events
2026-09-25T17:23:21  INFO  web_monitor  STORE new=0 unchanged=6 updated=0 errors=0 source=fixture_events
2026-09-25T17:23:21  INFO  web_monitor  END source=fixture_events duration_ms=130
2026-09-25T17:23:21  INFO  scheduler    JOB OK job_id=fixture_events new=0 unchanged=6 updated=0 errors=0 duration_ms=130

2026-09-25T17:23:40  INFO  scheduler    SCHEDULER shutting down — goodbye
```

**Fire 1 (immediate):** `new=6` — first time these records hit the DB.  
**Fire 2 (t+30s):** `unchanged=6` — idempotency confirmed; zero duplicates created.  
**Fire 3 (t+60s):** `unchanged=6` — consistent across repeated interval fires.  
**Ctrl+C at t+79s:** scheduler shut down cleanly.

---

## Questions

**1. What prevents overlapping runs?**  
`max_instances=1` on each `add_job()` call. APScheduler tracks how many concurrent
instances of a job are running and refuses to fire a new one if the limit is already
reached. A misfire grace window (`misfire_grace_time`) lets the job fire late if it
just barely missed its trigger.

**2. What happens if a scheduled run fails?**  
The `_on_job_event` listener catches `EVENT_JOB_ERROR` events and logs them at `ERROR`
level with the job ID and exception. The scheduler itself keeps running — one failed
job does not bring down other jobs or future runs of the same job.

**3. How can you change the schedule without touching the parser?**  
Edit the `trigger` arguments in `scheduler.py`. The parser lives in
`sources/iiser_pune.py` and `fixture_source.py`. They share no code with the scheduler.

**4. What cadence would be appropriate for IISER Pune in production?**  
The events page doesn't update more than once or twice a day. A 6-hour interval is
polite and sufficient. Daily would also be fine. Sub-hourly would be wasteful and
impolite.

**5. Why demo against fixture rather than live site?**  
The assignment spec says: *"Demonstrate first against a local fixture or a local test
source."* It avoids hammering the live site during development and keeps test results
deterministic.

---

## What is generic vs source-specific

| Generic (unchanged across sources) | Source-specific |
|---|---|
| `src/runner.py` — pipeline orchestration | `fixture_source.py` — parser, fetcher, config |
| `src/storage.py` — upsert / dedup | `sources/iiser_pune.py` — parser, normalizer |
| `src/logging_config.py` — logger factory | `fixture_events.html` — test data |
| `scheduler.py` — job wiring and timing | Schedule cadence per source |

The scheduler knows only about source config dicts and `run_source()`. It has zero
knowledge of selectors, HTML structure, or normalization logic.

---

## To run

```bash
# From inside the assignment folder
python scheduler.py
```

Press `Ctrl+C` after ~35 seconds to see the immediate fire and the first interval fire.  
Let it run to ~65 seconds to see two interval fires.

To enable live IISER Pune crawling, uncomment the `iiserpune_events` block in `scheduler.py`.
