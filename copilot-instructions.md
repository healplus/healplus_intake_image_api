# Copilot Instructions for HealPlus Intake Image API

## Project Overview
HealPlus Intake Image API is a FastAPI-based application designed to handle image intake operations for the HealPlus healthcare platform.

**Stack:**
- **Framework:** FastAPI (with standard dependencies)
- **Python:** ≥3.12
- **Package Manager:** uv
- **Build System:** uv_build

## Project Structure
```
src/healplus_intake_image_api/
├── __init__.py           # Package initialization
├── main.py              # FastAPI application entry point
├── core/                # Core configuration and utilities
├── api/                 # API route handlers
├── models/              # Data models (ORM, Pydantic)
├── schemas/             # Request/response schemas
├── services/            # Business logic layer
└── repositories/        # Data access layer
```

## Key Development Guidelines

### 1. Code Organization
- **Routes:** Place all endpoint definitions in `api/` directory
- **Business Logic:** Implement in `services/` layer
- **Data Access:** Use `repositories/` for database operations
- **Models:** Define Pydantic models in `schemas/` for request/response validation
- **ORM Models:** Store database models in `models/` directory

### 2. FastAPI Standards
- Use type hints for all function parameters and return types
- Leverage Pydantic for automatic validation and documentation
- Implement proper HTTP status codes and error handling
- Use dependency injection for services and repositories
- Document endpoints with docstrings for auto-generated OpenAPI docs

### 3. Python Code Style
- Minimum Python version: 3.12 (use modern Python features)
- Follow PEP 8 conventions
- Use type hints extensively for better IDE support and type safety
- Avoid mutable default arguments
- Use f-strings for string formatting

### 4. Dependencies
Currently installed:
- `fastapi[standard]>=0.141.1` - Web framework with all standard extras

To add new dependencies: modify `pyproject.toml` and run `uv sync`

### 5. Running the Application
```bash
# Install dependencies
uv sync

# Run development server
uv run fastapi dev src/healplus_intake_image_api/main.py
```

### 6. Project Goals
- Build a robust API for image intake operations
- Maintain clean separation of concerns (routes → services → repositories)
- Ensure type safety and automatic API documentation
- Support healthcare data handling requirements

## Best Practices for AI Assistance
When requesting code changes from Copilot:
- Specify the module/directory where changes should be made
- Provide examples of expected behavior or schemas
- Request full implementations rather than partial code
- Include error handling and type annotations in responses
- Ask for tests when implementing critical features
- Request documentation updates when changing APIs

## Important Notes
- The project uses `uv` as the package manager (faster alternative to pip)
- Generated CLI entry point: `healplus-intake-image-api`
- Main application instance is `app` in `main.py`
- Author: wolley silva (wolleyws@gmail.com)
