# Contributing

Thanks for looking at ELK Logging Stack. This is a small project, so the
process is deliberately lightweight.

## Running the tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

That's it — Docker is **not** required to run or validate the test suite.
`tests/test_app.py` exercises the real Flask app in-process, and
`tests/test_config.py` validates `docker-compose.yml` as YAML and mirrors
the Logstash grok filter in pure Python (see `logstash/grok_pattern.py`).
See the README's "Honest limitation" section for why the project is
structured this way.

If you do have Docker available and want to sanity-check the full stack,
see "Completing the loop with Docker" in the README — that part of the
workflow is not covered by automated tests here and is on you to verify
manually.

## Code style

- Match the existing style: plain `logging` (not `print`) for anything the
  Logstash pipeline is meant to parse, small focused functions, and
  docstrings on modules/classes that explain *why*, not just *what*.
- Keep `app/main.py`'s log line format and `logstash/grok_pattern.py`'s
  regex in sync with `logstash/logstash.conf`'s grok pattern — if you
  change one, update all three plus the "Log line format" table in
  README.md.
- No new dependencies unless they earn their place; the project intentionally
  stays small (`requirements.txt` currently has three entries).

## Submitting changes

1. Fork/branch, make a focused change (one concern per commit/PR).
2. Add or update tests for any behavior change — `pytest -v` must pass.
3. If you touched the log format or the docker-compose wiring, update
   README.md so the docs stay accurate.
4. Open a PR describing what changed and why.
