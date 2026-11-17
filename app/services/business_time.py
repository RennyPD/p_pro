from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

INSTITUTION_TIME_ZONE = ZoneInfo("America/Santo_Domingo")


def business_date(value: datetime | None = None) -> date:
    instant = value if value is not None else datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return instant.astimezone(INSTITUTION_TIME_ZONE).date()
