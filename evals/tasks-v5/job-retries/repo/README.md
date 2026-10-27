# taskmill

A small background job runner for the PebblePrint shop. Jobs live in one
SQLite file; worker processes poll it, run the handler registered for each
job's kind and record the result. No broker, no Redis.

Built-in job kinds:

| kind              | what it does                                  |
|-------------------|-----------------------------------------------|
| `email.send`      | order confirmations and shipping emails       |
| `image.thumbnail` | preview images for uploaded print files       |
| `webhook.deliver` | order events to partner shops and the lab API |

## Quick start

```sh
export TASKMILL_DB=./dev.db
python -m taskmill enqueue email.send -p '{"to": "me@example.com", "subject": "hi", "body": "test"}'
python -m taskmill work --burst      # run everything that's due, then exit
python -m taskmill stats
```

## How it works

- `taskmill/store.py`: `JobStore`, the only code that touches SQL. Every
  write also appends to `job_events`, which `taskmill show ID` prints.
- `taskmill/worker.py`: `Worker(store, registry, clock).run_once()` claims the
  next due job (highest priority, then oldest `run_at`), runs it, and marks
  it `done` or `failed`.
- `taskmill/registry.py`: maps a kind like `email.send` to a function that
  takes the payload dict.
- `taskmill/clock.py`: the `Clock` seam. Tests use `FakeClock`, which only
  moves when told to.
- `taskmill/supervisor.py`: `taskmill supervise` starts and babysits the
  worker processes.

A job's fields: `status` (queued, running, done, failed, cancelled),
`attempts` (how many times a worker has picked it up), `run_at` (when it is
due; a queued job is not picked up before this), plus timestamps,
`worker_id` and `last_error`.

## Failures

When a handler raises, the job is marked `failed` with the traceback in
`last_error`. Requeue it by hand once the cause is fixed:

```sh
python -m taskmill list --status failed
python -m taskmill requeue 1234          # or --all-failed
```

Automatic retries are on the roadmap.

## Configuration

`config.toml` in the working directory, or `--config PATH`, or
`$TASKMILL_CONFIG`. `$TASKMILL_DB` overrides the database path. See
`taskmill/config.py` for every setting and its default.

## Scaling

taskmill runs a single worker by default. When the queue backs up, raise
`workers` in `config.toml`; the supervisor starts that many processes, all
sharing the one database file. SQLite copes fine with a handful of workers on
one box.

## Development

```sh
python -m pytest
```
