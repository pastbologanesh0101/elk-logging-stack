# Changelog

## v0.1.0 — Initial release

The initial commit (`c043919`) established the project end to end:

- **Flask app** (`app/main.py`) with `/health`, `/orders` (GET/POST),
  `/orders/<id>`, and `/boom` (deliberately triggers a 500) endpoints,
  logging every request to stdout and to `app/logs/app.log` in a single
  structured line via a dedicated `elk_app` logger (not `print`).
- **Logstash pipeline** (`logstash/logstash.conf`): a `file` input tailing
  `app/logs/app.log`, a `grok` filter parsing the app's log line format
  into `timestamp`, `level`, `service`, `method`, `path`, `status` and
  `duration_ms`, a `date` filter setting `@timestamp`, and an
  `elasticsearch` output shipping to a daily `elk-logging-stack-*` index.
- **`docker-compose.yml`** wiring up Elasticsearch 8.13.4, Logstash 8.13.4
  and Kibana 8.13.4 on a shared `elk` bridge network, with Logstash
  mounting the pipeline config and the app's log directory read-only.
- **`logstash/grok_pattern.py`**: a Python/`re` translation of the grok
  pattern above, used to verify the pipeline's parsing logic without a
  running Logstash instance.
- **Test suite** (`tests/test_app.py`, `tests/test_config.py`): the
  Flask app's endpoints and actual emitted log output, `docker-compose.yml`
  structural validation, and the grok-pattern translation against sample
  log lines including query-string paths and 4xx/5xx statuses.
- **CI** (`.github/workflows/tests.yml`): runs `pytest -v` on push/PR
  against Python 3.11 and 3.12.
- **MIT license** and a README that is explicit about the Docker daemon
  not having been available to actually start the ELK containers in the
  environment this project was built in, and about what was verified
  instead.

No behavior changes since this release yet — see `git log` for
subsequent incremental additions (tests, docs, small fixes) on top of it.
