from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    Drop-in replacement for the deprecated ``datetime.utcnow()`` — same value
    (naive, in UTC) but without the DeprecationWarning. Intentionally kept naive
    to match the existing ``DateTime`` columns and ``.timestamp()`` comparisons,
    so stored values and behaviour are unchanged.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
