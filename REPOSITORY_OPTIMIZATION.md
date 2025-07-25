# Repository Optimization Guide

Repositories are responsible for communicating with the database. Efficient queries are key to fast GET endpoints.

## Query Efficiency

- **Ensure indexes** on frequently filtered columns such as `symbol`, `date`, and foreign keys.
- **Use joined or subquery loading** with SQLAlchemy to avoid N+1 query problems.
- Prefer selecting only necessary columns rather than using `*`.

## Bulk Operations

- Use bulk creation and updates where applicable to reduce commit overhead.
- Avoid per-row queries in loops by using `IN` clauses or set-based operations.

## Connection Management

- Use session pooling and proper session scoping. Close sessions promptly to free resources.
- For read-heavy endpoints, consider read replicas or caching layers.

## Code Review Summary

The repository layer resides in `myapi/repositories`.

- `ticker_repository.get_ticker_order_by` (lines 217-309) builds several
  subqueries to calculate daily changes. Ensure indexes on `Ticker.symbol` and
  `Ticker.date` to support the joins and order-by operations. Using SQLAlchemy's
  `selectinload` for related entities avoids additional queries.
- Simple getters such as `get_by_symbol_and_date` rely on equality filters and
  benefit from combined indexes (`symbol`, `date`).
- Use `bulk_save_objects` carefully and wrap bulk operations in transactions to
  minimize commit overhead.
