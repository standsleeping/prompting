# Translators

Translators are pure conversion functions that transform data representations at architectural boundaries, ensuring type safety and separation of concerns between external systems and domain logic.

## Problem

Applications have multiple boundaries where data representations change:

- **Network ↔ Domain**: JSON strings ↔ typed objects.
- **Database ↔ Domain**: SQL rows ↔ domain entities.
- **Domain ↔ Domain**: Context A objects ↔ Context B objects.
- **Domain ↔ External**: Internal models ↔ third-party APIs.

Without consistent boundary translation, type errors and architectural confusion proliferate.

## The Pattern

**Boundary Translators** convert data representations at architectural boundaries. They are pure conversion functions that:

- **Input**: External representation (JSON, SQL rows).
- **Output**: Internal representation (domain objects, entities).
- **Return**: Either conversion errors OR translated objects.

Translators **only** convert data. They never perform business operations.

### Unit vs. Integrator Translators

**Unit Translators:**

- Pure conversion using built-in functions.
- No dependencies on other modules.
- Direct type transformation.

**Integrator Translators:**

- Compose other translators for complex conversion.
- May use validation functions.
- Orchestrate multiple conversions.

Both maintain the same responsibility: convert without operating.

## Core Pattern

```python
# Generic translator signature
async def boundary_translator[TInput, TOutput](
    input_data: TInput
) -> tuple[TranslatorError | None, TOutput | None]:
    # 1. VALIDATE structure
    if not has_required_fields(input_data):
        return TranslatorError("Missing required fields"), None
    
    # 2. CONVERT types
    try:
        output = convert_to_output_type(input_data)
    except (ValueError, TypeError) as e:
        return TranslatorError(f"Conversion failed: {e}"), None
    
    # 3. RETURN domain representation
    return None, output
```

## Boundary Examples

### Network → Domain
```python
async def http_to_domain_translator(
    request: Request
) -> tuple[TranslatorError | None, UserCommand | None]:
    data = await request.json()
    
    email = data.get("email")
    if not email:
        return TranslatorError("Missing 'email'"), None
    
    try:
        user_id = uuid.UUID(data.get("user_id", str(uuid.uuid4())))
    except (ValueError, TypeError):
        return TranslatorError("Invalid 'user_id' format"), None
    
    return None, UserCommand(user_id=user_id, email=email)
```

### Database → Domain
```python
def db_row_to_domain_translator(
    row: dict[str, object]
) -> tuple[TranslatorError | None, User | None]:
    if not row:
        return TranslatorError("Empty row"), None
    
    try:
        return None, User(
            id=uuid.UUID(row["id"]),
            email=row["email"],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )
    except KeyError as e:
        return TranslatorError(f"Missing column: {e}"), None
    except (ValueError, TypeError) as e:
        return TranslatorError(f"Invalid data format: {e}"), None
```

### Domain → External API
```python
def domain_to_api_translator(
    order: Order
) -> tuple[TranslatorError | None, dict[str, object] | None]:
    try:
        return None, {
            "orderId": str(order.id),
            "customerEmail": order.customer.email,
            "items": [
                {
                    "sku": item.product.sku,
                    "quantity": item.quantity,
                    "priceInCents": int(item.price * 100)
                }
                for item in order.items
            ],
            "totalInCents": int(order.total * 100)
        }
    except AttributeError as e:
        return TranslatorError(f"Missing required attribute: {e}"), None
```

### Cross-Domain Translation
```python
def billing_to_shipping_translator(
    billing_order: BillingOrder
) -> tuple[TranslatorError | None, ShippingRequest | None]:
    if billing_order.status != "PAID":
        return TranslatorError("Order must be paid before shipping"), None
    
    return None, ShippingRequest(
        order_ref=billing_order.id,
        recipient=Address(
            name=billing_order.customer_name,
            street=billing_order.delivery_address,
            postal_code=billing_order.postal_code
        ),
        items=[
            ShippingItem(sku=item.sku, quantity=item.qty)
            for item in billing_order.line_items
        ]
    )
```

## Protocol Design

```python
from dataclasses import dataclass

@dataclass
class TranslatorError:
    """Standard translator error"""
    message: str
    code: str = "TRANSLATION_ERROR"
    
# Generic translator signature using modern syntax
type TranslatorFunction[TInput, TOutput] = (
    callable[[TInput], tuple[TranslatorError | None, TOutput | None]]
)

# Composable translators
class TranslatorChain[T1, T2, T3]:
    """Chain multiple translators"""
    
    def __init__(
        self,
        first: TranslatorFunction[T1, T2],
        second: TranslatorFunction[T2, T3]
    ):
        self.first = first
        self.second = second
    
    def __call__(self, input_data: T1) -> tuple[TranslatorError | None, T3 | None]:
        err, intermediate = self.first(input_data)
        if err:
            return err, None
        
        return self.second(intermediate)
```

## Usage Patterns

### Repository Pattern
```python
class UserRepository:
    def __init__(self, db: Database, translator: TranslatorFunction[dict, User]):
        self.db = db
        self.translator = translator
    
    async def get(self, user_id: uuid.UUID) -> User | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", user_id)
        if not row:
            return None
        
        err, user = self.translator(dict(row))
        if err:
            raise TranslationException(err.message)
        
        return user
```

### API Handler Pattern
```python
async def handle_request[TCommand](
    request: Request,
    translator: TranslatorFunction[Request, TCommand],
    handler: CommandHandler[TCommand]
) -> Response:
    err, command = await translator(request)
    if err:
        return Response({"error": err.message}, status=400)
    
    result = await handler.handle(command)
    return Response({"result": result}, status=200)
```

## Rule Summary

### Translators should:

- Focus solely on data conversion.
- Handle conversion errors gracefully.
- Be composable and reusable.
- Work at specific architectural boundaries.
- Return errors using consistent types.

### Translators should not:

- Perform business logic.
- Access external systems directly.
- Maintain state.
- Handle authentication/authorization.
- Make decisions beyond data validity.

## Benefits

- **Decoupling**: Isolates external representations from domain.
- **Type Safety**: Enforces boundaries with types.
- **Testability**: Pure functions, easy to test.
- **Flexibility**: Swap external systems without changing domain.
- **Consistency**: Uniform error handling across boundaries.