"""
ELK Logging Stack - sample log-generating Flask application.

Every request is logged to stdout AND to app/logs/app.log in a single-line,
structured-ish format that the Logstash pipeline (logstash/logstash.conf) is
built to parse with a grok filter:

    TIMESTAMP LEVEL service=app method=METHOD path=PATH status=STATUS duration_ms=DURATION

Example:

    2026-09-18 12:00:01,123 INFO service=app method=GET path=/orders status=200 duration_ms=12
"""

import logging
import os
import time
import uuid
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# In-memory "orders" store just so the sample app does something real.
_ORDERS = {
    1: {"id": 1, "item": "keyboard", "qty": 2},
    2: {"id": 2, "item": "monitor", "qty": 1},
}


def _build_logger(log_file=LOG_FILE):
    """Create and return the app's logger, configured with the exact line
    format the Logstash grok/dissect filter expects.

    A distinct logger name/handlers are used (rather than the root logger)
    so tests can attach their own handler and capture output in isolation.
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger("elk_app")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid attaching duplicate handlers if the app module is imported twice
    # (e.g. once by the app, once by tests).
    logger.handlers = []

    # No datefmt is passed deliberately: Python's logging module only
    # appends the ",SSS" millisecond suffix to %(asctime)s when datefmt is
    # left as the default, and that suffix is required to match both the
    # documented log format and the grok TIMESTAMP_ISO8601 pattern.
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s service=app %(message)s",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = _build_logger()


def create_app():
    app = Flask(__name__)

    @app.before_request
    def _start_timer():
        request._start_time = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration_ms = int((time.perf_counter() - getattr(request, "_start_time", time.perf_counter())) * 1000)
        level = "INFO" if response.status_code < 400 else ("WARN" if response.status_code < 500 else "ERROR")
        log_line = (
            "method=%s path=%s status=%s duration_ms=%s"
            % (request.method, request.full_path.rstrip("?") if request.query_string else request.path,
               response.status_code, duration_ms)
        )
        if level == "INFO":
            logger.info(log_line)
        elif level == "WARN":
            logger.warning(log_line)
        else:
            logger.error(log_line)
        return response

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(status="ok"), 200

    @app.route("/orders", methods=["GET"])
    def list_orders():
        return jsonify(orders=list(_ORDERS.values())), 200

    @app.route("/orders/<int:order_id>", methods=["GET"])
    def get_order(order_id):
        order = _ORDERS.get(order_id)
        if order is None:
            return jsonify(error="not found"), 404
        return jsonify(order=order), 200

    @app.route("/orders", methods=["POST"])
    def create_order():
        payload = request.get_json(silent=True) or {}
        item = payload.get("item")
        qty = payload.get("qty")
        if not item or not isinstance(qty, int) or qty <= 0:
            return jsonify(error="item and positive integer qty are required"), 400
        new_id = max(_ORDERS.keys(), default=0) + 1
        _ORDERS[new_id] = {"id": new_id, "item": item, "qty": qty}
        return jsonify(order=_ORDERS[new_id]), 201

    @app.route("/boom", methods=["GET"])
    def boom():
        # Deliberately-triggerable server error, useful for exercising the
        # 5xx / ERROR logging path and the Logstash pipeline's handling of it.
        raise RuntimeError("simulated failure for log demonstration")

    @app.errorhandler(RuntimeError)
    def handle_runtime_error(exc):
        return jsonify(error=str(exc)), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
