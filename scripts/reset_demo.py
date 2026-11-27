"""Create or restore the public demo institution (Fase 5 G2).

    python -m scripts.reset_demo

The worker restores it every night at 03:00 when DEMO_ENABLED=true.
"""

from app.db.database import engine
from app.services.demo import reset_demo


def main() -> None:
    summary = reset_demo(engine)
    print("Demo lista:", ", ".join(f"{key}={value}" for key, value in summary.items()))


if __name__ == "__main__":
    main()
