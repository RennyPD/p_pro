"""Uploaded files outside the database (Fase 4 C, audit M4)."""

import base64

import pytest
from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.db.database import Settings
from app.db.tenant import set_tenant
from app.models import Student, StudentDocument, TransferRequest, User
from app.services import storage
from app.services.file_migration import move, verify

PDF = b"%PDF-1.4\nexpediente de prueba"


def upload(client, token, student_id, content=PDF):
    return client.post(
        f"/operations/students/{student_id}/documents",
        headers=token,
        json={
            "document_type": "acta",
            "filename": "acta.pdf",
            "mime_type": "application/pdf",
            "content_base64": base64.b64encode(content).decode(),
        },
    )


def first_student(sessions) -> int:
    with sessions() as db:
        return db.query(Student).order_by(Student.student_id).first().student_id


def test_uploads_go_to_storage_under_their_institution(demo, isolated_storage):  # noqa: F811
    client, sessions, tokens = demo
    student = first_student(sessions)
    created = upload(client, tokens["admin"], student)
    assert created.status_code == 200, created.text
    with sessions() as db:
        row = db.get(StudentDocument, created.json()["student_document_id"])
        assert row.content is None
        assert row.storage_key.startswith("inst/1/documents/")
        assert row.size_bytes == len(PDF) and row.sha256 == storage.digest(PDF)
        key = row.storage_key
    assert (isolated_storage / key).read_bytes() == PDF
    download = client.get(
        f"/operations/documents/{created.json()['student_document_id']}/download",
        headers=tokens["admin"],
    )
    assert download.status_code == 200 and download.content == PDF
    # The file disappears from storage: a clear Spanish error, not a crash.
    (isolated_storage / key).unlink()
    missing = client.get(
        f"/operations/documents/{created.json()['student_document_id']}/download",
        headers=tokens["admin"],
    )
    assert missing.status_code == 503 and "no está disponible" in missing.json()["detail"]


def test_files_of_a_failed_transaction_are_deleted(demo, isolated_storage):  # noqa: F811
    _client, sessions, _tokens = demo
    with sessions() as db:
        set_tenant(db, 1)
        rolled_back = storage.store(db, "documents", PDF, "application/pdf")
        db.rollback()
    with sessions() as db:
        set_tenant(db, 1)
        closed = storage.store(db, "documents", PDF, "application/pdf")
    with sessions() as db:
        set_tenant(db, 1)
        kept = storage.store(db, "documents", PDF, "application/pdf")
        db.commit()
    assert not (isolated_storage / rolled_back.key).exists()
    assert not (isolated_storage / closed.key).exists()
    assert (isolated_storage / kept.key).read_bytes() == PDF


def test_existing_files_move_verified_and_keep_downloading(demo, isolated_storage):  # noqa: F811
    client, sessions, tokens = demo
    student = first_student(sessions)
    with sessions() as db:
        admin = db.query(User).order_by(User.user_id).first()
        legacy = StudentDocument(
            student_id=student,
            document_type="acta",
            filename="antigua.pdf",
            mime_type="application/pdf",
            content=PDF,
            uploaded_by=admin.user_id,
        )
        proof = TransferRequest(
            student_id=student,
            amount_cents=100,
            reference="LEGADO-1",
            bank="Banco",
            proof=b"\x89PNG\r\n\x1a\nimagen",
            proof_type="image/png",
            submitted_by=admin.user_id,
        )
        db.add_all([legacy, proof])
        db.commit()
        document_id = legacy.student_document_id
    url = f"/operations/documents/{document_id}/download"
    assert client.get(url, headers=tokens["admin"]).content == PDF  # read from the old column
    assert verify(sessions).pending["student_documents"] == 1

    report = move(sessions, clear=True)
    assert report.moved["student_documents"] == 1 and report.moved["transfer_requests"] == 1
    assert report.cleared["student_documents"] == 1
    with sessions() as db:
        row = db.get(StudentDocument, document_id)
        assert row.content is None and row.storage_key.startswith("inst/1/documents/")
        transfer = db.query(TransferRequest).filter_by(reference="LEGADO-1").one()
        assert transfer.proof is None and transfer.proof_size == 14
    assert client.get(url, headers=tokens["admin"]).content == PDF
    again = move(sessions)  # a second run copies nothing
    assert sum(again.moved.values()) == 0
    check = verify(sessions)
    assert sum(check.pending.values()) == 0 and check.broken == []
    (isolated_storage / row.storage_key).write_bytes(b"alterado")
    assert verify(sessions).broken == [f"student_documents: {row.storage_key}"]


def test_local_storage_refuses_keys_outside_its_folder(tmp_path):
    local = storage.LocalStorage(str(tmp_path))
    with pytest.raises(storage.StorageError):
        local.put("../fuera.txt", b"x", "text/plain")


def test_s3_storage_encrypts_and_uses_the_bucket():
    calls = []

    class Body:
        def read(self):
            return b"datos"

    class Client:
        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": Body()}

        def delete_object(self, **kwargs):
            calls.append(("delete", kwargs))

    s3 = storage.S3Storage(Client(), "nexo-archivos")
    s3.put("inst/2/documents/a", b"datos", "application/pdf")
    assert s3.get("inst/2/documents/a") == b"datos"
    s3.delete("inst/2/documents/a")
    put = calls[0][1]
    assert put["Bucket"] == "nexo-archivos" and put["ServerSideEncryption"] == "AES256"
    assert put["ContentType"] == "application/pdf"
    assert [name for name, _ in calls] == ["put", "get", "delete"]


def test_production_s3_requires_a_bucket():
    with pytest.raises(ValueError, match="S3_BUCKET"):
        Settings(
            app_environment="production",
            secret_key="x" * 40,
            cors_origins="https://nexo.do",
            storage_backend="s3",
        )
