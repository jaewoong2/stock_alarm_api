"""Database utility functions for safer transaction handling."""

import functools
import logging
from typing import Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def db_transaction_safe(func: Callable) -> Callable:
    """
    Decorator to safely handle database transactions.
    Automatically rolls back the session on any exception.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Repository 인스턴스에서 db_session 속성을 찾습니다
        db_session = None
        if hasattr(args[0], "db_session"):
            db_session = args[0].db_session

        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            if db_session:
                try:
                    db_session.rollback()
                    logger.warning(
                        f"Database transaction rolled back due to SQLAlchemy error: {e}"
                    )
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise e
        except Exception as e:
            if db_session:
                try:
                    db_session.rollback()
                    logger.warning(
                        f"Database transaction rolled back due to error: {e}"
                    )
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise e

    return wrapper


def db_async_transaction_safe(func: Callable) -> Callable:
    """
    Async version of the database transaction safety decorator.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Repository 인스턴스에서 db_session 속성을 찾습니다
        db_session = None
        if hasattr(args[0], "db_session"):
            db_session = args[0].db_session

        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
            if db_session:
                try:
                    db_session.rollback()
                    logger.warning(
                        f"Database transaction rolled back due to SQLAlchemy error: {e}"
                    )
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise e
        except Exception as e:
            if db_session:
                try:
                    db_session.rollback()
                    logger.warning(
                        f"Database transaction rolled back due to error: {e}"
                    )
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback transaction: {rollback_error}")
            raise e

    return wrapper


def safe_db_operation(db_session: Session, operation: Callable):
    """
    Execute a database operation safely with automatic rollback on error.

    Args:
        db_session: SQLAlchemy session
        operation: Callable that performs the database operation

    Returns:
        Result of the operation

    Raises:
        Exception: Re-raises any exception after rolling back the session
    """
    try:
        return operation()
    except Exception as e:
        try:
            db_session.rollback()
            logger.warning(f"Database operation failed, transaction rolled back: {e}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise e
