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

### The 1:1:1 Rule (Function:File:TestFile)

We maintain a strict 1:1 correspondence between:
1. functions and files: one function per file (in the functions folder).
2. data and files: one data structure per file (in the data folder).
3. files and tests: one file, one test suite.

At the same level as the functions and data folders, there may also exist:

- Traditional classes, if they are not "pure" and/or are not easily expressed as functions (this is VERY rare).
- Protocols.
- Subpackages, which themselves have the same data and functions structure as the subpackage they are in.

### Boundary Management

A critical aspect of hexagonal architecture is proper boundary management between layers. We enforce strict type safety at system boundaries:

#### The dict[str, Any] Antipattern

Allowing `dict[str, Any]` to persist into domain layers violates our architectural principles:
- **Loss of Type Safety**: No IDE support, no compile-time checks, runtime errors
- **Domain Modeling Failure**: Domain objects should represent business concepts with clear contracts
- **Scattered Validation**: Without proper deserialization, validation spreads throughout the codebase
- **Coupling to Transport**: Domain logic becomes coupled to JSON structure

#### Translator Functions

We use **translator functions** as the standard pattern for converting external data (JSON, HTTP requests) into domain objects. These functions have a single, narrow responsibility:
- **Pure conversion**: Transform `dict[str, Any]` from requests into properly typed domain objects
- **Boundary validation**: Handle conversion errors with appropriate HTTP responses
- **No domain logic**: Never perform domain operations, only convert types and pass to domain layer
- **Context-specific**: Must be understood in relation to the specific request type and target domain objects

Critical: Translators do NOT take a request, convert it, AND do work with domain objects. They ONLY convert the request into domain objects, then pass those objects to the appropriate domain functions.

See TRANSLATORS.md for detailed implementation guidelines.

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

### Rules and System Design

Here are a few rules for how testing makes systems easier to reason about:

- Each layer of abstraction has a list of "rules" or invariants that must be maintained.
- This is one of many ways to implement "business logic."
- Each rule, ideally, has a test.
- Different layers of abstraction have a different specificity of rules.
- The "correctness" of a rule should be demonstrated in a test in the same way a User would be able to demonstrate it.
- (For lower-level rules below the user-level of abstraction, you can demonstrate them as an engineer would).
- Simple unnested lists of rules/invariants/constraints, in domain/business language, makes systems easier to reason about.
- Knowing where these rules are maintained makes them easier to find.
- Seeing rules presented together in a consistent way makes them easier to understand.
- It also makes gaps easier to identify.
- Encoding the rules in TESTS is helpful for making the system easier to change.
- If the rules are _only_ self-evident in code, then changing the system is harder.

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

### Translator Functions: Units or Integrators

Translator functions sit at system boundaries with a highly focused scope, and can be either units or integrators depending on their dependencies:

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

## Workflows

"Simple things should be simple, complex things should be possible." — Alan Kay

Code changes in this project should typically start at the highest level, where we model the system's user's request or command, and cascade "all the way down" into the lower levels of the system, making architectural and code changes as necessary along that path down through all layers of abstraction. The reasoning behind this order of operations follows from the ultimate aim of this project: ease of use and power of expression. If we decide to add a feature or extend certain behavior of the system, we should first focus on how that specific behavior is *expressed* by the user of the software. How do _they_ see the world, how do they express the outcome they desire, and how then can our system most naturally model their intent? Always start with the user, and work backwards from there. As we proceed through the layers of abstraction, we can think of each interface boundary as having users/clients/consumers in isolation, more abstractly. For example: if some other higher-level package were using this interface, what would feel most natural?

## Style

We follow a strictly functional programming style:
1. Prefer functions and composition over classes and inheritance.
2. Functions are almost always pure and have no side effects.
3. Functions follow SRP and are small/focused.
4. Functions always have clear input and output types.
5. Functions never mutate their arguments.

### Function Composition

Build complex operations by composing simple, focused functions. This makes code easier to test, understand, and modify.

#### Composition Examples

**BAD: Monolithic function:**
```python
def process_user_registration(raw_data: dict[str, Any]) -> tuple[dict[str, str], int]:
    # Validation mixed with normalization and storage
    if not raw_data.get('email'):
        return {"error": "Email required"}, 400
    
    email = raw_data['email'].strip().lower()
    if '@' not in email:
        return {"error": "Invalid email"}, 400
    
    username = raw_data.get('username', '').strip()
    if len(username) < 3:
        return {"error": "Username too short"}, 400
    
    # Storage logic mixed in
    try:
        user = User(email=email, username=username)
        storage.save_user(user)
        return {"message": "User created"}, 201
    except Exception as e:
        return {"error": "Save failed"}, 500
```

**GOOD: Composed from small functions:**
```python
# Small, focused functions
def normalize_email(email: str) -> str:
    return email.strip().lower()

def normalize_username(username: str) -> str:
    return username.strip()

def validate_email(email: str) -> Result[str, str]:
    if not email:
        return failure("Email required")
    if '@' not in email:
        return failure("Invalid email format")
    return success(email)

def validate_username(username: str) -> Result[str, str]:
    if len(username) < 3:
        return failure("Username must be at least 3 characters")
    return success(username)

def validate_user_data(email: str, username: str) -> Result[tuple[str, str], str]:
    email_result = validate_email(email)
    if isinstance(email_result, Failure):
        return failure(email_result.error)
    
    username_result = validate_username(username)
    if isinstance(username_result, Failure):
        return failure(username_result.error)
    
    return success((email_result.value, username_result.value))

# Composed operation
def process_user_registration(raw_data: dict[str, Any]) -> Result[User, str]:
    # Extract and normalize
    raw_email = raw_data.get('email', '')
    raw_username = raw_data.get('username', '')
    
    email = normalize_email(raw_email)
    username = normalize_username(raw_username)
    
    # Validate
    validation_result = validate_user_data(email, username)
    if isinstance(validation_result, Failure):
        return failure(validation_result.error)
    
    validated_email, validated_username = validation_result.value
    
    # Create domain object
    user = User(email=validated_email, username=validated_username)
    return success(user)
```

