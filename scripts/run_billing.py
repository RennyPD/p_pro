"""Daily school finance job (Fase 3 E).

Run once a day (cron or task scheduler), for example at 6:30 in
America/Santo_Domingo:
    python -m scripts.run_billing
    python -m scripts.run_billing --simulate   # shows what would happen, changes nothing

It generates the plans' months that fall within the policy's lead days,
applies sibling discounts, late fees and automatic holds (each only when the
finance policy enables it). Running it twice, or after a missed day, never
charges, discounts or fines anyone twice.
"""

import argparse

from sqlalchemy.orm import Session

from app.db.database import engine
from app.services.finance_automation import run_daily


def main() -> None:
    parser = argparse.ArgumentParser(description="Tareas financieras diarias")
    parser.add_argument("--simulate", action="store_true", help="No guarda ningún cambio")
    args = parser.parse_args()
    with Session(bind=engine) as db:
        result = run_daily(db)
        if args.simulate:
            db.rollback()
        else:
            db.commit()
    label = "Simulación" if args.simulate else "Aplicado"
    print(
        f"{label} {result.today}: {len(result.billing_runs)} cobros generados, "
        f"{result.sibling_discounts} descuentos por hermanos, {len(result.late_fees)} recargos, "
        f"{len(result.holds_set)} bloqueos y {len(result.holds_lifted)} desbloqueos"
    )
    for run in result.billing_runs:
        print(f"  Cobro {run['plan']} {run['cycle']}: {run['charges']} cargos, {run['total']}")
    for fee in result.late_fees:
        print(f"  Recargo {fee['student']}: {fee['amount']} ({fee['charge']})")
    for name in result.holds_set:
        print(f"  Bloqueo: {name}")
    for name in result.holds_lifted:
        print(f"  Desbloqueo: {name}")


if __name__ == "__main__":
    main()
