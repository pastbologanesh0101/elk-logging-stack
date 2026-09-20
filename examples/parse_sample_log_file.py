"""
Example: parse a whole log file the way the Logstash pipeline would,
using the pure-Python mirror of the grok filter (logstash/grok_pattern.py).

This is a realistic variant of what `logstash.conf`'s `file` input does
line-by-line, but runnable without Docker/Logstash: read every line from
a log file, parse it, and report both the structured events and any
lines that failed to parse (Logstash would tag these `_grokparsefailure`
instead of dropping them silently).

Usage:

    python -m examples.parse_sample_log_file [path/to/app.log]

With no argument, it parses a handful of representative lines instead of
requiring app/logs/app.log to already exist (that file is gitignored and
only appears once the Flask app has actually been run).
"""

import sys

from logstash.grok_pattern import parse_log_line

SAMPLE_LOG_LINES = [
    "2026-09-18 12:00:01,123 INFO service=app method=GET path=/orders status=200 duration_ms=45",
    "2026-09-18 12:00:05,001 INFO service=app method=POST path=/orders status=201 duration_ms=12",
    "2026-09-18 12:00:09,555 WARNING service=app method=GET path=/orders/9999 status=404 duration_ms=3",
    "2026-09-18 12:00:11,999 ERROR service=app method=GET path=/boom status=500 duration_ms=1",
    "",  # a blank line, e.g. trailing newline at EOF - should be skipped, not crash
    "not a log line the app ever produced",  # simulates a _grokparsefailure
]


def parse_lines(lines):
    """Parse an iterable of raw log lines, returning (events, failures)."""
    events = []
    failures = []
    for raw_line in lines:
        fields = parse_log_line(raw_line)
        if fields is None:
            if raw_line.strip():
                failures.append(raw_line)
            continue
        events.append(fields)
    return events, failures


def main(argv):
    if len(argv) > 1:
        with open(argv[1]) as f:
            lines = f.readlines()
        source = argv[1]
    else:
        lines = SAMPLE_LOG_LINES
        source = "built-in sample lines"

    events, failures = parse_lines(lines)

    print(f"Parsed {len(events)} event(s) from {source}:")
    for event in events:
        print(
            f"  {event['timestamp']} [{event['level']:<7}] "
            f"{event['method']:<6} {event['path']:<20} "
            f"status={event['status']} duration_ms={event['duration_ms']}"
        )

    if failures:
        print(f"\n{len(failures)} line(s) would have failed grok parsing "
              f"(tagged _grokparsefailure by real Logstash):")
        for line in failures:
            print(f"  {line!r}")

    error_count = sum(1 for e in events if e["level"] == "ERROR")
    if events:
        print(f"\n{error_count}/{len(events)} parsed events were at ERROR level.")


if __name__ == "__main__":
    main(sys.argv)
