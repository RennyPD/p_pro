"""Structured request logs and a request id on every response."""

import json
import logging

from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter
from main import app


def test_responses_carry_a_request_id():
    with TestClient(app) as client:
        generated = client.get("/health")
        echoed = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert len(generated.headers["X-Request-ID"]) == 32
    assert echoed.headers["X-Request-ID"] == "abc123"


def test_json_formatter_includes_extra_fields_and_exceptions():
    try:
        raise ValueError("fallo de prueba")
    except ValueError:
        record = logging.getLogger("nexo.test").makeRecord(
            "nexo.test",
            logging.ERROR,
            __file__,
            1,
            "database_error",
            (),
            exc_info=__import__("sys").exc_info(),
            extra={"request_id": "r1", "path": "/x"},
        )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "database_error"
    assert payload["request_id"] == "r1"
    assert payload["path"] == "/x"
    assert "fallo de prueba" in payload["exception"]
