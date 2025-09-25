from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
from fastapi import HTTPException

US_MARKET_TZ = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
US_MARKET_CLOSE = time(16, 0)
US_MARKET_CALENDAR = mcal.get_calendar("XNYS")


def get_current_kst_datetime() -> datetime:
    """Return the current datetime in Asia/Seoul timezone."""

    return datetime.now(KST)


def get_current_kst_date() -> date:
    """Return today's date in Asia/Seoul timezone."""

    return get_current_kst_datetime().date()


def to_kst(dt: datetime, assume_tz: tzinfo | None = None) -> datetime:
    """Convert a datetime to Asia/Seoul timezone.

    Naive datetimes are assumed to be in the supplied timezone (UTC by default).
    """

    if dt.tzinfo is None:
        if assume_tz is None:
            return dt
        dt = dt.replace(tzinfo=assume_tz)
    return dt.astimezone(KST)


def to_kst_naive(dt: datetime, assume_tz: tzinfo | None = None) -> datetime:
    """Convert a datetime to naive Asia/Seoul time."""

    return to_kst(dt, assume_tz=assume_tz).replace(tzinfo=None)


def get_latest_market_date(reference_dt: Optional[datetime] = None) -> date:
    """Return the most recent completed US trading day (New York time).

    Args:
        reference_dt: Optional timezone-aware datetime used as the baseline.
            When omitted, the current time in the US market timezone is used.

    Returns:
        The date of the latest finished trading session.
    """

    if reference_dt is None:
        current_ny = datetime.now(US_MARKET_TZ)
    else:
        if reference_dt.tzinfo is None:
            raise ValueError("reference_dt must be timezone-aware")
        current_ny = reference_dt.astimezone(US_MARKET_TZ)

    lookback_start = current_ny.date() - timedelta(days=10)
    lookahead_end = current_ny.date() + timedelta(days=1)

    schedule = US_MARKET_CALENDAR.schedule(
        start_date=lookback_start, end_date=lookahead_end
    )

    if not schedule.empty:
        # Iterate from the latest scheduled session backwards and find the
        # most recent session whose close already passed.
        for session_date in reversed(schedule.index):
            market_close_ts = schedule.loc[session_date, "market_close"].tz_convert(
                US_MARKET_TZ
            )
            if current_ny >= market_close_ts:
                return market_close_ts.date()

        # If the current time is earlier than the first session in the
        # schedule window, fall through to the graceful fallback below.

    # Graceful fallback: mirror the previous behaviour while still avoiding
    # weekends. This path is reached when the schedule is empty (e.g. calendar
    # fetch failure) or when no session in the window has closed yet (e.g. the
    # window was too short).
    market_date = current_ny.date()
    if current_ny.time() < US_MARKET_CLOSE:
        market_date -= timedelta(days=1)

    while market_date.weekday() >= 5:
        market_date -= timedelta(days=1)

    return market_date


def validate_date(
    input_date: date,
    max_past_days: int = 30,
    reference_date: Optional[date] = None,
) -> date:
    """Validate a date is not in the future and not too far in the past.

    Args:
        input_date: The date to validate.
        max_past_days: Maximum number of days in the past allowed.
        reference_date: The baseline "today" date for validation. Defaults
            to the system's current date when not provided.

    Returns:
        The validated date.

    Raises:
        HTTPException: If the date is in the future or too far in the past.
    """

    today = reference_date or date.today()
    if input_date > today:
        raise HTTPException(status_code=400, detail="Date cannot be in the future.")
    if input_date < today - timedelta(days=max_past_days):
        raise HTTPException(
            status_code=400,
            detail=f"Date cannot be older than {max_past_days} days.",
        )
    return input_date
