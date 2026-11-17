from datetime import UTC, date, datetime, timedelta, timezone

from app.services.business_time import business_date


def test_institutional_date_uses_santo_domingo_midnight():
    assert business_date(datetime(2026, 1, 2, 3, 59, tzinfo=UTC)) == date(2026, 1, 1)
    assert business_date(datetime(2026, 1, 2, 4, 0)) == date(2026, 1, 2)
    offset = timezone(timedelta(hours=1))
    assert business_date(datetime(2026, 1, 2, 4, 59, tzinfo=offset)) == date(2026, 1, 1)
