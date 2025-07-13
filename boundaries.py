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


def ollama_api_response(
    content: str = "Hello, world!", model: str = "llama3.1:8b"
) -> MockHttpResponse:
    """Create a standard Ollama chat API response."""
    return MockHttpResponse(
        json_data={
            "model": model,
            "created_at": "2024-01-01T12:00:00Z",
            "message": {"role": "assistant", "content": content},
            "done": True,
        }
    )


def ollama_streaming_response(
    chunks: list[str] | None = None, model: str = "llama3.1:8b"
) -> MockHttpResponse:
    """Create a streaming Ollama chat API response."""
    if chunks is None:
        chunks = ["Hello", ", streaming", " world!"]

    lines = []
    for i, chunk in enumerate(chunks):
        is_done = i == len(chunks) - 1
        line = {
            "model": model,
            "created_at": f"2024-01-01T12:00:0{i}Z",
            "message": {"role": "assistant", "content": chunk},
            "done": is_done,
        }
        lines.append(json.dumps(line))

    return MockHttpResponse(
        text_data="\n".join(lines), content_type="application/x-ndjson"
    )


def ollama_tool_call_response(
    tool_name: str = "get_weather",
    tool_arguments: dict[str, Any] | None = None,
    model: str = "llama3.1:8b",
) -> MockHttpResponse:
    """Create a standard Ollama chat API response with tool call."""
    if tool_arguments is None:
        tool_arguments = {"city": "Omaha"}

    return MockHttpResponse(
        json_data={
            "model": model,
            "created_at": "2024-01-01T12:00:00Z",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": tool_name, "arguments": tool_arguments}}
                ],
            },
            "done": True,
        }
    )


def ollama_streaming_tool_call_response(
    tool_name: str = "get_weather",
    tool_arguments: dict[str, Any] | None = None,
    model: str = "llama3.1:8b",
) -> MockHttpResponse:
    """Create a streaming Ollama chat API response with tool call."""
    if tool_arguments is None:
        tool_arguments = {"city": "Omaha"}

    lines = []

    # First chunk with tool call
    tool_call_chunk = {
        "model": model,
        "created_at": "2024-01-01T12:00:00Z",
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": tool_name, "arguments": tool_arguments}}
            ],
        },
        "done": False,
    }

    lines.append(json.dumps(tool_call_chunk))

    # Final chunk indicating completion
    completion_chunk = {
        "model": model,
        "created_at": "2024-01-01T12:00:01Z",
        "message": {"role": "assistant", "content": ""},
        "done_reason": "stop",
        "done": True,
        "total_duration": 99,
        "load_duration": 99,
        "prompt_eval_count": 99,
        "prompt_eval_duration": 99,
        "eval_count": 99,
        "eval_duration": 99,
    }

    lines.append(json.dumps(completion_chunk))

    return MockHttpResponse(
        text_data="\n".join(lines),
        content_type="application/x-ndjson",
    )


def full_tool_config() -> MockFileSystem:
    """Create a comprehensive tool configuration structure for testing."""

    tool_boxes_config = [
        {
            "name": "test_box",
            "description": "Test tool box",
            "tools": ["test_tool1", "test_tool2"],
        },
        {
            "name": "empty_box",
            "description": "Empty tool box",
            "tools": [],
        },
    ]

    test_tool1 = {
        "name": "test_tool1",
        "description": "Test tool 1",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter 1",
                },
            },
            "required": ["param1"],
        },
    }

    test_tool2 = {
        "name": "test_tool2",
        "description": "Test tool 2",
        "parameters": {
            "type": "object",
            "properties": {
                "param2": {
                    "type": "number",
                    "description": "Parameter 2",
                },
            },
            "required": ["param2"],
        },
    }

    files = [
        MockFile(Path("tool_boxes.json"), tool_boxes_config, is_json=True),
        MockFile(Path("test_tool1.json"), test_tool1, is_json=True),
        MockFile(Path("test_tool2.json"), test_tool2, is_json=True),
    ]

    return MockFileSystem(files=files)


def full_prompt_config() -> MockFileSystem:
    """Comprehensive prompt configuration structure for testing."""

    files = []
    directories = [Path("schemas")]

    # Test schema file
    test_schema = {
        "type": "object",
        "properties": {"response": {"type": "string"}},
        "required": ["response"],
    }

    files.append(
        MockFile(
            Path("schemas/test_schema.json"),
            test_schema,
            is_json=True,
        )
    )

    # System message file
    system_message = "This is a test system message."

    files.append(
        MockFile(
            Path("test_system_message.txt"),
            system_message,
        )
    )

    # Prompt config with schema
    test_config = {
        "name": "test_prompt",
        "description": "Test prompt description",
        "system_message_path": "test_system_message.txt",
        "schema_path": "schemas/test_schema.json",
    }

    files.append(
        MockFile(
            Path("test_prompt.json"),
            test_config,
            is_json=True,
        )
    )

    # Prompt config without schema
    test_config_no_schema = {
        "name": "test_prompt_no_schema",
        "description": "Test prompt without schema",
        "system_message_path": "test_system_message.txt",
    }

    files.append(
        MockFile(
            Path("test_prompt_no_schema.json"),
            test_config_no_schema,
            is_json=True,
        )
    )

    return MockFileSystem(files=files, directories=directories)


@contextmanager
def mock_boundaries(
    http_mocks: dict[str, MockHttpResponse] | None = None,
    filesystem: MockFileSystem | None = None,
    env_vars: dict[str, str] | None = None,
    clear_env_prefix: str | None = None,
):
    """
    Comprehensive context manager for mocking all boundary interactions.

    Args:
        http_mocks: Dict of URL to MockHttpResponse mappings
        filesystem: MockFileSystem structure to create
        env_vars: Environment variables to set
        clear_env_prefix: Clear env vars with this prefix

    Yields:
        tuple: (http_mocker, filesystem_path)
    """
    with mock_http() as http_mocker:
        # Set up HTTP mocks
        if http_mocks:
            for url, response in http_mocks.items():
                http_mocker.mock_any(url, response)

        with mock_filesystem(filesystem) as fs_path:
            with mock_env(env_vars, clear_env_prefix):
                yield http_mocker, fs_path
