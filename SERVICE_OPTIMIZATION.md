# Service Optimization Guide

This guide covers best practices to reduce latency within service classes.

## Asynchronous Operations

- **Adopt async SQLAlchemy sessions** to prevent blocking during database access.
- Where external API calls are made, use `httpx.AsyncClient` or similar libraries.

## Caching

- Cache expensive operations such as AI model calls or heavy calculations.
- Consider using Redis for shared caching across instances.

## Batch Processing

- Where possible, fetch or update data in bulk rather than iterating per row.
- Use list comprehensions and vectorized operations with pandas where applicable.

## Error Handling

- Centralize error handling to avoid repeating try/except blocks in routers.
- Log slow queries and monitor performance metrics.

## Code Review Summary

Several service modules under `myapi/services` perform long-running operations.

- `ticker_service.update_ticker_informations` (lines 320-417) loops through
  pandas data frames and individually inserts records. It already batches writes
  using `bulk_create`; further speedups can be achieved by vectorizing the loop
  with pandas and reducing per-row Python overhead.
- `ticker_service.get_latest_tickers_with_changes` (lines 336-417) iterates over
  each ticker to compute changes. Caching the results or prefetching related
  signals can lower repeated computation costs.
- Many methods call repositories synchronously. Adopting async SQLAlchemy
  sessions allows these methods to be defined with `async def` and awaited in
  routers, reducing blocking behavior.
