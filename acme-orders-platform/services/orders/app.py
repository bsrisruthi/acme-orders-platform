"""Acme Orders API: a deliberately small service to practise operating."""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

# Readiness flag. Flipped to True at the bottom of this file, once everything
# above has been defined. See docs/decisions.md (D3) for what "ready" means.
app.config["READY"] = False

# In-memory state: lost on restart and NOT shared between processes or
# replicas. A known limitation, see docs/decisions.md (D4).
_orders = []
_orders_lock = threading.Lock()

DEBUG_LOGS = os.environ.get("LOG_LEVEL", "info").lower() == "debug"
QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}  # probe/scrape noise

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["route"],
)


def log_event(event, level="info", **fields):
    """One JSON object per line on stdout."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "level": level,
        "event": event,
        **fields,
    }
    print(json.dumps(record), flush=True)


def route_label():
    """The route template (e.g. /orders), never the raw URL.

    Raw URLs as metric labels create unbounded cardinality: every junk URL a
    scanner sends becomes a new time series.
    """
    rule = request.url_rule
    return rule.rule if rule is not None else "unmatched"


@app.before_request
def start_request():
    g.start = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())


@app.after_request
def finish_request(response):
    duration = time.perf_counter() - g.get("start", time.perf_counter())
    route = route_label()

    REQUEST_COUNT.labels(
        method=request.method, route=route, status_code=str(response.status_code)
    ).inc()
    REQUEST_LATENCY.labels(route=route).observe(duration)

    response.headers["X-Request-ID"] = g.get("request_id", "-")

    if DEBUG_LOGS or request.path not in QUIET_PATHS:
        log_event(
            "http_request",
            request_id=g.get("request_id", "-"),
            method=request.method,
            path=request.path,
            route=route,
            status_code=response.status_code,
            duration_seconds=round(duration, 6),
        )
    return response


@app.errorhandler(Exception)
def handle_error(err):
    if isinstance(err, HTTPException):
        return {"error": err.name}, err.code
    log_event(
        "unhandled_exception",
        level="error",
        request_id=g.get("request_id", "-"),
        error=repr(err),
    )
    return {"error": "internal server error"}, 500


@app.get("/healthz")
def healthz():
    """Liveness: the process is up and able to answer. Checks NO dependencies."""
    return {"status": "ok"}, 200


@app.get("/readyz")
def readyz():
    """Readiness: should this instance receive traffic right now?"""
    if not app.config["READY"]:
        return {"status": "not ready"}, 503
    return {"status": "ready"}, 200


@app.post("/orders")
def create_order():
    payload = request.get_json(silent=True)
    product = payload.get("product") if isinstance(payload, dict) else None
    if not isinstance(product, str) or not product.strip():
        return {"error": "body must be a JSON object with a non-empty string 'product'"}, 400

    with _orders_lock:
        order = {"id": len(_orders) + 1, "order": payload}
        _orders.append(order)
    return order, 201


@app.get("/orders")
def list_orders():
    with _orders_lock:
        return {"orders": list(_orders)}, 200


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


app.config["READY"] = True

if __name__ == "__main__":
    # Local development only. In the container, gunicorn runs the app.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
