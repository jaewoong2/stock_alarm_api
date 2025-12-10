"""Repository for API key management and usage tracking"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import date, datetime
from typing import Literal, Optional
import logging

from myapi.domain.api_key.api_key_models import APIKey, APIKeyUsage

logger = logging.getLogger(__name__)


class ApiKeyRepository:
    """Handles database operations for API keys and usage tracking"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_available_key(
        self, provider: Literal["GEMINI", "OPENAI"]
    ) -> Optional[APIKey]:
        """
        Get an available API key for the specified provider.
        Selects keys that haven't exceeded their quota for today,
        prioritizing by priority field and then by usage count.

        Args:
            provider: Provider name ('GEMINI', 'OPENAI', etc.)

        Returns:
            APIKey object if available, None if all keys are exhausted
        """
        today = date.today()

        query = (
            self.db.query(APIKey)
            .outerjoin(
                APIKeyUsage,
                and_(
                    APIKey.id == APIKeyUsage.api_key_id, APIKeyUsage.usage_date == today
                ),
            )
            .filter(
                APIKey.provider == provider,
                APIKey.is_active == True,
                # Only keys under quota limit
                func.coalesce(APIKeyUsage.request_count, 0) < APIKey.quota_limit,
            )
            .order_by(
                APIKey.priority.asc(),  # Lower priority value = higher priority
                func.coalesce(APIKeyUsage.request_count, 0).asc(),  # Least used first
            )
            .limit(1)
        )

        result = query.first()

        if result:
            logger.info(
                f"Selected {provider} key (ID: {result.id}, Priority: {result.priority})"
            )
        else:
            logger.warning(f"No available {provider} keys found")

        return result

    def increment_usage(self, api_key_id: int) -> None:
        """
        Increment usage count for an API key.
        Creates a new usage record if one doesn't exist for today.

        Args:
            api_key_id: ID of the API key to increment
        """
        today = date.today()

        try:
            usage = (
                self.db.query(APIKeyUsage)
                .filter(
                    APIKeyUsage.api_key_id == api_key_id,
                    APIKeyUsage.usage_date == today,
                )
                .first()
            )

            if usage:
                # Update existing record directly
                usage.request_count += 1
                usage.last_request_at = datetime.now()
                logger.debug(
                    f"Incremented usage for key {api_key_id} to {usage.request_count}"
                )
            else:
                usage = APIKeyUsage(
                    api_key_id=api_key_id,
                    usage_date=today,
                    request_count=1,
                    last_request_at=datetime.now(),
                )
                self.db.add(usage)
                logger.debug(f"Created new usage record for key {api_key_id}")

            self.db.commit()

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to increment usage for key {api_key_id}: {e}")

    def get_usage_today(self, api_key_id: int) -> int:
        """
        Get today's usage count for an API key.

        Args:
            api_key_id: ID of the API key

        Returns:
            Number of requests made today
        """
        today = date.today()

        usage = (
            self.db.query(APIKeyUsage)
            .filter(
                APIKeyUsage.api_key_id == api_key_id, APIKeyUsage.usage_date == today
            )
            .first()
        )

        count = usage.request_count if usage else 0

        return int(count.real)
