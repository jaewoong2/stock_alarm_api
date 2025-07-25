# Router Optimization Guide

This document describes techniques to improve the response time of GET endpoints in the FastAPI routers.

## General Tips

- **Use `async` functions**: Define asynchronous endpoints for I/O heavy tasks such as database or network calls.
- **Leverage dependency injection**: Keep router functions lightweight by delegating logic to services and repositories.
- **Validate and limit query parameters**: Minimize database work by validating dates and limiting result counts.
- **Return only required fields**: Use Pydantic models with `response_model` and `response_model_exclude_none` to avoid sending unnecessary data.
- **Apply caching where possible**: Frequently requested data (e.g., latest tickers) can be cached using Redis or in-memory caching.

## Example Changes

- Convert blocking functions to asynchronous versions when calling async services.
- Use pagination or filtering parameters for large collections.
- Add proper indexes in the repository layer for fields accessed by routers (e.g., `symbol`, `date`).

## Code Review Summary

The project defines multiple routers under `myapi/routers`.

- `ticker_router.py` contains both synchronous and asynchronous endpoints. For instance,
  `get_latest_tickers_with_changes` is declared as `async` at lines 147-176
  while adjacent endpoints such as `get_ticker` at lines 114-123 remain synchronous.
  Converting these to `async def` and awaiting service calls prevents blocking the
  event loop.
- `signal_router.py` and other routers rely on synchronous service calls.
  They can benefit from the same async conversion and from validating query
  parameters to limit workload.

Overall, prefer async functions with proper dependency injection and ensure each
router limits the amount of data returned in GET requests.
