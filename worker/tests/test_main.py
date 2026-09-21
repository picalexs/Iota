"""Tests for worker startup module."""

import logging
import math
import threading
from unittest.mock import MagicMock, patch

import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from worker import main as main_module
from worker.chemistry.aer_runtime import AerRuntimeInfo
from worker.exceptions import BackendError


class TestLogQueueDepth:
    def test_log_queue_depth_logs_queue_depth(self, caplog):
        mock_client = MagicMock()
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=5)

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", return_value=mock_queue):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with caplog.at_level(logging.INFO):
                            with patch.object(
                                main_module,
                                "_schedule_next_log",
                                side_effect=lambda *args, **kwargs: None,
                            ):
                                main_module._log_queue_depth("redis://localhost", "default")

        assert "Queue 'default' depth: 5" in caplog.text

    def test_log_queue_depth_closes_redis_client(self):
        mock_client = MagicMock()
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=3)

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", return_value=mock_queue):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with patch.object(
                            main_module,
                            "_schedule_next_log",
                            side_effect=lambda *args, **kwargs: None,
                        ):
                            main_module._log_queue_depth("redis://localhost", "default")

        mock_client.close.assert_called_once()

    def test_log_queue_depth_closes_redis_client_on_exception(self):
        mock_client = MagicMock()

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", side_effect=RuntimeError("Redis down")):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with patch.object(
                            main_module,
                            "_schedule_next_log",
                            side_effect=lambda *args, **kwargs: None,
                        ):
                            main_module._log_queue_depth("redis://localhost", "default")

        mock_client.close.assert_called_once()

    def test_log_queue_depth_handles_redis_unavailable(self, caplog):
        mock_client = MagicMock()

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", side_effect=RuntimeError("Connection refused")):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with caplog.at_level(logging.WARNING):
                            with patch.object(
                                main_module,
                                "_schedule_next_log",
                                side_effect=lambda *args, **kwargs: None,
                            ):
                                main_module._log_queue_depth("redis://localhost", "default")

        assert "Failed to read queue depth" in caplog.text
        assert "Connection refused" in caplog.text

    def test_log_queue_depth_schedules_next_timer_on_success(self):
        mock_client = MagicMock()
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=2)

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", return_value=mock_queue):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with patch.object(main_module, "_schedule_next_log") as mock_schedule:
                            main_module._log_queue_depth("redis://localhost", "default")

        mock_schedule.assert_called_once_with("redis://localhost", "default")

    def test_log_queue_depth_does_not_schedule_on_exception(self):
        mock_client = MagicMock()

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", side_effect=RuntimeError("Connection refused")):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer"):
                        with patch.object(main_module, "_schedule_next_log") as mock_schedule:
                            main_module._log_queue_depth("redis://localhost", "default")

        mock_schedule.assert_not_called()

    def test_log_queue_depth_cancels_previous_timer(self):
        mock_client = MagicMock()
        mock_queue = MagicMock()
        mock_queue.__len__ = MagicMock(return_value=1)

        with patch.object(main_module, "_build_redis_client", return_value=mock_client):
            with patch.object(main_module, "Queue", return_value=mock_queue):
                with patch.object(main_module, "_timer", None):
                    with patch.object(main_module, "_cancel_timer") as mock_cancel:
                        with patch.object(main_module, "_schedule_next_log") as _mock_schedule:
                            main_module._log_queue_depth("redis://localhost", "default")

        mock_cancel.assert_called_once()


class TestCancelTimer:
    def test_cancel_timer_cancels_existing_timer(self):
        mock_timer = MagicMock(spec=threading.Timer)

        with patch.object(main_module, "_timer", mock_timer):
            main_module._cancel_timer()

        mock_timer.cancel.assert_called_once()

    def test_cancel_timer_handles_none(self):
        with patch.object(main_module, "_timer", None):
            main_module._cancel_timer()


class TestScheduleNextLog:
    def test_schedule_next_log_creates_timer(self):
        with patch("threading.Timer") as mock_timer_class:
            mock_timer_instance = MagicMock()
            mock_timer_class.return_value = mock_timer_instance

            with patch.object(main_module, "_timer", None):
                main_module._schedule_next_log("redis://localhost", "default")

        mock_timer_class.assert_called_once()
        call_args = mock_timer_class.call_args
        assert call_args[0][0] == 60  # interval (positional)
        # args are passed as keyword argument
        assert call_args[1]["args"] == ["redis://localhost", "default"]

        mock_timer_instance.daemon = True
        mock_timer_instance.start.assert_called_once()

    def test_schedule_next_log_sets_daemon(self):
        with patch("threading.Timer") as mock_timer_class:
            mock_timer_instance = MagicMock()
            mock_timer_class.return_value = mock_timer_instance

            with patch.object(main_module, "_timer", None):
                main_module._schedule_next_log("redis://localhost", "default")

        mock_timer_instance.daemon = True


