# Project Guide

This project follows a strict set of rules for development. Rules for the overall architecture and file structure, testing guidelines, and the integrators/units sections below, must be followed at all times.

## Purpose and Usage

Please refer to README.md at the project root for details about the purpose of this project, how it is organized and configured, and for usage examples.

## Commands

Set up to run as a module:

```bash
uv pip install -e .
```

Run tests:

```bash
uv run python -m pytest
```

## System Architecture

This project follows a strict "hexagonal" architecture. Other names for this architectural style include "functional core, imperative shell" and "ports and adapters."

The codebase is organized into a set of subpackages. Each subpackage is an independent unit, often with a clear/independent API, complete with types, usage guidelines, and documentation. Circular dependencies between subpackages are strictly forbidden.

Each subpackage keeps an internally strict separation between functions and data.

The data (data structures, dataclasses, Pydantic models, and types) are kept in a data folder.

The functions (often "pure" functions, wherever possible) are kept in the functions folder.

We maintain a strict 1:1 correspondence between:
1. functions and files: one function per file (in the functions folder).
2. data and files: one data structure per file (in the data folder).
3. files and tests: one file, one test suite.

At the same level as the functions and data folders, there may also exist:

- Traditional classes, if they are not "pure" and/or are not easily expressed as functions (this is VERY rare).
- Protocols.
- Subpackages, which themselves have the same data and functions structure as the subpackage they are in.


### Dependencies

Run the following command to visualize the dependency graph:

```bash
uv run pydeps src/[REPLACE] --max-module-depth=2 --rankdir RL --rmprefix [REPLACE].
```

There should be no blue boxes in the above graph (blue boxes and two-way arrows indicate circular dependencies).

The following dependencies are allowed:

[REPLACE]

## Testing

Testing is critical in this project and often informs how subsystems are designed.

Well-designed components produce tests that are easy to read, write, and run.

We use our tests as a way of evaluating the quality of our design.

We follow a strict and focused test-first approach, always discussing WHAT behavior to test before determining HOW to test it.

We almost never use test classes; usually functions are simple and sufficiently "unit-like" that a flat list of pytest tests in a file will suffice.

Tests are written before implementation with declarative assertion documentation:
- BAD test docstring: "Tests that env is loaded in non-containerized environment"
- GOOD test docstring: "Loads env in non-containerized environment"

Additional general testing rules:

- Fixtures are ALWAYS centralized and shared in tests/fixtures.py. No exceptions.
- Tests focus on input/output pairs for our functional codebase.
- Single pytest assertion per test where possible.
- Never write code until tests have been written.
- Never patch/mock/stub code (see below)

### Mocking Rules

We strictly avoid mocking our own application code. When we encounter tests that would patch internal code, we should either:
1. Refactor the code into units and integrators (see below) to make it more directly testable.
2. Write integration tests that exercise the real code paths without mocking.

However, external system boundaries (HTTP, filesystem, environment variables, databases) must be mocked for reliable, deterministic testing. All boundary mocking should be centralized in `boundaries.py`:

#### Boundary Mocking Guidelines

- **HTTP Requests**: Use `mock_http()` context manager with `MockHttpResponse` objects
- **File System**: Use `mock_filesystem()` with `MockFileSystem` and `MockFile` objects  
- **Environment Variables**: Use `mock_env()` to set/clear environment variables
- **Combined Boundaries**: Use `mock_boundaries()` for tests requiring multiple boundary types

Example boundary mocking patterns:
```python
# HTTP mocking
with mock_http() as http_mocker:
    http_mocker.mock_get("https://api.example.com", MockHttpResponse(json_data={"result": "success"}))
    
# Filesystem mocking
with mock_filesystem(MockFileSystem(files=[MockFile(Path("config.json"), {"key": "value"}, is_json=True)])) as fs_path:
    
# Environment mocking
with mock_env({"API_KEY": "test-key"}, clear_prefix="TEST_"):
    
# Combined boundaries
with mock_boundaries(
    http_mocks={"https://api.example.com": MockHttpResponse(json_data={"data": "test"})},
    filesystem=MockFileSystem(files=[...]),
    env_vars={"ENV": "test"}
) as (http_mocker, fs_path):
```

