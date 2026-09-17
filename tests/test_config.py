"""Validation tests for the ELK stack configuration.

Since the Docker daemon is not available in this environment, the stack
cannot be started end-to-end. These tests instead validate:

  1. docker-compose.yml is well-formed YAML with the expected services and
     wiring (Elasticsearch <- Logstash -> Elasticsearch <- Kibana, ports,
     volumes).
  2. The Logstash grok pattern (translated to an equivalent Python regex in
     logstash/grok_pattern.py) correctly extracts every field from real
     sample log lines the Flask app produces, including edge cases (a path
     with a query string, and 4xx/5xx statuses).
"""

import os
import unittest

import yaml

from logstash.grok_pattern import parse_log_line

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_PATH = os.path.join(REPO_ROOT, "docker-compose.yml")
LOGSTASH_CONF_PATH = os.path.join(REPO_ROOT, "logstash", "logstash.conf")


class DockerComposeConfigTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMPOSE_PATH) as f:
            cls.compose = yaml.safe_load(f)

    def test_compose_file_parses_as_valid_yaml(self):
        self.assertIsInstance(self.compose, dict)
        self.assertIn("services", self.compose)

    def test_compose_defines_all_three_elk_services(self):
        services = self.compose["services"]
        for name in ("elasticsearch", "logstash", "kibana"):
            self.assertIn(name, services)

    def test_elasticsearch_exposes_port_9200(self):
        ports = self.compose["services"]["elasticsearch"]["ports"]
        self.assertTrue(any("9200" in str(p) for p in ports))

    def test_kibana_depends_on_and_points_at_elasticsearch(self):
        kibana = self.compose["services"]["kibana"]
        self.assertIn("elasticsearch", kibana.get("depends_on", []))
        env = kibana.get("environment", [])
        self.assertTrue(any("elasticsearch" in str(e) for e in env))

    def test_logstash_depends_on_elasticsearch_and_mounts_pipeline_config(self):
        logstash = self.compose["services"]["logstash"]
        self.assertIn("elasticsearch", logstash.get("depends_on", []))
        volumes = logstash.get("volumes", [])
        self.assertTrue(any("logstash.conf" in v for v in volumes))
        self.assertTrue(any("app/logs" in v for v in volumes))


class LogstashConfigTestCase(unittest.TestCase):
    def test_logstash_conf_file_exists_and_is_non_empty(self):
        self.assertTrue(os.path.isfile(LOGSTASH_CONF_PATH))
        with open(LOGSTASH_CONF_PATH) as f:
            content = f.read()
        self.assertTrue(len(content.strip()) > 0)

    def test_logstash_conf_has_input_filter_output_blocks(self):
        with open(LOGSTASH_CONF_PATH) as f:
            content = f.read()
        self.assertIn("input {", content)
        self.assertIn("filter {", content)
        self.assertIn("output {", content)
        self.assertIn("grok {", content)
        self.assertIn("elasticsearch {", content)

    def test_logstash_conf_output_targets_elasticsearch_service_name(self):
        with open(LOGSTASH_CONF_PATH) as f:
            content = f.read()
        # Must reference the compose service name, not localhost, since
        # Logstash and Elasticsearch run as separate containers on the same
        # docker-compose network.
        self.assertIn("elasticsearch:9200", content)


class GrokPatternTestCase(unittest.TestCase):
    """Validates the grok filter's parsing logic (mirrored in Python) against
    real sample log lines in the app's documented format.
    """

    def test_parses_standard_get_request_line(self):
        line = "2026-09-18 12:00:01,123 INFO service=app method=GET path=/orders status=200 duration_ms=45"
        fields = parse_log_line(line)
        self.assertIsNotNone(fields)
        self.assertEqual(fields["timestamp"], "2026-09-18 12:00:01,123")
        self.assertEqual(fields["level"], "INFO")
        self.assertEqual(fields["service"], "app")
        self.assertEqual(fields["method"], "GET")
        self.assertEqual(fields["path"], "/orders")
        self.assertEqual(fields["status"], 200)
        self.assertEqual(fields["duration_ms"], 45)

    def test_parses_post_request_line(self):
        line = "2026-09-18 12:00:05,001 INFO service=app method=POST path=/orders status=201 duration_ms=12"
        fields = parse_log_line(line)
        self.assertEqual(fields["method"], "POST")
        self.assertEqual(fields["status"], 201)

    def test_parses_line_with_query_string_in_path(self):
        line = "2026-09-18 12:00:07,222 INFO service=app method=GET path=/orders?limit=5&sort=asc status=200 duration_ms=8"
        fields = parse_log_line(line)
        self.assertIsNotNone(fields)
        self.assertEqual(fields["path"], "/orders?limit=5&sort=asc")
        self.assertEqual(fields["status"], 200)

    def test_parses_4xx_status_line(self):
        line = "2026-09-18 12:00:09,555 WARNING service=app method=GET path=/orders/9999 status=404 duration_ms=3"
        fields = parse_log_line(line)
        self.assertIsNotNone(fields)
        self.assertEqual(fields["level"], "WARNING")
        self.assertEqual(fields["status"], 404)
        self.assertEqual(fields["path"], "/orders/9999")

    def test_parses_5xx_status_line(self):
        line = "2026-09-18 12:00:11,999 ERROR service=app method=GET path=/boom status=500 duration_ms=1"
        fields = parse_log_line(line)
        self.assertIsNotNone(fields)
        self.assertEqual(fields["level"], "ERROR")
        self.assertEqual(fields["status"], 500)
        self.assertEqual(fields["duration_ms"], 1)

    def test_malformed_line_does_not_match(self):
        line = "this is not a log line at all"
        self.assertIsNone(parse_log_line(line))


if __name__ == "__main__":
    unittest.main()
