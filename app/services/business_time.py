from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

INSTITUTION_TIME_ZONE = ZoneInfo("America/Santo_Domingo")


def business_date(value: datetime | None = None) -> date:
    instant = value if value is not None else datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(INSTITUTION_TIME_ZONE).date()


def business_day_utc_range(day: date) -> tuple[datetime, datetime]:
    """Naive UTC bounds [start, end) of a local business day, for indexed queries."""
    start = datetime.combine(day, time.min, INSTITUTION_TIME_ZONE)
    end = datetime.combine(day + timedelta(days=1), time.min, INSTITUTION_TIME_ZONE)
    return (
        start.astimezone(UTC).replace(tzinfo=None),
        end.astimezone(UTC).replace(tzinfo=None),
    )