Never mock application functions, classes, or methods - only external system boundaries.

## "Integrators" and "Units"

All subpackages contain functions that are one of two types:
1. **Units**: Simple components with pure functions (input -> output)
2. **Integrators**: Components with dependencies on other functions, and/or effectful behavior

Integration tests may contain multiple assertions since integrators often call several units and compose their results into some data structure, which is returned.

We avoid combinatorial explosion (2^n paths for n branches) through careful design that makes invalid states unrepresentable and maintains a clear separation between integrators and units.

Notes on units:
- Simple data types in and out.
- Pure functions, no imports, no dependencies, no side effects.
- Tested simply: all possible return values are covered in unit-like assertions.

Notes on integrators:
- Calls other units and/or integrators.
- Sole purpose is to assemble complex return types and data structures via delegated unit/integrator calls.
- Never makes semantically meaningful decisions: always delegates to other integrators/units.
- Can use if/else but ONLY to conditionally (i.e. early) return its return type.
- Simple integration tests: one test function/suite-of-functions for each `return` inside integrator body.
- Size of test suite is proportional to variety of return conditions.
- Tests NEVER mock or stub user code; always RUNS code that integrator depends on.

## Workflows

"Simple things should be simple, complex things should be possible." — Alan Kay

Code changes in this project should typically start at the highest level, where we model the system's user's request or command, and cascade "all the way down" into the lower levels of the system, making architectural and code changes as necessary along that path down through all layers of abstraction. The reasoning behind this order of operations follows from the ultimate aim of this project: ease of use and power of expression. If we decide to add a feature or extend certain behavior of the system, we should first focus on how that specific behavior is *expressed* by the user of the software. How do _they_ see the world, how do they express the outcome they desire, and how then can our system most naturally model their intent? Always start with the user, and work backwards from there. As we proceed through the layers of abstraction, we can think of each interface boundary as having users/clients/consumers in isolation, more abstractly. For example: if some other higher-level package were using this interface, what would feel most natural?

## Style

We follow a strictly functional programming style:
1. Prefer functions and composition over classes and inheritance.
2. Functions are almost always pure and have no side effects.
3. Functions follow SRP and are small/focused.
4. Functions always have clear input and output types.
5. Functions never mutate their arguments.

There are a few other general rules for how we write code:
1. Always use `dedent` for multi-line strings.
2. Avoid underscore method patterns; always prefer `this_func` over `_this_func`.
3. Always prefer modern Python (3.12+) language and type features.
4. Always use generic type parameter syntax (`class Foo[T]:` instead of `TypeVar`).
5. Prefer union types with `|` syntax (`str | None` instead of `Union[str, None]`).
6. Never use `if TYPE_CHECKING`.
7. Never use `# type: ignore[xyz]`.

### Modern Typing Conventions

We strictly follow modern Python typing conventions and avoid legacy typing patterns:

#### Built-in Generic Types
- Use: `list[T]`, `dict[K, V]`, `set[T]`, `tuple[T, ...]`
- Avoid: `List[T]`, `Dict[K, V]`, `Set[T]`, `Tuple[T, ...]`

#### Union Types
- Use: `T | None`, `str | int`, `list[str] | dict[str, int]`
- Avoid: `Optional[T]`, `Union[str, int]`

#### Generic Classes
- Use: `class Container[T]:` (PEP 695 syntax)
- Avoid: `T = TypeVar('T')` + `class Container(Generic[T]):`

#### Import Minimization
- Only import from `typing` when necessary (e.g., `Any`, `Protocol`, `Literal`)
- Never import: `List`, `Dict`, `Set`, `Tuple`, `Optional`, `Union`, `Generic`, `TypeVar`
- Built-in types and union syntax eliminate most `typing` imports

## Progress

Some code predates these rules and is not yet in compliance. Before making changes to existing functionality, please review the code and determine if it is in compliance with the rules. If it is not in compliance, please highlight the code in question and ask for guidance as to whether it should be changed before proceeding.