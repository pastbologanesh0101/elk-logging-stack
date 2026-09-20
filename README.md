# ELK Logging Stack

[![tests](https://github.com/pastbologanesh0101/elk-logging-stack/actions/workflows/tests.yml/badge.svg)](https://github.com/pastbologanesh0101/elk-logging-stack/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, real Flask application that emits structured log lines, plus a
complete ELK (Elasticsearch, Logstash, Kibana) configuration wired up to
ingest and parse them.

## Honest limitation: Docker was not run to build this

This project was built in an environment where the **Docker daemon was not
running**, so the Elasticsearch/Logstash/Kibana containers themselves were
never actually started end-to-end here. To compensate, everything that
*can* be verified without Docker was verified:

- `docker-compose.yml` is parsed as YAML and asserted on for correct
  service wiring (Elasticsearch/Logstash/Kibana present, ports exposed,
  `depends_on` relationships, volume mounts) — see `tests/test_config.py`.
- The Logstash grok filter's parsing logic is translated into an equivalent
  Python regex (`logstash/grok_pattern.py`) and tested against real sample
  log lines the app produces, including edge cases (a path with a query
  string, and 4xx/5xx statuses) — see `tests/test_config.py`.
- The Flask app itself is fully real, runs directly with `python -m app.main`,
  and is covered by tests that hit its endpoints and capture its actual log
  output.

If you have Docker available, `docker compose up -d` should bring up the
real stack using the same config files (see "Completing the loop" below).

## Architecture

```
┌─────────────┐   writes    ┌────────────────┐   tails    ┌───────────┐   ships    ┌────────────────┐   visualized in   ┌─────────┐
│  Flask app  │ ──────────► │ app/logs/app.log│ ─────────► │ Logstash  │ ─────────► │ Elasticsearch  │ ─────────────────► │ Kibana  │
└─────────────┘             └────────────────┘            └───────────┘            └────────────────┘                    └─────────┘
```

- **app/main.py** — a Flask app with `/health`, `/orders` (GET/POST),
  `/orders/<id>` and `/boom` (deliberately triggers a 500) endpoints. Every
  request is logged through Python's `logging` module (not `print`) to
  both stdout and `app/logs/app.log`, in one line per request.
- **logstash/logstash.conf** — a `file` input tails `app/logs/app.log`, a
  `grok` filter parses each line into structured fields, and an
  `elasticsearch` output ships the parsed event into a daily index.
- **docker-compose.yml** — wires up Elasticsearch, Logstash (mounting the
  pipeline config and the app's log directory read-only) and Kibana on a
  shared `elk` network.

### Why a `file` input instead of TCP/Beats

The `file` input keeps the whole demo self-contained: the app just writes
to a file, Logstash tails it directly, and there's no extra shipper process
to run. Swapping to a `beats` input (Filebeat sitting in front of Logstash
on port 5044) would be a small, well-understood change for a production
setup with multiple hosts — the `logstash.conf` input block is the only
place that would need to change.

### How `grok_pattern.py` mirrors the real filter

`logstash/logstash.conf`'s `grok` filter and `logstash/grok_pattern.py`
express the *same* pattern in two different engines: Logstash's grok
(built on Oniguruma regex plus named base patterns like
`%{TIMESTAMP_ISO8601}` and `%{WORD}`) and Python's `re`. `grok_pattern.py`
is not imported by the pipeline and does not run inside Logstash at all —
it exists purely so this pattern's *behavior* can be exercised with
`pytest` in an environment without a Logstash process. Each grok base
pattern used in `logstash.conf` has a one-to-one hand-translated regex
group in `grok_pattern.py` (documented in that file's module docstring),
and the `mutate { convert => ... }` block that coerces `status` and
`duration_ms` to integers in the real pipeline has an equivalent
`int(...)` coercion in `parse_log_line`. If the grok pattern in
`logstash.conf` ever changes, `grok_pattern.py`'s regex needs a matching
change or the two will silently drift apart — there is no automated check
tying them together beyond both being tested against the same sample log
lines in `tests/test_config.py`.

## Log line format

The app logs one line per request in this format:

```
TIMESTAMP LEVEL service=app method=METHOD path=PATH status=STATUS duration_ms=DURATION
```

Example:

```
2026-09-18 12:00:01,123 INFO service=app method=GET path=/orders status=200 duration_ms=45
```

The Logstash grok filter parses this into:

| field         | value                  |
|---------------|------------------------|
| `timestamp`   | `2026-09-18 12:00:01,123` |
| `level`       | `INFO`                 |
| `service`     | `app`                  |
| `method`      | `GET`                  |
| `path`        | `/orders`              |
| `status`      | `200` (integer)        |
| `duration_ms` | `45` (integer)         |

An error request (e.g. `GET /orders/9999` → 404, or `GET /boom` → 500) logs
at `WARNING`/`ERROR` level respectively, and a path with a query string
(e.g. `/orders?limit=5&sort=asc`) is captured verbatim in the `path` field —
both cases are covered by the grok-pattern tests.

## Running the app directly

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

The app listens on `http://localhost:5000`. Try it:

```bash
curl http://localhost:5000/health
curl http://localhost:5000/orders
curl -X POST http://localhost:5000/orders -H 'Content-Type: application/json' -d '{"item": "mouse", "qty": 3}'
curl http://localhost:5000/boom
```

Log lines will appear on stdout and accumulate in `app/logs/app.log`.

Set the `LOG_LEVEL` env var (e.g. `LOG_LEVEL=DEBUG python -m app.main`) to
raise or lower the app's log verbosity; it accepts any standard `logging`
level name and falls back to `INFO` if unset or invalid.

## Completing the loop with Docker

Once Docker is available:

```bash
docker compose up -d          # starts Elasticsearch, Logstash, Kibana
python -m app.main            # in another terminal — generates log traffic
curl http://localhost:5000/orders   # a few times, to produce log lines
```

Logstash will tail `app/logs/app.log`, parse each line, and ship it to
Elasticsearch. Open Kibana at `http://localhost:5601`, create a data view
over the `elk-logging-stack-*` index pattern, and the parsed fields
(`level`, `method`, `path`, `status`, `duration_ms`, ...) will be available
to search and visualize.

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

22 tests in total:

- `tests/test_app.py` — the Flask app's endpoints and its actual emitted log
  output (captured via a logging handler and asserted against the
  documented format), including 2xx/4xx/5xx paths and a query-string case.
- `tests/test_config.py` — `docker-compose.yml` structural validation, and
  the grok pattern (translated to Python regex) tested against real sample
  log lines, including a query-string path and 4xx/5xx statuses.

CI (`.github/workflows/tests.yml`) runs the full suite on push/PR against
Python 3.11, 3.12 and 3.13, with no Docker dependency.

## Troubleshooting / FAQ

**I have Docker running — how do I actually verify this end-to-end?**
Run `docker compose up -d`, wait for `docker compose ps` to show
`elasticsearch` as healthy (it has a `healthcheck` that curls
`/_cluster/health`; Logstash and Kibana don't wait for it automatically,
so give it 20-30s), then run the app (`python -m app.main`) and hit a few
endpoints with `curl`. Check `docker logs elk-logstash` for a line like
`Pipeline started` and no `_grokparsefailure` lines, then confirm data
landed with `curl http://localhost:9200/elk-logging-stack-*/_search`
before bothering to open Kibana.

**Why do the tests validate YAML structure instead of starting containers?**
Because the containers were never started in this environment (see
"Honest limitation" above) — there was no Docker daemon to start them
against. Structural YAML checks and the Python-regex mirror of the grok
pattern are what's actually verifiable without Docker, so that's what
`tests/test_config.py` checks. They catch a wrong port, a missing
`depends_on`, or a grok field that stops matching a real log line; they
cannot catch a typo'd Elasticsearch index template or a Kibana version
mismatch, which only show up when the real stack runs.

**My log line isn't showing up as parsed data in Kibana — why?**
The most common cause is the line not matching
`logstash/logstash.conf`'s grok pattern at all, which Logstash reports as
a `_grokparsefailure` tag on the event rather than a dropped line —
check `docker logs elk-logstash` for it. That pattern expects the *exact*
format `TIMESTAMP LEVEL service=app method=METHOD path=PATH
status=STATUS duration_ms=DURATION` with single spaces between fields; a
stray `print()` statement anywhere in the app (instead of going through
`logger`) will write a line to stdout that never reaches
`app/logs/app.log` at all, and therefore never reaches Logstash either.

**Why does `path` capture the whole query string instead of just the route?**
By design — `%{NOTSPACE:path}` (translated as `\S+` in
`logstash/grok_pattern.py`) matches anything up to the next space, so
`/orders?limit=5&sort=asc` is captured verbatim in one field rather than
split into a route and query params. If you need them split in
Elasticsearch, add a `kv` or `dissect` filter on the `path` field in
`logstash.conf` after the grok filter.

## Project layout

```
app/
  main.py            Flask app + logging setup
  logs/              app.log written here at runtime (gitignored)
logstash/
  logstash.conf       Logstash pipeline: file input -> grok filter -> ES output
  grok_pattern.py     Python regex translation of the grok pattern, for testing
docker-compose.yml    Elasticsearch + Logstash + Kibana
tests/
  test_app.py         Flask app + logging tests
  test_config.py       docker-compose + grok pattern tests
.github/workflows/
  tests.yml           CI: pytest on 3.11 and 3.12
```

## License

MIT — see [LICENSE](LICENSE).
