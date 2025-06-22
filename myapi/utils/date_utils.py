from datetime import date, timedelta
from fastapi import HTTPException


def validate_date(input_date: date, max_past_days: int = 30) -> date:
    """Validate a date is not in the future and not too far in the past.

    Args:
        input_date: The date to validate.
        max_past_days: Maximum number of days in the past allowed.

    Returns:
        The validated date.

    Raises:
        HTTPException: If the date is in the future or too far in the past.
    """
    today = date.today()
    if input_date > today:
        raise HTTPException(status_code=400, detail="Date cannot be in the future.")
    if input_date < today - timedelta(days=max_past_days):
        raise HTTPException(
            status_code=400,
            detail=f"Date cannot be older than {max_past_days} days.",
        )
    return input_date
