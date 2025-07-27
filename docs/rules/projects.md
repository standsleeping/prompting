# Projects

Our projects follow a strict set of rules for development. Principles for the overall system architecture, file structure, testing guidelines, and style rules must be followed closely.

Please also refer to README.md at the project root for details about the purpose of this project, how it is organized and configured, and for specific usage examples.

## Commands

Set up to run as a module:

```bash
uv pip install -e .
```

Always run `pytest` (and commands like `mypy` and `ty`) via `uv`:

```bash
uv run python -m pytest
```

## System Architecture

This project follows a strict "hexagonal" architecture (also known as "functional core, imperative shell" or "ports and adapters") with a type-driven development methodology.

The codebase is organized modularly, as a series of packages. Each package is designed as an independent unit with a clear, type-first API. Types serve as the primary contract between modules, complete with usage guidelines and documentation. Circular dependencies between packages are strictly forbidden.

### Type-Driven Development

In this architecture, types are the foundation of system design. We follow these principles:

1. **Types as Module Boundaries**: Each package's public interface is defined primarily through its data types.

2. **Design Flow**: Development follows a type-first workflow,
   where data structures and types that model the domain are often designed first, with pure functions that transform these types are implemented next. Type signatures guide and constrain implementations.

3. **Types Enforce Architecture**: The prohibition on circular dependencies is reinforced by our type system. Modules can only depend on types from their dependencies, creating a clear, unidirectional flow.

### Package Structure

Each package maintains a strict separation between functions and data.

**Data structures** (types, dataclasses, Pydantic models) are placed at the package root level, at the same level as the `functions` folder. This placement reflects their fundamental importance. In this architecture, data structures are of the utmost importance as they define the vocabulary of the system, help establish module boundaries, guide function implementations, and ensure type safety across module boundaries.

**Functions** (pure functions, wherever possible) are kept in the package's `functions` folder. These functions operate on the well-defined types, with their signatures serving as executable documentation of the transformations they perform.

This separation ensures that:

- Types are immediately visible and discoverable.
- The data model can be understood independently of implementation.
- Functions remain pure and testable.
- Module interfaces remain stable even as implementations evolve.

### The 1:1:1 Rule (Function:File:TestFile)

We maintain a strict 1:1 correspondence between:

1. **Data and files**: One data structure per file.
2. **Functions and files**: One function per file.
3. **Files and tests**: One file, one test suite.

Union types and their constituent result types may be grouped together in a single file when they form a cohesive set of related outcomes for a specific operation

Example: `RegistrationResult = RegistrationSuccess | AlreadyExists | InvalidAppData`.

At the same level as the functions and data, there may also exist subpackages with semantically meaningful names, themselves having the same data/function structure as the subpackage they are in.

### Boundaries and Translators

A critical aspect of hexagonal architecture is proper boundary management between layers. We enforce strict type safety at system boundaries.

When `dict[str, Any]` types propagate deeper into the codebase beyond initial entry points, it's a clear sign that boundaries are not being properly defined and managed. Allowing `dict[str, Any]` to persist into domain layers violates our architectural principles:

- **Loss of type safety**: No IDE support, no compile-time checks, runtime errors.
- **Domain modeling failure**: Domain objects should represent business concepts with clear contracts.
- **Scattered validation**: Without proper deserialization, validation spreads throughout the codebase.
- **Coupling to transport**: Domain logic becomes coupled to JSON structure.

We use **translator functions** as the standard pattern for converting external data (JSON, HTTP requests) into domain objects. These functions have a single, narrow responsibility:

- **Pure conversion**: Transform `dict[str, Any]` from requests into properly typed domain objects.
- **Boundary validation**: Handle conversion errors with appropriate HTTP responses.
- **No domain logic**: Never perform domain operations, only convert types and pass to domain layer.

See [translators.md](translators.md) for detailed implementation guidelines.

### Dependencies

Run the following command to visualize the dependency graph:

```bash
uv run pydeps src/[REPLACE] --max-module-depth=2 --rankdir RL --rmprefix [REPLACE].
```

Blue boxes and two-way arrows in the generated dependency graph indicate circular dependencies. There should be no blue boxes!

## Testing

Testing is critical in this project and often informs how subsystems are designed.

Well-designed components produce tests that are easy to read, write, and run.

We use our tests as a way of evaluating the quality of our design.

We follow a strict test-first approach, always discussing WHAT behavior to test before determining HOW to test it.

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

We always avoid mocking our own application code. When we encounter tests that would patch internal code, we should either:

1. Refactor the code into units and integrators (see below) to make it more directly testable.
2. Write integration tests that exercise the real code paths without mocking.

