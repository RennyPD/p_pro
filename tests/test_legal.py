"""Legal documents and their acceptance (Fase 5, step G3)."""

from datetime import datetime

from test_signup import BODY
from test_write_audit import demo, entries  # noqa: F401  (shared fixtures)

from app import legal as documents
from app.db.database import settings
from app.models import LegalAcceptance
from app.services import rate_limit


def test_documents_are_public_and_marked_as_drafts(demo):  # noqa: F811
    client, _sessions, _tokens = demo
    listed = client.get("/public/legal").json()
    assert {item["slug"] for item in listed} == {
        "terminos",
        "privacidad",
        "cookies",
        "tratamiento-de-datos",
    }
    privacy = client.get("/public/legal/privacidad").json()
    assert "Ley 172-13" in privacy["text"] and "menores" in privacy["text"]
    assert "BORRADOR PARA REVISIÓN LEGAL" in privacy["text"]
    assert client.get("/public/legal/no-existe").status_code == 404


def test_administrators_accept_the_terms_and_the_dpa_once_per_version(demo, monkeypatch):  # noqa: F811
    client, sessions, tokens = demo
    pending = client.get("/legal/pending", headers=tokens["admin"]).json()["documents"]
    assert [item["kind"] for item in pending] == ["terms", "dpa"]
    # Other accounts are never asked (nor allowed to accept for the institution).
    assert client.get("/legal/pending", headers=tokens["docente"]).json() == {"documents": []}
    assert (
        client.post("/legal/accept", headers=tokens["docente"], json={"kinds": ["dpa"]}).status_code
        == 403
    )
    accepted = client.post(
        "/legal/accept", headers=tokens["admin"], json={"kinds": ["terms", "dpa"]}
    )
    assert accepted.status_code == 200 and accepted.json() == {"documents": []}
    with sessions() as db:
        rows = db.query(LegalAcceptance).filter_by(institution_id=1).all()
        assert {(row.kind, row.version) for row in rows} == {
            ("terms", "2026-11-26"),
            ("dpa", "2026-11-26"),
        }
        assert rows[0].accepted_by
    assert entries(sessions, "legal.accepted")
    # A new version of the terms is asked for again.
    newer = documents.LegalDocument(
        "terms", "Términos de uso", "2027-01-15", "terminos.md", "terminos"
    )
    monkeypatch.setitem(documents.DOCUMENTS, "terms", newer)
    again = client.get("/legal/pending", headers=tokens["admin"]).json()["documents"]
    assert [(item["kind"], item["version"]) for item in again] == [("terms", "2027-01-15")]


def test_sign_up_requires_accepting_terms_and_privacy(demo, monkeypatch):  # noqa: F811
    client, sessions, _tokens = demo
    monkeypatch.setattr(settings, "app_url", "https://nexo.example.edu")
    monkeypatch.setattr(rate_limit, "now", lambda: datetime(2026, 11, 26, 10, 0))
    refused = client.post("/public/signup", json={**BODY, "accept_terms": False})
    assert refused.status_code == 422 and "términos" in refused.json()["detail"]
    created = client.post("/public/signup", json=BODY)
    assert created.status_code == 202, created.text
    with sessions() as db:
        kinds = {
            row.kind
            for row in db.query(LegalAcceptance).filter(LegalAcceptance.institution_id != 1)
        }
    assert kinds == {"terms", "privacy"}  # the DPA is accepted by the administrator inside
