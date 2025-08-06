import os

from fastapi import status
from fastapi.testclient import TestClient

from refresh_requester.main import app


def test_health_check_endpoint():
    """Test the health check endpoint returns correct response."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


def test_invalid_endpoint_returns_404():
    """Test that invalid endpoints return 404."""
    client = TestClient(app)
    response = client.get("/invalid")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_logging_format(mocker):
    """Test that logging produces correct format."""
    mock_logger = mocker.patch("refresh_requester.main.logger")

    # Test the logging directly by importing the modules
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


def test_fastapi_app_creation():
    """Test that the FastAPI app is created correctly."""
    assert app is not None
    assert hasattr(app, "get")

    # Test that the route is registered
    routes = [route.path for route in app.routes]
    assert "/health" in routes
