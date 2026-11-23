from app.db.database import SessionLocal
from app.db.tenant import mark_request


def get_db():
    db = SessionLocal()
    # A request sees nothing until authentication sets its institution (Fase 4 A).
    mark_request(db)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
