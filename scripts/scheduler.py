"""Scheduled jobs worker (Fase 4 C): emails, daily billing and reminders.

    python -m scripts.scheduler          # runs until stopped (SIGTERM / Ctrl+C)
    python -m scripts.scheduler --once   # runs what is due now and exits

In Docker it is the ``worker`` service. Several replicas are safe: with
PostgreSQL only one holds the lock and runs jobs; the others stand by.
"""

import argparse
import logging
import signal
import threading
from datetime import UTC, datetime

from app.db.database import engine
from app.logging_config import configure_logging
from app.observability import init_sentry
from app.services.scheduler import acquire_leadership, run_due, still_leader

logger = logging.getLogger("nexo.scheduler")
TICK_SECONDS = 30


def main() -> None:
    parser = argparse.ArgumentParser(description="Tareas programadas de Nexo")
    parser.add_argument("--once", action="store_true", help="Ejecuta lo pendiente y termina")
    args = parser.parse_args()
    configure_logging()
    init_sentry()
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    last_runs: dict[str, datetime] = {}
    leader = None
    while not stop.is_set():
        if leader is not None and not still_leader(leader):
            leader = None
        if leader is None:
            leader = acquire_leadership(engine)
            if leader is None:
                logger.info("scheduler_standby")
        if leader is not None:
            run_due(engine, last_runs, datetime.now(UTC))
        if args.once:
            break
        stop.wait(TICK_SECONDS)
    if leader is not None:
        leader.close()  # releases the advisory lock
    logger.info("scheduler_stopped")


if __name__ == "__main__":
    main()