Note that, in accordinace with the 1:1:1 rule, this will create many files.

#### Benefits of Composition

- **Testable units**: Each function can be tested independently
- **Reusable components**: Validation logic can be used elsewhere
- **Clear dependencies**: Input/output relationships are explicit
- **Easy debugging**: Step through individual functions
- **Maintainable**: Change one aspect without affecting others


### General Rules

There are a few other general rules for how we write code:
1. Always use `dedent` for multi-line strings.
2. Avoid underscore method patterns; always prefer `this_func` over `_this_func`.
3. Always prefer modern Python (3.13+) language and type features.
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
- Use `type` statement for type aliases instead of `TypeAlias`

#### Domain Type Safety

**Never allow `dict[str, Any]` in domain layers**. This is a critical antipattern that violates type safety and domain modeling principles.

##### Why dict[str, Any] is Forbidden in Domain Code

- **Loss of Type Safety**: No IDE autocomplete, no compile-time checks, runtime errors from typos
- **Domain Modeling Failure**: Domain objects should represent business concepts with clear contracts
- **Scattered Validation**: Without proper types, validation logic spreads as defensive checks
- **Coupling to Transport**: Domain logic becomes coupled to JSON/HTTP structure

### Result Types for Explicit Error Handling

Instead of raising exceptions in domain logic, use Result types to make success and failure explicit. This improves testability and makes error handling more predictable.

#### The Result Pattern

```python
@dataclass
class Success[T]:
    value: T
    
@dataclass  
class Failure[E]:
    error: E

type Result[T, E] = Success[T] | Failure[E]

# Helper functions
def success[T](value: T) -> Success[T]:
    return Success(value)

def failure[E](error: E) -> Failure[E]:
    return Failure(error)
```

#### Usage Examples

**BAD: Exceptions in domain logic:**
```python
def calculate_user_score(user_data: dict[str, Any]) -> float:
    if not user_data.get('points'):
        raise ValueError("Points required")  # Exception in domain
    
    points = user_data.get('points', 0)
    multiplier = user_data.get('multiplier', 1.0)
    
    if multiplier <= 0:
        raise ValueError("Invalid multiplier")  # Exception in domain
        
    return points * multiplier
```

**GOOD: Result types with typed domain objects:**
```python
@dataclass
class ScoreCalculationError:
    message: str
    field: str | None = None

def calculate_user_score(user: User) -> Result[float, ScoreCalculationError]:
    if user.points < 0:
        return failure(ScoreCalculationError("Points cannot be negative", "points"))
    
    if user.multiplier <= 0:
        return failure(ScoreCalculationError("Multiplier must be positive", "multiplier"))
    
    score = user.points * user.multiplier
    return success(score)

# Usage in integrator
def process_user_score(user: User) -> tuple[dict[str, str], int]:
    result = calculate_user_score(user)
    
    match result:
        case Success(score):
            return {"score": str(score)}, 200
        case Failure(error):
            return {"error": error.message}, 400
```

#### Benefits of Result Types

- **Explicit error handling**: All possible outcomes are visible in the type signature
- **No hidden exceptions**: Domain functions never throw, making them predictable
- **Easier testing**: Test both success and failure paths without exception handling
- **Composable**: Chain operations while preserving errors
- **Type safe**: Compiler ensures all error cases are handled

##### Examples

**BAD: Untyped dictionaries in domain:**
```python
def calculate_user_score(user_data: dict[str, Any]) -> float:
    # Domain logic coupled to JSON structure
    return user_data.get('points', 0) * user_data.get('multiplier', 1.0)
```

**GOOD: Typed domain objects:**
```python
def calculate_user_score(user: User) -> float:
    # Domain logic works with proper types
    return user.points * user.multiplier
```

**BAD: Passing dictionaries through layers:**
```python
# In integrator
def process_user_request(json_data: dict[str, Any]) -> dict[str, Any]:
    # Dictionary propagates through system
    result = user_service.update_profile(json_data)
    return result
```

**GOOD - Use translator pattern at boundaries:**
```python
# In translator function (see TRANSLATORS.md)
async def process_user_request(request: Request) -> tuple[dict[str, str], int]:
    # Immediate deserialization at boundary
    data = await request.json()
    
    # Convert to domain types
    try:
        user_id = uuid.UUID(data.get("user_id"))
    except (ValueError, TypeError):
        return {"error": "Invalid user_id"}, 400
    
    # Work with typed domain objects
    user = user_service.get_user(user_id)
    result = user_service.update_profile(user)
    
    return {"message": "Profile updated"}, 200
```

##### Exceptions

The only exceptions for `dict[str, Any]` in domain code:
- Truly dynamic data where structure is part of the domain (e.g., CMS storing arbitrary JSON)
- Even then, wrap in a value object that provides controlled access:

```python
class DynamicContent:
    """Encapsulates truly dynamic JSON content."""
    def __init__(self, data: dict[str, Any]):
        self._data = data
    
    def get_field(self, path: str, default: Any = None) -> Any:
        """Controlled access to dynamic data with validation."""
        # Implementation
```

## Progress

Some code predates these rules and is not yet in compliance. Before making changes to existing functionality, please review the code and determine if it is in compliance with the rules. If it is not in compliance, please highlight the code in question and ask for guidance as to whether it should be changed before proceeding.
