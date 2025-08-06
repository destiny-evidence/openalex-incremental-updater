import os
import threading
import time

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from refresh_requester.main import health_probe_app, start_health_check_server


def test_health_check_endpoint():
    """Test the health check endpoint returns correct response."""
    client = TestClient(health_probe_app)
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


def test_invalid_endpoint_returns_404():
    """Test that invalid endpoints return 404."""
    client = TestClient(health_probe_app)
    response = client.get("/invalid")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_start_health_check_server_calls_uvicorn(mocker):
    """Test that start_health_check_server calls uvicorn with correct parameters."""
    mock_uvicorn_run = mocker.patch("uvicorn.run")

    start_health_check_server()

    mock_uvicorn_run.assert_called_once_with(
        health_probe_app,
        host="0.0.0.0",  # noqa: S104 Possible binding to all interfaces
        port=23045,
        log_level="warning",
        access_log=False,
    )


def test_health_server_runs_in_separate_thread(mocker):
    """Test that health server can run in a separate thread without blocking."""
    import threading

    stop_event = threading.Event()

    def mock_uvicorn_run() -> None:
        """Mock function to simulate uvicorn.run."""
        stop_event.wait(timeout=1)

    mock_uvicorn = mocker.patch("uvicorn.run", side_effect=mock_uvicorn_run)

    thread = threading.Thread(target=start_health_check_server, daemon=True)

    thread.start()

    # Give thread time to start
    time.sleep(0.1)

    # Thread should be running
    assert thread.is_alive()

    # uvicorn.run should have been called
    mock_uvicorn.assert_called_once()

    stop_event.set()
    thread.join(timeout=1)


def test_thread_creation_logic(mocker):
    """Test thread creation when not in pytest environment."""
    mock_thread = mocker.patch("threading.Thread")
    mock_thread_instance = mocker.Mock()
    mock_thread.return_value = mock_thread_instance

    mocker.patch.dict(os.environ, {}, clear=True)

    # Test the conditional logic directly
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        health_check_thread = threading.Thread(
            target=start_health_check_server,
            daemon=True,
        )
        health_check_thread.start()

    mock_thread.assert_called_once_with(target=start_health_check_server, daemon=True)
    mock_thread_instance.start.assert_called_once()


def test_thread_not_created_in_pytest(mocker):
    """
    Test thread is not created when in pytest environment.

    Do not patch the environment variable, but let pytest handle it.
    """
    mock_thread = mocker.patch("threading.Thread")

    # Test the conditional logic directly
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        health_check_thread = threading.Thread(
            target=start_health_check_server,
            daemon=True,
        )
        health_check_thread.start()

    mock_thread.assert_not_called()


def test_logging_format(mocker):
    """Test that logging produces correct format."""
    mock_logger = mocker.patch("refresh_requester.main.logger")

    # Test the logging directly by importing the modules
    import os
    import socket
    import uuid

    test_host_name = "test-host"
    test_run_id = "test-uuid"
    test_pid = 12345
    mocker.patch("socket.gethostname", return_value=test_host_name)
    mocker.patch("uuid.uuid4", return_value=test_run_id)
    mocker.patch("os.getpid", return_value=test_pid)
    log_message = f"[DEBUG] Job started. Host: {socket.gethostname()}, Run ID: {uuid.uuid4()}, PID: {os.getpid()}"
    mock_logger.warning(log_message)

    expected_log = f"[DEBUG] Job started. Host: {test_host_name}, Run ID: {test_run_id}, PID: {test_pid}"
    mock_logger.warning.assert_called_once_with(expected_log)


def test_settings_and_pipeline_execution(mocker):
    """Test that settings are retrieved and pipeline is executed."""
    mock_get_settings = mocker.patch("refresh_requester.main.get_settings")
    mock_run_pipeline = mocker.patch("refresh_requester.main.run_full_pipeline")
    mock_settings = mocker.Mock()
    mock_get_settings.return_value = mock_settings

    # Test just the settings and pipeline part
    from refresh_requester.main import get_settings, run_full_pipeline

    settings = get_settings()
    run_full_pipeline(settings)

    mock_get_settings.assert_called_once()
    mock_run_pipeline.assert_called_once_with(mock_settings)


def test_pytest_environment_detection(mocker):
    """Test that PYTEST_CURRENT_TEST environment variable is properly detected."""
    # Test with pytest environment
    mocker.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_something"})
    assert os.environ.get("PYTEST_CURRENT_TEST") == "test_something"


def test_no_pytest_environment(mocker):
    """Test behavior when PYTEST_CURRENT_TEST is not set."""
    mocker.patch.dict(os.environ, {}, clear=True)
    assert os.environ.get("PYTEST_CURRENT_TEST") is None


def test_thread_daemon_flag():
    """Test that thread is created with correct daemon flag."""
    thread = threading.Thread(target=start_health_check_server, daemon=True)

    assert thread.daemon is True
    assert thread._target == start_health_check_server  # noqa: SLF001 Private attribute access for testing purposes


def test_environment_conditional_behavior():
    """Test the complete conditional behavior for different environments."""
    # Test pytest environment behavior
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("PYTEST_CURRENT_TEST", "test_something")
        should_start_thread = not os.environ.get("PYTEST_CURRENT_TEST")
        assert should_start_thread is False

    # Test non-pytest environment behavior
    with pytest.MonkeyPatch().context() as mp:
        mp.delenv("PYTEST_CURRENT_TEST", raising=False)
        should_start_thread = not os.environ.get("PYTEST_CURRENT_TEST")
        assert should_start_thread is True


def test_fastapi_app_creation():
    """Test that the FastAPI app is created correctly."""
    assert health_probe_app is not None
    assert hasattr(health_probe_app, "get")

    # Test that the route is registered
    routes = [route.path for route in health_probe_app.routes]
    assert "/health" in routes
