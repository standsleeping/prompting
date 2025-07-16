# TRANSLATOR PATTERN

## Problem

Applications need a consistent boundary between the **network layer** (HTTP requests with JSON) and the **domain layer** (typed objects). Without this boundary, type errors and architectural confusion arise.

## The Pattern

**Translators** convert raw HTTP request data into typed domain objects. They are pure conversion functions that:

- **Input**: HTTP requests containing JSON strings
- **Output**: Typed domain objects (NOT domain operations)
- **Return**: Either conversion errors OR domain objects

**Critical**: Translators only convert data. They never perform domain operations.

### Unit vs Integrator Translators

**Unit Translators:**
- Pure conversion using built-in functions
- No imports from other modules
- Direct string-to-type transformation

**Integrator Translators:**
- Call other units/integrators for complex conversion
- May import domain validation functions
- Compose multiple conversions

Both maintain the same responsibility: convert without operating.

## The Correct Pattern

```python
async def translator_function(
    request: Request
) -> tuple[TranslatorError | None, DomainObject | None]:
    # 1. EXTRACT
    data = await request.json()
    
    # 2. VALIDATE PRESENCE
    raw_field = data.get("required_field")
    if raw_field is None:
        return TranslatorError("Missing 'required_field'"), None
    
    # 3. TRANSLATE
    try:
        typed_field = DomainType(raw_field)
    except (ValueError, TypeError):
        return TranslatorError("Invalid 'required_field' format"), None
    
    # 4. RETURN
    return None, DomainObject(field=typed_field)

# Separate handler for domain operations:
async def http_handler(request: Request, domain_service: Service) -> tuple[dict, int]:
    error, domain_object = await translator_function(request)
    if error:
        return {"error": error.message}, error.status_code
    
    # Domain operations happen here
    result = domain_service.process(domain_object)
    return {"message": "Success"}, 200
```

## Architecture

```
┌─────────────────┐
│   HTTP Request  │ ← JSON strings
└─────────────────┘
         │
┌─────────────────┐
│   TRANSLATOR    │ ← String → Type conversion
│                 │   Return objects OR errors
└─────────────────┘   (NO domain operations)
         │
┌─────────────────┐
│  HTTP Handler   │ ← Use converted objects
│                 │   Call domain services
└─────────────────┘
         │
┌─────────────────┐
│ Domain Services │ ← Receive typed objects
└─────────────────┘
```

## Key Rules

### Translators SHOULD:
- Convert JSON to domain types
- Handle conversion errors
- Validate required fields
- Return domain objects
- Be request-specific

### Translators SHOULD NOT:
- Call domain services
- Perform business logic
- Return HTTP responses directly
- Use domain validators for conversion
- Handle persistence

## Protocol-Based Design

### Core Protocol

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class TranslatorError:
    """Standard translator error"""
    message: str
    status_code: int = 400
    
    def to_response(self) -> tuple[dict[str, str], int]:
        return {"error": self.message}, self.status_code

class TranslatorFunction[T](Protocol):
    """Protocol for all translators"""
    
    def __call__(self, request: Request) -> tuple[TranslatorError | None, T | None]:
        """Convert HTTP request to domain object"""
        ...
```

### Standard Errors

```python
class TranslatorErrors:
    """Common translator errors"""
    
    @staticmethod
    def missing_field(field: str) -> TranslatorError:
        return TranslatorError(f"Missing '{field}' field")
    
    @staticmethod
    def invalid_format(field: str, expected: str) -> TranslatorError:
        return TranslatorError(f"Invalid '{field}' format, expected {expected}")
    
    @staticmethod
    def not_found(resource: str) -> TranslatorError:
        return TranslatorError(f"{resource} not found", 404)
```

### Example Implementation

```python
async def create_user_translator(
    request: Request
) -> tuple[TranslatorError | None, UserCreation | None]:
    """Translate user creation request"""
    
    data = await request.json()
    
    # Validate presence
    email = data.get("email")
    if not email:
        return TranslatorErrors.missing_field("email"), None
    
    # Convert types
    try:
        user_id = uuid.UUID(data.get("user_id", str(uuid.uuid4())))
    except (ValueError, TypeError):
        return TranslatorErrors.invalid_format("user_id", "UUID"), None
    
    # Return domain object
    return None, UserCreation(
        user_id=user_id,
        email=email,
        created_at=datetime.now(timezone.utc)
    )

# Thin HTTP handler
async def create_user(request: Request, user_service: UserService) -> tuple[dict, int]:
    err, user_creation = await create_user_translator(request)
    if err:
        return err.to_response()
    
    user_service.create(user_creation)
    return {"message": "User created"}, 200
```

## Usage Pattern

```python
# Consistent error handling
err, domain_object = await translator(request)
if err:
    return err.to_response()

# Work with typed objects
service.process(domain_object)
return {"message": "Success"}, 200
```

## Benefits

- **Type Safety**: Protocol ensures consistency
- **Explicit Errors**: Clear `err, result` pattern
- **Separation**: Translation isolated from business logic
- **Testability**: Domain objects easier to test than HTTP
- **Reusability**: Standard errors across translators