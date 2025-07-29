"""
Centralized module for mocking all boundary-level interactions in tests.

This module provides a unified interface for mocking:
- HTTP requests and responses
- HTTP Session data
- File system operations
- Environment variables
- Other external system boundaries
"""

import os
import json
from pathlib import Path
from typing import Any, Protocol
from tempfile import TemporaryDirectory
from contextlib import contextmanager
from dataclasses import dataclass, field
from urllib.parse import urlencode

import respx
from httpx import Response
from starlette.requests import Request


# ==============================================================================
# HTTP
# ==============================================================================


@dataclass
class MockHttpResponse:
    """Represents a mocked HTTP response."""

    status_code: int = 200
    json_data: dict[str, Any] | None = None
    text_data: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str | None = None

    def to_httpx_response(self) -> Response:
        """Convert to httpx Response object."""
        headers = self.headers.copy()

        if self.content_type:
            headers["content-type"] = self.content_type

        if self.json_data is not None:
            headers.setdefault("content-type", "application/json")
            return Response(self.status_code, json=self.json_data, headers=headers)
        elif self.text_data is not None:
            return Response(self.status_code, text=self.text_data, headers=headers)
        else:
            return Response(self.status_code, headers=headers)


class MockState:
    """Mock request state object for adding state attributes."""

    def __init__(self, data: dict[str, Any]):
        for key, value in data.items():
            setattr(self, key, value)


def mock_request(
    form_data: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    query_params: dict[str, str] | None = None,
    session_data: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    path: str = "/",
    method: str = "POST",
) -> Request:
    """
    Create a real Starlette Request object for testing TRANSLATOR functions.

    Args:
        form_data: Dictionary of form field data (for web APIs)
        json_data: Dictionary of JSON data (for JSON APIs)
        query_params: Dictionary of query parameters
        session_data: Dictionary of session data
        state: Dictionary of request state data
        path: Request path
        method: HTTP method

    Returns:
        Real Starlette Request object
    """
    # Determine content type and body based on data provided
    if json_data is not None:
        # JSON request
        body = json.dumps(json_data).encode("utf-8")
        content_type = b"application/json"
    elif form_data is not None:
        # Form request
        body = urlencode(form_data).encode("utf-8")
        content_type = b"application/x-www-form-urlencoded"
    else:
        # Empty request
        body = b""
        content_type = b"text/plain"

    # Handle query parameters
    query_string = b""
    if query_params:
        query_string = urlencode(query_params).encode("utf-8")

    # Create ASGI scope
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
        "headers": [
            (b"content-type", content_type),
            (b"content-length", str(len(body)).encode()),
        ],
    }

    # Create receive function that provides the request body
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    # Create the request
    request = Request(scope, receive)

    # Add session data if provided
    if session_data:
        request._session = session_data  # type: ignore

    # Add state data if provided
    if state:
        # Set state attributes individually to avoid assignment warning
        for key, value in state.items():
            setattr(request.state, key, value)

    return request


class HttpMocker(Protocol):
    """Protocol for HTTP mocking operations."""

    def mock_get(self, url: str, response: MockHttpResponse) -> None:
        """Mock a GET request."""
        ...

    def mock_post(self, url: str, response: MockHttpResponse) -> None:
        """Mock a POST request."""
        ...

    def mock_any(self, url: str, response: MockHttpResponse) -> None:
        """Mock any HTTP method."""
        ...


@contextmanager
def mock_http():
    """Context manager for mocking HTTP requests."""

    class HttpMockerImpl:
        def __init__(self, respx_mock):
            self.respx_mock = respx_mock

        def mock_get(self, url: str, response: MockHttpResponse) -> None:
            self.respx_mock.get(url).mock(return_value=response.to_httpx_response())

        def mock_post(self, url: str, response: MockHttpResponse) -> None:
            self.respx_mock.post(url).mock(return_value=response.to_httpx_response())

        def mock_any(self, url: str, response: MockHttpResponse) -> None:
            self.respx_mock.route(url=url).mock(
                return_value=response.to_httpx_response()
            )

    with respx.mock(assert_all_called=False) as respx_mock:
        yield HttpMockerImpl(respx_mock)


# ==============================================================================
# File System
# ==============================================================================


@dataclass
class MockFile:
    """Represents a mocked file."""

    path: Path
    content: str | bytes | dict | list
    is_json: bool = False

    def write(self, parent_dir: Path) -> Path:
        """Write the file to the given parent directory."""
        full_path = parent_dir / self.path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if self.is_json and isinstance(self.content, (dict, list)):
            with open(full_path, "w") as f:
                json.dump(self.content, f)
        elif isinstance(self.content, bytes):
            with open(full_path, "wb") as f:
                f.write(self.content)
        else:
            with open(full_path, "w") as f:
                f.write(self.content)

        return full_path


@dataclass
class MockFileSystem:
    """Represents a mocked file system structure."""

    files: list[MockFile] = field(default_factory=list)
    directories: list[Path] = field(default_factory=list)

    def create_in(self, parent_dir: Path) -> None:
        """Create the file system structure in the given directory."""
        # Create directories
        for directory in self.directories:
            full_path = parent_dir / directory
            full_path.mkdir(parents=True, exist_ok=True)

        # Create files
        for file in self.files:
            file.write(parent_dir)


@contextmanager
def mock_filesystem(structure: MockFileSystem | None = None):
    """Context manager for mocking file system operations."""
    with TemporaryDirectory() as temp_dir:  # type: ignore
        temp_path = Path(temp_dir)

        if structure:
            structure.create_in(temp_path)

        yield temp_path


# ==============================================================================
# Session Management
# ==============================================================================

from unittest.mock import patch


@contextmanager
def mock_session(session_data: dict[str, Any] | None = None):
    """
    Context manager for mocking Starlette session data.

    Args:
        session_data: Dictionary of session data to set
    """
    session = session_data or {}

    with patch("starlette.requests.Request.session", session):
        yield session


# ==============================================================================
# Environment Variables
# ==============================================================================


@contextmanager
def mock_env(variables: dict[str, str] | None = None, clear_prefix: str | None = None):
    """
    Context manager for mocking environment variables.

    Args:
        variables: Dictionary of environment variables to set
        clear_prefix: Clear all env vars starting with this prefix
    """
    # Save current environment
    env_backup = os.environ.copy()

    try:
        # Clear variables with prefix if specified
        if clear_prefix:
            for key in list(os.environ.keys()):
                if key.startswith(clear_prefix):
                    del os.environ[key]

        # Set new variables
        if variables:
            for key, value in variables.items():
                os.environ[key] = value

        yield

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(env_backup)


@contextmanager
def mock_boundaries(
    http_mocks: dict[str, MockHttpResponse] | None = None,
    filesystem: MockFileSystem | None = None,
    env_vars: dict[str, str] | None = None,
    clear_env_prefix: str | None = None,
    session_data: dict[str, Any] | None = None,
):
    """
    Comprehensive context manager for mocking all boundary interactions.

    Args:
        http_mocks: Dict of URL to MockHttpResponse mappings
        filesystem: MockFileSystem structure to create
        env_vars: Environment variables to set
        clear_env_prefix: Clear env vars with this prefix
        session_data: Session data to set

    Yields:
        tuple: (http_mocker, filesystem_path, session)
    """
    with mock_http() as http_mocker:
        # Set up HTTP mocks
        if http_mocks:
            for url, response in http_mocks.items():
                http_mocker.mock_any(url, response)

        with mock_filesystem(filesystem) as fs_path:
            with mock_env(env_vars, clear_env_prefix):
                with mock_session(session_data) as session:
                    yield http_mocker, fs_path, session
