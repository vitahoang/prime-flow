"""Command line: ``python -m taskmill <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from . import config as config_mod
from .clock import SystemClock, format_ts, parse_ts
from .errors import ConfigError, TaskmillError
from .logging_setup import configure
from .models import Status
from .registry import Registry
from .serialize import PayloadError, dumps, parse_payload
from .store import JobStore
from .worker import Worker

DAY = 86_400.0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taskmill", description="SQLite background job runner")
    p.add_argument("--config", help="path to config.toml")
    p.add_argument("--db", help="database file (overrides config)")
    p.add_argument("--version", action="version", version=f"taskmill {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("enqueue", help="add a job")
    e.add_argument("kind")
    e.add_argument("--payload", "-p", help="JSON object or key=value,key=value")
    when = e.add_mutually_exclusive_group()
    when.add_argument("--at", help="run at this ISO time (UTC if no offset)")
    when.add_argument("--in", dest="delay", type=float, help="run in this many seconds")
    e.add_argument("--priority", type=int, default=0)
    e.add_argument("--queue", default="default")

    ls = sub.add_parser("list", help="list jobs")
    ls.add_argument("--status", choices=[s.value for s in Status])
    ls.add_argument("--kind")
    ls.add_argument("--queue")
    ls.add_argument("--limit", type=int, default=50)
    ls.add_argument("--json", action="store_true")

    sh = sub.add_parser("show", help="show one job and its history")
    sh.add_argument("job_id", type=int)
    sh.add_argument("--json", action="store_true")

    sub.add_parser("stats", help="job counts by status")

    rq = sub.add_parser("requeue", help="put failed or cancelled jobs back in the queue")
    rq.add_argument("job_ids", type=int, nargs="*")
    rq.add_argument("--all-failed", action="store_true")

    c = sub.add_parser("cancel", help="cancel a queued job")
    c.add_argument("job_id", type=int)

    pg = sub.add_parser("purge", help="delete old finished jobs")
    pg.add_argument("--older-than", type=float, help="days (default: purge_after_days)")
    pg.add_argument("--include-failed", action="store_true")

    w = sub.add_parser("work", help="run a single worker in the foreground")
    w.add_argument("--burst", action="store_true", help="exit once nothing is due")
    w.add_argument("--max-jobs", type=int)

    sub.add_parser("supervise", help="run config.workers worker processes")
    sub.add_parser("kinds", help="list registered job kinds")
    return p


def _registry(cfg: config_mod.Config) -> Registry:
    reg = Registry()
    reg.load_modules(cfg.handler_modules)
    return reg


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_mod.load(args.config)
    except ConfigError as exc:
        print(f"taskmill: config error: {exc}", file=sys.stderr)
        return 2
    if args.db:
        cfg.database = args.db
    configure(cfg.log_level)
    clock = SystemClock()

    if args.command == "supervise":
        from .supervisor import Supervisor
        Supervisor(cfg).run()
        return 0
    if args.command == "kinds":
        for kind in _registry(cfg).kinds():
            print(kind)
        return 0

    try:
        with JobStore(cfg.database) as store:
            return _dispatch(args, cfg, store, clock)
    except (TaskmillError, PayloadError) as exc:
        print(f"taskmill: {exc}", file=sys.stderr)
        return 1


def _dispatch(args, cfg, store: JobStore, clock) -> int:
    now = clock.now()
    cmd = args.command

    if cmd == "enqueue":
        run_at = parse_ts(args.at) if args.at else (now + args.delay if args.delay else now)
        job = store.enqueue(args.kind, parse_payload(args.payload), run_at=run_at,
                            priority=args.priority, queue=args.queue, now=now)
        print(job.id)
        return 0

    if cmd == "list":
        jobs = store.list(status=args.status, kind=args.kind, queue=args.queue, limit=args.limit)
        if args.json:
            print(json.dumps([j.to_dict() for j in jobs]))
        else:
            for j in jobs:
                print(j.summary())
        return 0

    if cmd == "show":
        job = store.get_or_raise(args.job_id)
        events = store.events(job.id)
        if args.json:
            print(dumps({"job": job.to_dict(), "events": events}))
            return 0
        print(job.summary())
        print(f"  queue={job.queue} priority={job.priority} run_at={format_ts(job.run_at)}")
        print(f"  started={format_ts(job.started_at)} finished={format_ts(job.finished_at)} worker={job.worker_id or '-'}")
        print(f"  payload={json.dumps(job.payload, sort_keys=True)}")
        for ev in events:
            print(f"  {format_ts(ev['at'])}  {ev['event']:<10} {ev['detail'] or ''}")
        if job.last_error:
            print("  last error:")
            for line in job.last_error.splitlines():
                print(f"    {line}")
        return 0

    if cmd == "stats":
        counts = store.counts()
        width = max(len(k) for k in counts)
        for status, n in counts.items():
            print(f"{status:<{width}}  {n}")
        oldest = store.oldest_due(now)
        if oldest is not None:
            print(f"oldest due job has waited {now - oldest:.0f}s")
        return 0

    if cmd == "requeue":
        ids = list(args.job_ids)
        if args.all_failed:
            ids += [j.id for j in store.list(status="failed", limit=10_000)]
        if not ids:
            print("nothing to requeue", file=sys.stderr)
            return 1
        for job_id in ids:
            store.requeue(job_id, now)
            print(f"requeued #{job_id}")
        return 0

    if cmd == "cancel":
        store.cancel(args.job_id, now)
        print(f"cancelled #{args.job_id}")
        return 0

    if cmd == "purge":
        days = args.older_than if args.older_than is not None else cfg.purge_after_days
        statuses = ["done", "cancelled"] + (["failed"] if args.include_failed else [])
        n = store.purge(now - days * DAY, statuses)
        print(f"purged {n} job(s)")
        return 0

    if cmd == "work":
        worker = Worker(store, _registry(cfg), clock, queues=cfg.queues or None,
                        poll_interval=cfg.poll_interval)
        if args.burst:
            n = worker.drain()
        else:
            n = worker.run_forever(max_jobs=args.max_jobs)
        print(f"ran {n} job(s); {worker.metrics.summary_line()}")
        return 0

    raise AssertionError(f"unhandled command {cmd}")