However, external system boundaries (HTTP, filesystem, environment variables, databases) must be mocked for reliable, deterministic testing. All boundary mocking should be centralized in `boundaries.py`.

**NEVER** import or use `unittest.mock` directly in test files.

**NEVER** use `AsyncMock`, `MagicMock`, `patch`, or similar manual mocking.

**ALWAYS** use `TestClient` from `starlette.testclient` for API endpoint testing with proper boundary mocking.

**ALWAYS** use boundary mockers from `tests/boundaries.py`:

- `mock_http()` for HTTP requests.
- `mock_session()` for Starlette sessions.
- `mock_filesystem()` for file operations.
- `mock_env()` for environment variables.
- `mock_boundaries()` for comprehensive boundary mocking.

Violation of these mocking rules indicates poor architectural boundaries and must be fixed by refactoring to use proper fixtures and integration patterns.

Never mock application functions, classes, or methods. Only external system boundaries.

## "Integrators" and "Units"

(Note: this is the most commonly violated architectural rule; be rigorous in your assessment as to whether the code you produce adheres to these standards).

All subpackages should contain functions that are one of two types:

1. **Units**: Simple components with pure functions (input -> output).
2. **Integrators**: Components with dependencies on other functions, and/or effectful behavior.

We avoid combinatorial explosion (2^n paths for n branches) through careful design that makes invalid states unrepresentable and maintains a clear separation between integrators and units.

**What characteristics define a unit?**

- Simple data types in and out.
- Pure functions, no imports, no dependencies, no side effects.
- Tested simply: all possible return values are covered in unit-like assertions.

**What characteristics define an integrator?**

- Calls other units and/or integrators.
- Sole purpose is to assemble complex return types and data structures via delegated unit/integrator calls.
- Never makes semantically meaningful decisions: always delegates to other integrators/units.
- Can use if/else but ONLY to conditionally (i.e. early) return its return type.
- Simple integration tests: one test function/suite-of-functions for each `return` inside integrator body.
- Size of test suite is proportional to variety of return conditions.
- Tests NEVER mock or stub user code; always RUNS code that integrator depends on.



Translator functions sit at system or package boundaries, and can be either units or integrators, depending on the context.

**Translator as Unit:**

- **Pure conversion**: Direct transformation of `dict[str, Any]` to domain types using only built-in functions
- **No dependencies**: Uses only standard library functions (uuid.UUID, datetime.fromisoformat, etc.)
- **No imports**: No calls to other application functions
- **Example**: Converting string to UUID, parsing ISO datetime, basic type coercion

**Translator as Integrator:**

- **Composed conversion**: Calls other units/integrators to perform complex translations
- **Has dependencies**: Uses validation units, parsing integrators, or lookup functions
- **Assembles results**: Combines multiple conversion operations into domain objects
- **Example**: Converting request data that requires validation against existing domain rules

Both types:

- **Only convert**: Transform external data to domain types
- **Only validate boundaries**: Handle conversion errors and return appropriate error responses  
- **Pass, don't execute**: Return properly typed domain objects for other functions to use
- **No domain operations**: Never call domain functions directly, leave that to the calling context

## Style Rules

**Functional Programming Rules**

1. Prefer functions and composition over classes and inheritance.
2. Functions are almost always pure and have no side effects.
3. Functions follow SRP and are small/focused.
4. Functions always have clear input and output types.
5. Functions never mutate their arguments.

**Python Language Usage**

1. Always use `dedent` for multi-line strings.
2. Avoid underscore method patterns; always prefer `this_func` over `_this_func`.
3. Always prefer modern Python (3.13+) language and type features.
4. Always use generic type parameter syntax (`class Foo[T]:` instead of `TypeVar`).
5. Prefer union types with `|` syntax (`str | None` instead of `Union[str, None]`).
6. Never use `if TYPE_CHECKING`.
7. Never use `# type: ignore[xyz]`.

## Typing Rules

We always follow modern Python typing conventions and avoid legacy typing patterns:

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
- Use `type` statement for type aliases instead of `TypeAlias`

#### Domain Type Safety

- Never allow `dict[str, Any]` in domain layers.
- Instead of raising exceptions in domain logic, use Result types to make success and failure explicit. This improves testability and makes error handling more predictable.
- Handle errors explicitly, so all possible outcomes are visible in the type signature.
- Domain functions should never throw, making them predictable.
- Test both success and failure paths without exception handling.

## Progress

Some code in this project predates these rules and is not yet in compliance. Before making changes to existing functionality, please review the code and determine if it is in compliance with the rules. If it is not in compliance, please highlight the code in question and ask for guidance as to whether it should be changed before proceeding.