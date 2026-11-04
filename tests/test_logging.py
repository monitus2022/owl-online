"""Logging setup: request-id context and idempotent handler install."""

import logging

from app.logging import configure_logging, get_request_id, set_request_id


def test_request_id_round_trips():
    set_request_id("abc123")
    assert get_request_id() == "abc123"


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    configure_logging("INFO")
    after_first = len(root.handlers)
    configure_logging("DEBUG")
    configure_logging("INFO")
    assert len(root.handlers) == after_first
    assert root.level == logging.INFO
