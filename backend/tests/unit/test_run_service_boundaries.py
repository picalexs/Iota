"""Tests for compatibility boundaries around the run service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.run import RunService


def test_run_control_methods_delegate_to_one_canonical_service() -> None:
    db = MagicMock()
    redis = MagicMock()
    run_id = uuid4()
    paused = object()
    resumed = object()
    child = object()

    with patch("app.services.run_control.RunControlService") as control_class:
        control = control_class.return_value
        control.pause.return_value = paused
        control.resume.return_value = resumed
        control.restart.return_value = (object(), child)
        service = RunService(db)

        assert service.pause(run_id, redis_client=redis) is paused
        assert service.resume(run_id, redis_client=redis) is resumed
        assert service.restart(run_id, redis_client=redis, cancel_active=True) is child

        control_class.assert_called_with(db)
        control.pause.assert_called_once_with(run_id, redis_client=redis)
        control.resume.assert_called_once_with(run_id, redis_client=redis)
        control.restart.assert_called_once_with(
            run_id,
            cancel_active=True,
            redis_client=redis,
        )
