"""Data rights: full export, a person's record and final deletion (Fase 5, step G4)."""

import io
import zipfile
from datetime import datetime, timedelta

from test_multi_tenant import second_institution
from test_object_storage import PDF, upload
from test_platform import platform_admin, platform_login
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app.models import Institution, PlatformAuditLog, Student, User


def test_full_export_has_every_table_but_no_secrets_nor_other_institutions(demo):  # noqa: F811
    client, sessions, tokens = demo
    second_institution(sessions)
    with sessions() as db:
        student = db.query(Student).filter_by(institution_id=1).first()
        student_id, email = student.student_id, student.email
    upload(client, tokens["admin"], student_id, PDF)
    response = client.get("/data/export.zip", headers=tokens["admin"])
    assert response.status_code == 200, response.text
    assert "nexo-exportacion-" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"LEEME.txt", "datos/students.csv", "datos/users.csv", "datos/grades.csv"} <= names
    assert not any(
        name.startswith(("datos/refresh_tokens", "datos/one_time_tokens")) for name in names
    )
    students = archive.read("datos/students.csv").decode("utf-8-sig")
    assert email in students and "solo@segundo.edu.do" not in students
    users_header = archive.read("datos/users.csv").decode("utf-8-sig").splitlines()[0]
    assert "username" in users_header and "password" not in users_header
    assert "mfa_secret" not in users_header
    documents = [name for name in names if name.startswith("archivos/documents/")]
    assert len(documents) == 1 and archive.read(documents[0]) == PDF
    assert entries(sessions, "data.exported")
    assert client.get("/data/export.zip", headers=tokens["docente"]).status_code == 403


def test_a_students_record_answers_an_access_request(demo):  # noqa: F811
    client, sessions, tokens = demo
    with sessions() as db:
        student_id = db.query(Student).filter_by(institution_id=1).first().student_id
    record = client.get(f"/data/students/{student_id}/record.json", headers=tokens["admin"])
    assert record.status_code == 200, record.text
    body = record.json()
    assert body["estudiante"]["student_id"] == student_id
    assert {"cuentas_de_acceso", "tutores", "inscripciones", "calificaciones", "finanzas"} <= set(
        body
    )
    assert "password" not in record.text and "institution_id" not in body["estudiante"]
    assert entries(sessions, "data.subject_export")
    assert (
        client.get(
            f"/data/students/{student_id}/record.json", headers=tokens["docente"]
        ).status_code
        == 403
    )


def test_final_deletion_waits_90_days_asks_for_the_code_and_spares_others(demo):  # noqa: F811
    client, sessions, tokens = demo
    second_institution(sessions)
    platform = platform_login(client, platform_admin(sessions))
    with sessions() as db:
        own_students = db.query(Student).filter_by(institution_id=1).count()
        segundo = db.get(Institution, 2)
        segundo.status, segundo.status_changed_at = "suspended", datetime.now()
        db.commit()
    body = {"code": "segundo", "reason": "Cancelación sin renovar"}
    too_soon = client.post("/platform/institutions/2/purge", headers=platform, json=body)
    assert too_soon.status_code == 409 and "90 días" in too_soon.json()["detail"]
    listed = client.get("/platform/institutions?q=segundo", headers=platform).json()[0]
    assert listed["purge_available_on"]
    with sessions() as db:
        db.get(Institution, 2).status_changed_at = datetime.now() - timedelta(days=91)
        db.commit()
    wrong = client.post(
        "/platform/institutions/2/purge", headers=platform, json={**body, "code": "otro"}
    )
    assert wrong.status_code == 422
    purged = client.post("/platform/institutions/2/purge", headers=platform, json=body)
    assert purged.status_code == 200, purged.text
    assert purged.json()["status"] == "deleted" and purged.json()["deleted_rows"] > 0
    with sessions() as db:
        assert db.query(Student).filter_by(institution_id=2).count() == 0
        assert db.query(User).filter_by(institution_id=2).count() == 0
        assert db.query(Student).filter_by(institution_id=1).count() == own_students
        assert db.get(Institution, 2).slug == "eliminada-2"
        assert db.query(PlatformAuditLog).filter_by(action="institution.purged").count() == 1
    assert client.get("/students/", headers=tokens["admin"]).status_code == 200
    main = client.post(
        "/platform/institutions/1/purge", headers=platform, json={**body, "code": "principal"}
    )
    assert main.status_code == 409
