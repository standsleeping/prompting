"""
Centralized module for mocking all boundary-level interactions in tests.

This module provides a unified interface for mocking:
- HTTP requests and responses
- File system operations
- Environment variables
- Database interactions (if needed)
- Other external system boundaries
"""

import os
import json
from pathlib import Path
from typing import Any, Protocol
from tempfile import TemporaryDirectory
from contextlib import contextmanager
from dataclasses import dataclass, field

import respx
from httpx import Response


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