class TestMain:
    def test_main_initializes_logging(self, caplog):
        with patch("worker.main.get_settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.log_level = "INFO"
            mock_settings_instance.queue_name = "default"
            mock_settings_instance.redis_url = "redis://localhost"
            mock_settings.return_value = mock_settings_instance

            with patch.object(main_module, "_log_aer_runtime"):
                with patch.object(main_module, "_log_queue_depth"):
                    main_module.main()

        mock_settings.assert_called_once()

    def test_main_schedules_queue_depth_logging(self):
        with patch("worker.main.get_settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.log_level = "INFO"
            mock_settings_instance.queue_name = "default"
            mock_settings_instance.redis_url = "redis://localhost"
            mock_settings.return_value = mock_settings_instance

            with patch.object(main_module, "_log_aer_runtime"):
                with patch.object(main_module, "_log_queue_depth") as mock_log_queue_depth:
                    main_module.main()

            mock_log_queue_depth.assert_called_once()

    def test_main_logs_initialization_message(self, caplog):
        with patch("worker.main.get_settings") as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings_instance.log_level = "INFO"
            mock_settings_instance.queue_name = "default"
            mock_settings_instance.redis_url = "redis://localhost"
            mock_settings.return_value = mock_settings_instance

            with patch.object(main_module, "_log_aer_runtime"):
                with patch.object(main_module, "_log_queue_depth"):
                    with caplog.at_level(logging.INFO):
                        main_module.main()

        assert "Worker initialized for queue 'default'" in caplog.text

    def test_gpu_preflight_fails_when_required_device_is_unavailable(self):
        with patch.object(
            main_module,
            "probe_aer_runtime",
            return_value=AerRuntimeInfo(aer_version="0.17.2", available_devices=("CPU",)),
        ):
            with pytest.raises(BackendError, match="requires Aer GPU support"):
                main_module._log_aer_runtime("GPU")


class TestRedisClientConfig:
    def test_worker_socket_timeout_adds_buffer(self):
        assert math.isclose(main_module._worker_socket_timeout_seconds(420, 60.0), 465.0)

    def test_build_redis_client_for_worker_uses_keepalive_and_buffered_timeout(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost"
        mock_settings.worker_ttl_seconds = 420
        mock_settings.redis_socket_timeout_buffer_seconds = 60.0
        mock_settings.redis_socket_connect_timeout_seconds = 5.0
        mock_settings.redis_health_check_interval_seconds = 30

        with patch("worker.main.get_settings", return_value=mock_settings):
            with patch("worker.main.redis_lib.from_url") as mock_from_url:
                main_module._build_redis_client(blocking_worker=True)

        mock_from_url.assert_called_once_with(
            "redis://localhost",
            health_check_interval=30,
            socket_connect_timeout=5.0,
            socket_keepalive=True,
            socket_timeout=465.0,
        )

    def test_build_redis_client_for_non_blocking_uses_connect_timeout(self):
        mock_settings = MagicMock()
        mock_settings.redis_url = "redis://localhost"
        mock_settings.worker_ttl_seconds = 420
        mock_settings.redis_socket_timeout_buffer_seconds = 60.0
        mock_settings.redis_socket_connect_timeout_seconds = 5.0
        mock_settings.redis_health_check_interval_seconds = 30

        with patch("worker.main.get_settings", return_value=mock_settings):
            with patch("worker.main.redis_lib.from_url") as mock_from_url:
                main_module._build_redis_client(blocking_worker=False)

        mock_from_url.assert_called_once_with(
            "redis://localhost",
            health_check_interval=30,
            socket_connect_timeout=5.0,
            socket_keepalive=True,
            socket_timeout=5.0,
        )


class TestResilientWorker:
    def test_dequeue_timeout_reconnects_and_retries(self):
        initial_connection = MagicMock()
        initial_connection.connection_pool.connection_kwargs = {}
        reconnected_connection = MagicMock()
        worker = main_module.ResilientWorker(
            ["default"],
            connection=initial_connection,
            prepare_for_work=False,
        )
        worker.unsubscribe = MagicMock()
        worker.subscribe = MagicMock()

        with patch.object(
            main_module.Worker,
            "dequeue_job_and_maintain_ttl",
            side_effect=[
                RedisTimeoutError("timed out"),
                ("job", "queue"),
            ],
        ):
            with patch.object(
                main_module, "_build_redis_client", return_value=reconnected_connection
            ):
                with patch.object(
                    worker, "_set_connection", return_value=reconnected_connection
                ) as mock_set_connection:
                    with patch("worker.main.time.sleep") as mock_sleep:
                        result = worker.dequeue_job_and_maintain_ttl(timeout=10)

        assert result == ("job", "queue")
        worker.unsubscribe.assert_called_once()
        initial_connection.close.assert_called_once()
        mock_set_connection.assert_called_once_with(reconnected_connection)
        worker.subscribe.assert_called_once()
        mock_sleep.assert_called_once_with(1.0)


class TestRunWorker:
    def test_run_worker_bootstraps_and_runs_resilient_worker(self):
        mock_settings = MagicMock()
        mock_settings.queue_name = "quantum"
        mock_settings.worker_ttl_seconds = 420
        mock_settings.log_level = "INFO"
        mock_worker = MagicMock()

        with patch("worker.main.get_settings", return_value=mock_settings):
            with patch.object(main_module, "main") as mock_main:
                with patch.object(
                    main_module, "_build_redis_client", return_value="redis-conn"
                ) as mock_build_client:
                    with patch.object(main_module, "recover_interrupted_runs") as mock_recovery:
                        with patch(
                            "worker.main.ResilientWorker", return_value=mock_worker
                        ) as mock_worker_cls:
                            main_module.run_worker()

        mock_main.assert_called_once()
        mock_recovery.assert_called_once_with(
            redis_client="redis-conn",
            worker_ttl_seconds=420,
        )
        mock_build_client.assert_called_once_with(blocking_worker=True)
        mock_worker_cls.assert_called_once_with(
            ["quantum"],
            connection="redis-conn",
            worker_ttl=420,
        )
        mock_worker.work.assert_called_once_with(logging_level="INFO")
        mock_worker.connection.close.assert_called_once()
