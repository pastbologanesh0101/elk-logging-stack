"""Unit tests for the Flask sample app (app/main.py).

Covers: the endpoints behaving correctly, and log lines actually being
emitted in the documented format by capturing the app's logger output
directly (rather than trusting the format is followed).
"""

import logging
import re
import unittest

from app.main import create_app, logger

LOG_LINE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ (INFO|WARNING|ERROR) "
    r"service=app method=\w+ path=\S+ status=\d+ duration_ms=\d+$"
)


class LogCapture(logging.Handler):
    """Minimal handler that stores formatted log records for assertions."""

    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


class FlaskAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

        # Attach a capture handler using the same formatter/format string the
        # app itself configures, so we observe exactly what would be written
        # to app/logs/app.log.
        self.capture = LogCapture()
        self.capture.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s service=app %(message)s",
            )
        )
        logger.addHandler(self.capture)

    def tearDown(self):
        logger.removeHandler(self.capture)

    def test_health_endpoint_returns_200(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_list_orders_returns_seed_data(self):
        response = self.client.get("/orders")
        self.assertEqual(response.status_code, 200)
        orders = response.get_json()["orders"]
        self.assertGreaterEqual(len(orders), 2)

    def test_get_single_order_found(self):
        response = self.client.get("/orders/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["order"]["id"], 1)

    def test_get_single_order_not_found_returns_404(self):
        response = self.client.get("/orders/9999")
        self.assertEqual(response.status_code, 404)

    def test_create_order_success_returns_201(self):
        response = self.client.post("/orders", json={"item": "mouse", "qty": 3})
        self.assertEqual(response.status_code, 201)
        body = response.get_json()["order"]
        self.assertEqual(body["item"], "mouse")
        self.assertEqual(body["qty"], 3)

    def test_create_order_missing_fields_returns_400(self):
        response = self.client.post("/orders", json={"item": "mouse"})
        self.assertEqual(response.status_code, 400)

    def test_boom_endpoint_returns_500(self):
        response = self.client.get("/boom")
        self.assertEqual(response.status_code, 500)

    def test_log_line_emitted_matches_documented_format(self):
        self.capture.lines.clear()
        self.client.get("/orders")
        self.assertEqual(len(self.capture.lines), 1)
        line = self.capture.lines[0]
        self.assertRegex(line, LOG_LINE_RE)
        self.assertIn("method=GET", line)
        self.assertIn("path=/orders", line)
        self.assertIn("status=200", line)

    def test_log_line_for_404_has_warning_level_and_status(self):
        self.capture.lines.clear()
        self.client.get("/orders/9999")
        self.assertEqual(len(self.capture.lines), 1)
        line = self.capture.lines[0]
        self.assertRegex(line, LOG_LINE_RE)
        self.assertIn("WARNING", line)
        self.assertIn("status=404", line)

    def test_log_line_for_500_has_error_level_and_status(self):
        self.capture.lines.clear()
        self.client.get("/boom")
        self.assertEqual(len(self.capture.lines), 1)
        line = self.capture.lines[0]
        self.assertRegex(line, LOG_LINE_RE)
        self.assertIn("ERROR", line)
        self.assertIn("status=500", line)

    def test_log_line_includes_query_string_in_path(self):
        self.capture.lines.clear()
        self.client.get("/orders?limit=5&sort=asc")
        self.assertEqual(len(self.capture.lines), 1)
        line = self.capture.lines[0]
        self.assertIn("path=/orders?limit=5&sort=asc", line)


if __name__ == "__main__":
    unittest.main()
