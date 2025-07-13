# TRANSLATOR FUNCTIONS

## Problem Statement

In our hexagonal architecture, we have a critical boundary between the **network layer** (HTTP requests with JSON strings) and the **domain layer** (typed objects used by `SystemStorage` and `Manager`). Currently, there's inconsistent handling of this translation, leading to type errors and architectural confusion.

## The Pattern

**Translator functions** have a single, focused responsibility: converting raw HTTP request data into properly typed domain objects. They are pure conversion functions that sit at the boundary between:

- **Input**: `Request` objects containing JSON with string representations 
- **Output**: Properly typed domain objects (NOT calls to domain functions)
- **Return**: Either conversion errors OR domain objects for the caller to use

**Critical**: Translators do NOT call `SystemStorage` or `Manager` - they only convert request data into the types that domain functions expect. The calling context is responsible for using those converted objects with domain functions.

### Unit vs Integrator Translators

Translator functions can be either **units** or **integrators** depending on their dependencies:

**Translator as Unit:**
- Pure conversion using only built-in functions (uuid.UUID, datetime.fromisoformat)
- No imports from other application modules
- Direct transformation of strings to domain types
- Example: Simple field extraction and type conversion

**Translator as Integrator:**
- Calls other units or integrators to perform complex conversion
- May import and use domain validation functions
- Assembles multiple conversion operations
- Example: Complex validation requiring domain knowledge

Both maintain the same responsibility: convert request data to domain objects without performing domain operations.

## Current Inconsistencies

### Example 1: `confirm_watcher.py` (BROKEN)
```python
# Lines 16-21: Attempts to use domain validation for boundary conversion
process_id_str = data.get("process_id")
try:
    process_id: uuid.UUID = valid_uuid(process_id_str)  # ❌ Wrong layer
except (ValueError, TypeError):
    return {"error": "Invalid 'process_id' format"}, 400
```

**Problem**: Uses `valid_uuid()` (designed for domain validation) to convert strings to UUIDs (boundary responsibility).

### Example 2: `add_process.py` (CORRECT)
```python
# Lines 82-89: Proper boundary conversion
process_id_str = data.get("process_id")
try:
    process_id = uuid.UUID(process_id_str)  # ✅ Correct conversion
except (ValueError, TypeError):
    return {"error": "Invalid 'process_id' format"}, 400
```

**Pattern**: Direct conversion from string to UUID with appropriate error handling.

### Example 3: `failed_watcher.py` (INCOMPLETE)
```python
# Line 23: Conversion without error handling
process_id = uuid.UUID(data.get("process_id"))  # ⚠️ Missing error handling
```

**Problem**: Correct conversion approach but lacks proper error handling for malformed UUIDs.

## The Correct Pattern

Translator functions should have a narrow focus on conversion only:

```python
async def translator_function(
    request: Request
) -> tuple[TranslationError | None, DomainObject | None]:
    # 1. EXTRACT: Get raw JSON data
    data = await request.json()
    
    # 2. VALIDATE PRESENCE: Check required fields exist
    raw_field = data.get("required_field")
    if raw_field is None:
        return TranslationError("Missing 'required_field' field"), None
    
    # 3. TRANSLATE: Convert strings to domain types with error handling
    try:
        typed_field = DomainType(raw_field)
    except (ValueError, TypeError):
        return TranslationError("Invalid 'required_field' format"), None
    
    # 4. RETURN: Domain object (NOT HTTP response)
    domain_object = DomainObject(field=typed_field, ...)
    return None, domain_object

# Separate function handles domain operations:
async def http_handler(request: Request, manager: Manager) -> tuple[dict[str, str], int]:
    # Use translator for conversion only
    error, domain_object = await translator_function(request)
    if error:
        return {"error": error.message}, error.status_code
    
    # Domain operations happen here, not in translator
    system_storage: SystemStorage = request.app.state.system_storage
    existing = system_storage.get_something(domain_object.field)
    
    if existing is None:
        return {"error": "Object not found"}, 404
    
    manager.do_something(domain_object)
    return {"message": "Success"}, 200
```

## Architectural Layers

```
┌─────────────────┐
│   HTTP Request  │ ← JSON strings, raw data
│   (Network)     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   TRANSLATOR    │ ← Convert strings → domain types
│   (Boundary)    │   Return domain objects OR errors
└─────────────────┘   (NO domain operations)
         │
         ▼
┌─────────────────┐
│  HTTP Handler   │ ← Use converted domain objects
│  (Application)  │   Call SystemStorage/Manager
└─────────────────┘   Return HTTP responses
         │
         ▼
┌─────────────────┐
│ SystemStorage   │ ← Receive typed domain objects
│ Manager         │   UUID objects, not strings
│ (Domain)        │
└─────────────────┘
```

## Key Responsibilities

### Translator Functions SHOULD:
- Convert JSON strings to proper domain types (UUID, datetime, etc.)
- Handle conversion errors and return structured error objects
- Validate required fields are present
- Return domain objects for the calling context to use
- Be context-specific to the request type and target domain objects

### Translator Functions SHOULD NOT:
- Call `SystemStorage` or `Manager` directly
- Perform domain operations or business logic
- Return HTTP status codes (return domain objects instead)
- Use domain validation functions (like `valid_uuid()`) for boundary conversion
- Handle database transactions or persistence

## Functions to Audit

Functions that SHOULD be translators can be identified by:
1. **Input**: Takes `Request` parameter
2. **Purpose**: Converts request data to domain objects
3. **Context**: Needs to work with specific request types and domain objects

Functions that are INCORRECTLY mixing translation with domain operations:
1. **Anti-pattern**: Takes `Request` AND calls `SystemStorage`/`Manager` in same function
2. **Anti-pattern**: Returns HTTP responses directly instead of domain objects
3. **Location**: Typically in `src/prodhost/server/apis/*/functions/event_handlers/`

