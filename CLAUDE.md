Backend Performance

- MUST: Use async/await for I/O operations
- MUST: Implement database query optimization
- SHOULD: Use caching for expensive operations
- SHOULD: Implement pagination for large datasets
- SHOULD: Monitor API response times

Python/FastAPI Rules - General Principles

- MUST: Follow PEP 8 style guide
- MUST: Use type hints for all function parameters and return values
- MUST: Use async/await for I/O operations
- SHOULD: Use descriptive variable and function names
- SHOULD: Keep functions small and focused

FastAPI Specific

- MUST: Use Pydantic models for request/response validation
- MUST: Use dependency injection for database sessions and auth
- MUST: Define proper HTTP status codes for responses
- MUST: Use proper exception handling with HTTPException
- SHOULD: Group related endpoints in separate router files
- SHOULD: Use response_model for endpoint documentation

Database & Models

- MUST: Use SQLAlchemy async for database operations
- MUST: Define separate Pydantic schemas for create/update/read operations
- MUST: Use proper database migrations with Alembic
- SHOULD: Use database transactions for data consistency
- SHOULD: Implement proper database indexing
