"""Add complete, clearly fictitious teacher dossiers without modifying existing data.

Preview by default; --apply creates a SQLite backup and inserts atomically.
Does not create login accounts, sections, or teaching assignments.
"""

import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.schemas.teacher_schema import TeacherCreate

BACKUP_DIRECTORY = Path(__file__).resolve().parents[1] / "backups"


def teacher_examples():
    profiles = [
        (
            "Mariana",
            "Valdez Demo",
            "Didáctica y evaluación educativa",
            "Educación",
            "Doctorado en Educación",
            "Titular",
            "full_time",
            18,
        ),
        (
            "Gabriel",
            "Peña Demo",
            "Ingeniería de software y pruebas",
            "Tecnología",
            "Maestría en Ingeniería de Software",
            "Adjunto",
            "part_time",
            10,
        ),
        (
            "Camila",
            "Rosario Demo",
            "Contabilidad financiera y auditoría",
            "Ciencias Empresariales",
            "Maestría en Auditoría",
            "Instructor",
            "adjunct",
            7,
        ),
        (
            "Andrés",
            "Pimentel Demo",
            "Álgebra y estadística aplicada",
            "Ciencias Básicas",
            "Licenciatura en Matemáticas",
            "Auxiliar",
            "substitute",
            3,
        ),
        (
            "Valeria",
            "Núñez Demo",
            "Mercadeo digital e investigación de mercados",
            "Ciencias Empresariales",
            "Maestría en Mercadeo",
            "Titular",
            "full_time",
            14,
        ),
        (
            "Samuel",
            "Báez Demo",
            "Redes, infraestructura y ciberseguridad",
            "Tecnología",
            "Maestría en Ciberseguridad",
            "Adjunto",
            "part_time",
            9,
        ),
        (
            "Isabel",
            "Matos Demo",
            "Comunicación escrita y literatura",
            "Humanidades",
            "Maestría en Lingüística Aplicada",
            "Instructor",
            "adjunct",
            6,
        ),
        (
            "Diego",
            "Tavárez Demo",
            "Inglés académico y profesional",
            "Idiomas",
            "Licenciatura en Lenguas Modernas",
            "Auxiliar",
            "substitute",
            2,
        ),
        (
            "Renata",
            "Cabrera Demo",
            "Gestión de proyectos e innovación",
            "Ciencias Empresariales",
            "Doctorado en Administración",
            "Titular",
            "full_time",
            16,
        ),
        (
            "Leonardo",
            "Santana Demo",
            "Física y laboratorio experimental",
            "Ciencias Básicas",
            "Maestría en Física Aplicada",
            "Adjunto",
            "part_time",
            11,
        ),
        (
            "Elena",
            "Peralta Demo",
            "Diseño de interfaces y experiencia de usuario",
            "Tecnología",
            "Maestría en Diseño de Interacción",
            "Instructor",
            "adjunct",
            5,
        ),
        (
            "Tomás",
            "Feliz Demo",
            "Orientación y acompañamiento estudiantil",
            "Educación",
            "Maestría en Orientación Educativa",
            "Auxiliar",
            "substitute",
            4,
        ),
    ]
    result = []
    for index, (
        first,
        last,
        specialty,
        department,
        degree,
        category,
        employment,
        years,
    ) in enumerate(profiles, 1):
        result.append(
            TeacherCreate(
                first_name=first,
                last_name=last,
                specialty=specialty,
                email=f"docente.demo.{index:02d}@example.com",
                telephone=f"809-000-{100 + index:04d}",
                address=f"Calle Ficticia {index}, Residencial de Pruebas, Santo Domingo (dirección ficticia)",
                active=index <= 10,
                employee_code=f"DEMO-DOC-{index:03d}",
                document_number=f"DEMO-NO-VALIDO-{index:03d}",
                birth_date=date(2026 - years - 25, (index - 1) % 12 + 1, 12),
                nationality="Dominicana",
                academic_degree=degree,
                alma_mater="Universidad Ficticia Horizonte de Pruebas",
                professional_license=f"DEMO-REG-{index:03d} (sin validez)",
                experience_years=years,
                department=department,
                teaching_category=category,
                employment_type=employment,
                appointment_date=date(2026 - min(years, 8), 1, 15),
                emergency_contact_name=f"Contacto Ficticio {index:02d} Demo",
                emergency_contact_phone=f"809-000-{200 + index:04d}",
                emergency_contact_relationship=("Hermana", "Padre", "Cónyuge", "Madre")[
                    (index - 1) % 4
                ],
            ).model_dump(mode="json")
        )
    return result


