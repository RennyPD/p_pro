"""Send pending emails and retry failed ones (audit M6).

Schedule it every few minutes in production (cron or a task scheduler):
    python -m scripts.send_emails
Delivery also happens right after each request that queues an email; this
command covers retries and messages queued by scheduled jobs.
"""

from app.db.database import engine
from app.services.email_service import deliver_pending


def main() -> None:
    total = {"sent": 0, "failed": 0}
    while True:
        result = deliver_pending(engine)
        total = {key: total[key] + result[key] for key in total}
        if result["sent"] + result["failed"] == 0:
            break
    print(f"Correos enviados: {total['sent']}; fallidos definitivamente: {total['failed']}")


if __name__ == "__main__":
    main()
