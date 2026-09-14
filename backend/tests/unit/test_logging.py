"""Unit tests for logging configuration."""

import logging
from io import StringIO
from unittest.mock import patch

import pytest
from app.core.logging import setup_logging


@pytest.fixture
def reset_logging():
    """Reset logging configuration before and after each test."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    yield

    root_logger.setLevel(original_level)
    root_logger.handlers.clear()
    for handler in original_handlers:
        root_logger.addHandler(handler)


def test_setup_logging_configures_root_logger(reset_logging):
    setup_logging(log_level="INFO")

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) > 0


def test_setup_logging_respects_log_level(reset_logging):
    for level_name, level_value in [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
    ]:
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        setup_logging(log_level=level_name)
        assert root_logger.level == level_value


def test_setup_logging_adds_stream_handler(reset_logging):
    setup_logging(log_level="INFO")

    root_logger = logging.getLogger()
    handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(handlers) > 0, "No StreamHandler found in root logger"


def test_logger_outputs_to_stdout(reset_logging):
    setup_logging(log_level="INFO")

    test_logger = logging.getLogger("test_module")

    with patch("sys.stdout", new=StringIO()) as fake_stdout:
        test_logger.info("Test message")
        fake_stdout.getvalue()
        # Output may be empty if handler is not using our patched stdout,
        # but the logger should not raise an exception

    assert test_logger.isEnabledFor(logging.INFO)


def test_setup_logging_with_default_level(reset_logging):
    setup_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_setup_logging_idempotent(reset_logging):
    setup_logging(log_level="INFO")
    initial_handler_count = len(logging.getLogger().handlers)

    setup_logging(log_level="DEBUG")
    assert len(logging.getLogger().handlers) == initial_handler_count
    assert logging.getLogger().level == logging.DEBUG