def seed(database: Path, apply=False):
    database = database.resolve(strict=True)
    examples = teacher_examples()
    with sqlite3.connect(
        database.as_uri() + ("?mode=rw" if apply else "?mode=ro"),
        uri=True,
        timeout=30,
        isolation_level=None,
    ) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if apply:
            db.execute("BEGIN IMMEDIATE")
        try:
            existing = db.execute("SELECT * FROM teachers ORDER BY teacher_id").fetchall()
            tables = [
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            counts = {
                table: db.execute(
                    'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
                ).fetchone()[0]
                for table in tables
            }
            new = []
            for example in examples:
                match = db.execute(
                    "SELECT employee_code,email FROM teachers WHERE employee_code=? OR email=?",
                    (example["employee_code"], example["email"]),
                ).fetchall()
                if match and match != [(example["employee_code"], example["email"])]:
                    raise ValueError(
                        "Un registro existente entra en conflicto con los ejemplos; no se ha modificado."
                    )
                if not match:
                    new.append(example)
            result = {
                "database": str(database),
                "applied": False,
                "existing_teachers": len(existing),
                "to_insert": len(new),
                "already_present": len(examples) - len(new),
                "examples": [
                    {
                        key: item[key]
                        for key in (
                            "employee_code",
                            "first_name",
                            "last_name",
                            "employment_type",
                            "active",
                        )
                    }
                    for item in examples
                ],
            }
            if not apply or not new:
                if apply:
                    db.commit()
                return result
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError(
                    "La base presenta errores de integridad previos; no se modificará."
                )
            backup = BACKUP_DIRECTORY / f"teachers-before-{uuid4().hex}.db"
            backup.parent.mkdir(exist_ok=True)
            with (
                sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source,
                sqlite3.connect(backup) as target,
            ):
                source.backup(target)
            tenant_column = any(
                row[1] == "institution_id"
                for row in db.execute("PRAGMA table_info(teachers)").fetchall()
            )
            for example in new:
                if tenant_column:
                    # Demo data belongs to the first institution (Fase 4 A).
                    example = {"institution_id": 1, **example}
                columns = ",".join(example)
                placeholders = ",".join("?" for _ in example)
                db.execute(
                    f"INSERT INTO teachers ({columns}) VALUES ({placeholders})",
                    tuple(example.values()),
                )
            for table, count in counts.items():
                expected = count + (len(new) if table == "teachers" else 0)
                if (
                    db.execute(
                        'SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"'
                    ).fetchone()[0]
                    != expected
                ):
                    raise ValueError(f"Cambio inesperado en {table}")
            for row in existing:
                if (
                    db.execute("SELECT * FROM teachers WHERE teacher_id=?", (row[0],)).fetchone()
                    != row
                ):
                    raise ValueError("Un docente anterior cambió; se revertirá la operación.")
            if (
                db.execute("PRAGMA foreign_key_check").fetchall()
                or db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            ):
                raise ValueError("Falló la verificación de integridad; se revertirá la operación.")
            db.commit()
            result.update(applied=True, backup=str(backup), total_teachers=len(existing) + len(new))
            return result
        except Exception:
            if apply:
                db.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(seed(args.database, args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