## Next Steps

1. **Scan**: Find all functions matching the translator pattern
2. **Audit**: Check each for consistent string-to-domain-type conversion
3. **Standardize**: Apply the correct pattern to all translator functions
4. **Document**: List specific instances that need fixes

---

## Protocol-Based Design

### Translator Protocol

All translator functions should implement this protocol to ensure consistent error handling and type safety:

```python
from typing import Protocol
from dataclasses import dataclass
from starlette.requests import Request

@dataclass
class TranslatorError:
    """Standardized error response for translator functions"""
    message: str
    status_code: int = 400
    
    def to_response(self) -> tuple[dict[str, str], int]:
        return {"error": self.message}, self.status_code

class TranslatorFunction[T](Protocol):
    """Protocol for all translator functions"""
    
    def __call__(self, request: Request, *args, **kwargs) -> tuple[TranslatorError | None, T | None]:
        """
        Convert HTTP request to domain objects
        
        Args:
            request: HTTP request with JSON data
            *args, **kwargs: Additional dependencies (Manager, SystemStorage, etc.)
            
        Returns:
            (error, None) if translation failed
            (None, domain_object) if translation succeeded
        """
        ...
```

### Standard Error Types

```python
class TranslatorErrors:
    """Standard error responses for common translator failures"""
    
    @staticmethod
    def missing_field(field_name: str) -> TranslatorError:
        return TranslatorError(f"Missing '{field_name}' field")
    
    @staticmethod
    def invalid_uuid(field_name: str) -> TranslatorError:
        return TranslatorError(f"Invalid '{field_name}' format")
    
    @staticmethod
    def invalid_format(field_name: str, expected_type: str) -> TranslatorError:
        return TranslatorError(f"Invalid '{field_name}' format, expected {expected_type}")
    
    @staticmethod
    def not_found(resource_type: str) -> TranslatorError:
        return TranslatorError(f"{resource_type} not found", 404)
```

### Domain-Centric Return Types

Instead of returning HTTP responses directly, translators should return domain objects:

```python
@dataclass
class WatcherConfirmation:
    """Domain object for confirmed watcher setup"""
    process_id: uuid.UUID
    function_name: str
    watch_attempt: WatchAttempt
    module_file: str | None = None
    module_name: str | None = None

@dataclass
class ProcessRegistration:
    """Domain object for process registration"""
    process_id: uuid.UUID
    process: Process
    system_identification: SystemIdentification
```

### Example Implementation

```python
import uuid
from datetime import datetime, timezone
from starlette.requests import Request
from prodhost.manager.data.manager import Manager
from prodhost.manager.data.watch_attempt import WatchAttempt

async def confirm_watcher_translator(
    request: Request
) -> tuple[TranslatorError | None, WatcherConfirmation | None]:
    """Translate confirm watcher request to domain objects"""
    
    # 1. Extract JSON data
    data = await request.json()
    
    # 2. Validate required fields
    process_id_str = data.get("process_id")
    if process_id_str is None:
        return TranslatorErrors.missing_field("process_id"), None
    
    function_name = data.get("function_name")
    if not function_name:
        return TranslatorErrors.missing_field("function_name"), None
    
    # 3. Convert to domain types
    try:
        process_id = uuid.UUID(process_id_str)
    except (ValueError, TypeError):
        return TranslatorErrors.invalid_uuid("process_id"), None
    
    # 4. Validate domain constraints
    system_storage = request.app.state.system_storage
    process = system_storage.get_process(process_id)
    if process is None:
        return TranslatorErrors.not_found("Process"), None
    
    # 5. Create domain objects
    finder_result = data.get("finder_result")
    watch_attempt = WatchAttempt(
        process_id=process_id,
        function_name=function_name,
        success=True,
        added_at=datetime.now(timezone.utc),
        module_file=finder_result.get("module_file") if finder_result else None,
        module_name=finder_result.get("module_name") if finder_result else None,
    )
    
    # 6. Return domain object
    confirmation = WatcherConfirmation(
        process_id=process_id,
        function_name=function_name,
        watch_attempt=watch_attempt,
        module_file=finder_result.get("module_file") if finder_result else None,
        module_name=finder_result.get("module_name") if finder_result else None,
    )
    
    return None, confirmation

# HTTP handler becomes thin wrapper
async def confirm_watcher(
    request: Request, manager: Manager
) -> tuple[dict[str, str], int]:
    """HTTP handler for confirm watcher endpoint"""
    
    err, watcher_confirmation = await confirm_watcher_translator(request, manager)
    if err:
        return err.to_response()
    
    # Use domain objects with manager
    manager.add_watch_attempt(watcher_confirmation.watch_attempt)
    manager.add_watcher(
        function_name=watcher_confirmation.function_name,
        module_file=watcher_confirmation.module_file,
        module_name=watcher_confirmation.module_name,
    )
    
    return {"message": "Success"}, 200
```

### Usage Pattern

The consistent pattern across all translator functions:

```python
# Simple, explicit error handling
err, domain_object = await translator_function(request, dependencies)
if err:
    return err.to_response()

# Work with properly typed domain objects
do_business_logic(domain_object)
return {"message": "Success"}, 200
```

This approach provides:
- **Type Safety**: Protocol ensures consistent signatures
- **Explicit Error Handling**: Clear `err, result = translate(...)` pattern
- **Modern Python**: Uses PEP 695 generics and union syntax
- **Standardized Errors**: Reusable error types with consistent HTTP responses
- **Domain Focus**: Return domain objects, not HTTP responses
- **Separation of Concerns**: Translation logic separate from HTTP handling
- **Testability**: Domain objects easier to test than HTTP responses