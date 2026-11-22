"""Daily due-date reminders by email (audit M6).

Run once a day (cron or task scheduler), for example at 7:00 in
America/Santo_Domingo:
    python -m scripts.send_due_reminders
Reminders go 3 days before and 1 day after the due date (if still unpaid);
running it twice, or after a missed day, never repeats a reminder.
"""

from sqlalchemy.orm import Session

from app.db.database import engine
from app.services.email_notices import queue_due_reminders
from app.services.email_service import deliver_pending


def main() -> None:
    with Session(bind=engine) as db:
        queued = queue_due_reminders(db)
        db.commit()
    sent = deliver_pending(engine)
    print(f"Recordatorios en cola: {queued}; enviados ahora: {sent['sent']}")


if __name__ == "__main__":
    main()
