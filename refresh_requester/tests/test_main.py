import asyncio
from io import StringIO

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from refresh_requester.main import app, lifespan, logger


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


def test_logging_format_works_with_debug(mocker):
    """Test that logging with non-f-string formatting is equivalent to an expected f-string."""
    test_host_name = "test-host"
    test_run_id = "test-uuid"
    test_pid = 12345
    mocker.patch("socket.gethostname", return_value=test_host_name)
    mocker.patch("uuid.uuid4", return_value=test_run_id)
    mocker.patch("os.getpid", return_value=test_pid)

    log_stream = StringIO()
    logger.add(log_stream, format="{message}", level="DEBUG")
    logger.debug(
        "Job started. Host: {}, Run ID: {}, PID: {}",
        test_host_name,
        test_run_id,
        test_pid,
    )

    expected_message = (
        f"Job started. Host: {test_host_name}, Run ID: {test_run_id}, PID: {test_pid}"
    )

    log_stream.seek(0)
    rendered_message = log_stream.read().strip()
    assert (
        rendered_message == expected_message
    ), "Rendered log message matches the expected f-string"


def test_logging_format_works_above_debug(mocker):
    """Test that logging with non-f-string formatting is equivalent to an expected f-string."""
    test_host_name = "test-host"
    test_run_id = "test-uuid"
    test_pid = 12345
    mocker.patch("socket.gethostname", return_value=test_host_name)
    mocker.patch("uuid.uuid4", return_value=test_run_id)
    mocker.patch("os.getpid", return_value=test_pid)

    log_stream = StringIO()
    logger.add(log_stream, format="{message}", level="INFO")
    logger.debug(
        "Job started. Host: {}, Run ID: {}, PID: {}",
        test_host_name,
        test_run_id,
        test_pid,
    )

    expected_message = ""

    log_stream.seek(0)
    assert (
        log_stream.read() == expected_message
    ), "No DEBUG messages should be logged at INFO level"


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


@pytest.mark.asyncio
async def test_lifespan(mocker, test_settings, caplog):
    """Test the lifespan context manager."""
    mocker.patch(
        "refresh_requester.main.asyncio.to_thread", new_callable=mocker.AsyncMock
    )
    mocked_loop = mocker.Mock()
    mocker.patch(
        "refresh_requester.main.asyncio.get_running_loop", return_value=mocked_loop
    )

    mock_create_task = mocker.patch(
        "refresh_requester.main.asyncio.create_task",
        wraps=asyncio.create_task,
    )
    mock_run_and_request_shutdown = mocker.patch(
        "refresh_requester.main.run_and_request_shutdown", new_callable=mocker.AsyncMock
    )
    mocker.patch("refresh_requester.main.get_settings", return_value=test_settings)
    mock_os_exit = mocker.patch(
        "refresh_requester.main.os._exit",
        side_effect=SystemExit(0),
    )
    app = FastAPI()

    with caplog.at_level("DEBUG"):
        with pytest.raises(SystemExit):
            async with lifespan(app):
                mock_run_and_request_shutdown.assert_called_once_with(
                    app, test_settings
                )
                mock_create_task.assert_called_once()
                assert app.state.exit_code == 0, "Exit code should be initialized to 0"

        assert "Exiting container" in caplog.text, "Exit message should be logged"

    (
        mock_os_exit.assert_called_once_with(0),
        "OS exit should be called with status code 0",
    )
    assert app.state.exit_code == 0, "Exit code should remain 0 if no exception occurs"


@pytest.mark.asyncio
async def test_lifespan_fails_on_exception(mocker, test_settings, caplog):
    """Test the lifespan context manager."""
    mocker.patch(
        "refresh_requester.main.asyncio.to_thread", new_callable=mocker.AsyncMock
    )
    mocked_loop = mocker.Mock()
    mocker.patch(
        "refresh_requester.main.asyncio.get_running_loop", return_value=mocked_loop
    )
    mock_create_task = mocker.patch(
        "refresh_requester.main.asyncio.create_task",
        wraps=asyncio.create_task,
    )
    mock_run_and_request_shutdown = mocker.patch(
        "refresh_requester.main.run_and_request_shutdown",
        new_callable=mocker.AsyncMock,
        side_effect=RuntimeError("A test error."),
    )
    mocker.patch("refresh_requester.main.get_settings", return_value=test_settings)
    mock_os_exit = mocker.patch(
        "refresh_requester.main.os._exit", side_effect=SystemExit(1)
    )
    app = FastAPI()

    with caplog.at_level("DEBUG"):
        with pytest.raises(SystemExit):
            async with lifespan(app):
                mock_run_and_request_shutdown.assert_called_once_with(
                    app, test_settings
                )
                mock_create_task.assert_called_once()
                assert (
                    app.state.exit_code == 0
                ), "Exit code should be 0 at this point, the task should not have been awaited."

        assert (
            "An error occurred: A test error." in caplog.text
        ), "Exit message should be logged"

    (
        mock_os_exit.assert_called_once_with(1),
        "OS exit should be called with status code 1 as an exception _has_ occured.",
    )
    assert (
        app.state.exit_code == 1
    ), "Exit code should change to 1 if an exception occurs"
