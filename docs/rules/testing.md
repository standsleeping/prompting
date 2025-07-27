# Testing

This document describes the testing infrastructure for this generic web application template.

## Overview

The project includes comprehensive tests covering all major functionality:

- **Unit tests**: Individual function and component testing.
- **Integration tests**: API endpoints and middleware testing.
- **Database tests**: SQL queries and migration testing.
- **Authentication tests**: User login, tokens, sessions.
- **Web interface tests**: Page and form functionality.

## Test Architecture

### Test Organization
- **Centralized fixtures**: All fixtures in `tests/fixtures.py`
- **Boundary mocking**: External systems mocked in `tests/boundaries.py`
- **1:1:1 rule**: One function per file, one test file per function
- **No test classes**: Flat pytest functions for simplicity

### Storage & Database Testing
- **In-memory stores**: Fake implementations for fast unit tests
- **Real database tests**: PostgreSQL with Alembic migrations
- **Automatic cleanup**: Database fixtures handle setup/teardown
- **Test isolation**: Each test runs with clean state

## Test Categories

### Authentication Tests
```python
def test_sign_in_success(test_app):
    """User can sign in with valid credentials"""

def test_generate_token(test_app, test_user_id):
    """User can generate API tokens"""
```

### Database Tests  
```python
def test_create_user(sample_user):
    """Creates user in database"""

def test_token_validation(db_client, query_loader):
    """Validates tokens against database"""
```

### Web Interface Tests
```python
def test_dashboard_shows_coming_soon(test_app, test_user_id):
    """Dashboard shows placeholder content"""
```

## Running Tests

### All Tests
```bash
uv run pytest
```

### Specific Test Categories
```bash
# Database tests only
uv run pytest tests/database/

# Authentication tests only  
uv run pytest tests/server/apis/web/functions/test_sign_*

# Middleware tests only
uv run pytest tests/server/middleware/
```

### Individual Test Files
```bash
uv run pytest tests/path/to/test_file.py::test_function
```

## Test Development

### Writing New Tests
1. **Follow naming**: `test_[function_name].py` for each function
2. **Use fixtures**: Leverage existing fixtures from `tests/fixtures.py`
3. **Mock boundaries**: Use `tests/boundaries.py` for external systems
4. **Declarative docstrings**: "User can sign in" not "Tests sign in"

### Adding Fixtures
All fixtures must be added to `tests/fixtures.py`:

```python
@pytest.fixture
def my_fixture():
    return SomeTestData()
```

### Database Test Setup
Database tests automatically:

- Create temporary test database
- Run all migrations
- Provide clean database per test
- Clean up after test completion

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
pg_ctl status

# Create test database manually if needed
createdb test_db
```

### Import Errors
Ensure package is installed in development mode:
```bash
uv pip install -e .
```