# Copilot Instructions for HealPlus Intake Image API

## Project Overview
HealPlus Intake Image API is a FastAPI-based application for receiving and processing medical images according to HL7 FHIR R4 standards. Images are received for analysis by the HealPlus Core module.

**Stack:**
- **Framework:** FastAPI (with standard dependencies)
- **Python:** ≥3.12
- **ORM:** SQLAlchemy 2.1+
- **Database:** PostgreSQL
- **Validation:** Pydantic v2
- **Package Manager:** uv
- **Build System:** uv_build

## Project Structure
```
src/healplus_intake_image_api/
├── __init__.py                # Package initialization
├── main.py                    # FastAPI application entry point
├── core/
│   ├── config.py             # Settings management (environment variables)
│   └── database.py           # Database connection and session management
├── api/
│   └── routes/
│       └── image.py          # Image endpoints (HTTP layer)
├── models/
│   └── image.py              # SQLAlchemy ORM models
├── schemas/
│   └── image.py              # Pydantic request/response schemas
├── services/
│   └── image.py              # Business logic with error handling
└── repositories/
    └── image.py              # Data access layer (pure DB operations)
```

## Architecture: 3-Layer Pattern

```
HTTP Request
    ↓
[Routes] - HTTP layer, endpoint definitions
    ↓
[Services] - Application logic, error handling, logging
    ↓
[Repositories] - Data access, DB operations
    ↓
PostgreSQL Database
```

### Layer Responsibilities

**Routes (`api/routes/`)**
- Handle HTTP requests/responses
- Validate input with Pydantic schemas
- Return appropriate HTTP status codes
- Delegate to services (no DB access)

**Services (`services/`)**
- Orchestrate business logic
- Call repositories for data access
- Implement error handling with try/except
- Map exceptions to HTTP status codes
- Log all errors and important events
- Perform db.rollback() on exceptions

**Repositories (`repositories/`)**
- Pure data access operations
- db.query(), db.add(), db.commit(), db.refresh()
- No error handling or business logic
- No HTTP/service layer dependencies

## Key Development Guidelines

### 1. Error Handling Pattern
All database operations in services must follow this pattern:

```python
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

def create_image(db: Session, image: ImageCreate) -> Image:
    try:
        return repo_create_image(db, image)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Resource conflict")
    except OperationalError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
```

**HTTP Status Codes:**
- `201 Created` - Resource successfully created
- `409 Conflict` - IntegrityError (duplicate key, constraint violation)
- `503 Service Unavailable` - OperationalError (DB connection issues)
- `500 Internal Server Error` - Unexpected exceptions
- `404 Not Found` - Resource doesn't exist
- `400 Bad Request` - Validation error (automatic via Pydantic)

### 2. Database Session Management
Use the `get_db()` dependency from `core/database.py`:

```python
def endpoint(db: Session = Depends(get_db)):
    # Session auto-rollback on exception, auto-close in finally
    pass
```

**Session guarantees:**
- Automatic rollback on exceptions
- Automatic close in finally block
- No manual close() or rollback() needed in route handlers

### 3. Logging
Import and use logging in services:

```python
import logging
logger = logging.getLogger(__name__)

logger.error(f"Database error: {e}")  # For errors
logger.info(f"Operation completed")   # For important events
```

### 4. Type Hints & Documentation
All functions must have:
- Type hints for parameters and return values
- Docstring with Args, Returns, Raises sections
- Example:

```python
def get_image(db: Session, image_id: int) -> Image | None:
    """Retrieve an image by ID.
    
    Args:
        db: Database session
        image_id: Image identifier
        
    Returns:
        Image if found, None otherwise
        
    Raises:
        HTTPException: On database errors
    """
```

### 5. FastAPI Standards
- Use type hints for all parameters and returns
- Leverage Pydantic for validation
- Set appropriate HTTP status codes with `status_code=`
- Add docstrings to all route handlers
- Use dependency injection via `Depends()`

### 6. Dependencies
Currently installed:
- `fastapi[standard]>=0.141.1` - Web framework
- `sqlalchemy>=2.1.1` - ORM
- `psycopg[binary]>=3.3.6` - PostgreSQL driver
- `pydantic-settings>=2.15.0` - Settings management

To add dependencies:
```bash
# Add to pyproject.toml, then:
uv sync
```

### 7. Running the Application
```bash
# Install/sync dependencies
uv sync

# Run development server
uv run fastapi dev src/healplus_intake_image_api/main.py
```

## Current Implementation Status

### ✅ Completed
- 3-layer architecture (Routes → Services → Repositories)
- Error handling with proper HTTP status codes
- Database session management with rollback
- Type hints and docstrings
- Logging integration
- Basic CRUD for images (GET, POST endpoints)

### ⏳ TODO (From Requirements)
- FHIR Bundle support (multiple images per request)
- Media resource implementation
- analysisId generation and tracking
- Analysis status tracking (ACCEPTED, QUEUED, PROCESSING, COMPLETED, FAILED)
- Async processing with background tasks
- Webhook integration (HealPlus Core + Client notifications)
- Authentication and client credentials
- Comprehensive test suite

## Best Practices for AI Assistance
When requesting code changes:
- Specify the layer affected (routes, services, repositories)
- Include error handling in all service implementations
- Add logging for debugging
- Provide type hints and docstrings
- Request full implementations, not partial code
- Ask for tests when implementing features
- Update documentation when changing APIs

## Important Notes
- Database credentials are managed via `.env` file (DO NOT COMMIT credentials)
- Use `pool_pre_ping=True` for connection health checks
- Session lifecycle is managed by `get_db()` dependency
- All database errors should be caught and mapped to HTTP responses
- Use modern Python 3.12+ features (union types with `|`, etc.)
- Author: wolley silva (wolleyws@gmail.com)
