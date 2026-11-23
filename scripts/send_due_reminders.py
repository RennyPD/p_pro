"""Daily due-date reminders by email (audit M6).

Run once a day (cron or task scheduler), for example at 7:00 in
America/Santo_Domingo:
    python -m scripts.send_due_reminders
Reminders go 3 days before and 1 day after the due date (if still unpaid);
running it twice, or after a missed day, never repeats a reminder.
"""

from app.db.database import engine
from app.services.email_notices import queue_due_reminders
from app.services.email_service import deliver_pending
from app.services.tenants import for_each_institution


def main() -> None:
    # Each institution's reminders in its own tenant session (Fase 4 A).
    queued = sum(for_each_institution(engine, queue_due_reminders).values())
    sent = deliver_pending(engine)
    print(f"Recordatorios en cola: {queued}; enviados ahora: {sent['sent']}")


if __name__ == "__main__":
    main()
