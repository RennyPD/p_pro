"""Disposable real backend for browser acceptance; never opens the normal DB."""

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    run_id = UUID(os.environ.get("NEXO_ACCEPTANCE_ID", uuid4().hex)).hex
    port = int(os.environ.get("NEXO_ACCEPTANCE_PORT", "8012"))
    if port not in {8012, 8013}:
        raise ValueError("Only isolated acceptance ports are allowed")
    output = root / "backups" / f"acceptance-{run_id}"
    # Refuse any existing output, so no demo seed can replace earlier data.
    output.mkdir(parents=True, exist_ok=False)
    os.environ["DATABASE_URL"] = f"sqlite:///{(output / 'acceptance.db').as_posix()}"
    os.environ["APP_ENVIRONMENT"] = "development"
    os.environ["SECRET_KEY"] = "acceptance-tests-only-never-use-for-a-real-installation"
    os.environ["CORS_ORIGINS"] = "http://127.0.0.3:5176"
    os.environ["CORS_ORIGIN_REGEX"] = r"http://127\.0\.0\.3:5176"
    os.environ["FINANCE_TRANSFER_INSTRUCTIONS"] = (
        "SOLO PRUEBAS: cuenta ficticia de aceptación; no realizar transferencias reales."
    )
    os.environ["FINANCE_SIMULATOR_ENABLED"] = "true"
    # Every browser test comes from one address; limits have their own tests.
    os.environ["RATE_LIMITS_ENABLED"] = "false"
    os.environ["STORAGE_DIR"] = (output / "storage").as_posix()

    import uvicorn
    from alembic.config import Config

    from alembic import command

    command.upgrade(Config(str(root / "alembic.ini")), "head")
    from app.db.database import SessionLocal
    from app.models.configuration_model import AcademicPeriod
    from scripts.seed_institution import seed_institution

    with SessionLocal() as db:
        seed_institution(db)
        # Acceptance must remain repeatable after the demo calendar expires.
        period = db.query(AcademicPeriod).filter_by(active=True).one()
        period.registration_start = period.registration_end = period.withdrawal_deadline = None
        db.commit()
    print(f"Acceptance database (disposable): {output}", flush=True)
    uvicorn.run("main:app", host="127.0.0.3", port=port)


if __name__ == "__main__":
    main()
