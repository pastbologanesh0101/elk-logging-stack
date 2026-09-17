"""
Python regex translation of the grok filter used in logstash/logstash.conf.

The grok pattern is:

    %{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} service=%{WORD:service} \
    method=%{WORD:method} path=%{NOTSPACE:path} status=%{NONNEGINT:status} \
    duration_ms=%{NONNEGINT:duration_ms}

This module is not used by the running Logstash pipeline (Logstash has its
own grok/Oniguruma engine); it exists so the pipeline's parsing behavior can
be verified with plain Python + `re` in an environment where Docker/Logstash
itself cannot be run (see README.md). Each named group below corresponds
directly to a grok field, and the sub-patterns are direct translations of
the underlying grok base patterns:

    TIMESTAMP_ISO8601  -> \\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2}:\\d{2}[.,]\\d+
    LOGLEVEL            -> [A-Za-z]+           (INFO / WARN(ING) / ERROR / DEBUG ...)
    WORD                -> \\w+
    NOTSPACE            -> \\S+
    NONNEGINT           -> \\d+
"""

import re

GROK_EQUIVALENT_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[.,]\d+) "
    r"(?P<level>[A-Za-z]+) "
    r"service=(?P<service>\w+) "
    r"method=(?P<method>\w+) "
    r"path=(?P<path>\S+) "
    r"status=(?P<status>\d+) "
    r"duration_ms=(?P<duration_ms>\d+)$"
)


def parse_log_line(line):
    """Parse one app log line, returning a dict of extracted fields (with
    status/duration_ms coerced to int, mirroring the mutate filter in
    logstash.conf), or None if the line does not match.
    """
    match = GROK_EQUIVALENT_REGEX.match(line.strip())
    if not match:
        return None
    fields = match.groupdict()
    fields["status"] = int(fields["status"])
    fields["duration_ms"] = int(fields["duration_ms"])
    return fields
