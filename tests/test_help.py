"""Help center (Fase 5, step G5)."""

from test_write_audit import demo  # noqa: F401  (shared fixture)

from app.help import GUIDES


def test_every_guide_exists_and_every_role_has_one():
    roles = set()
    for guide in GUIDES:
        assert guide.text.startswith("# "), guide.slug
        roles |= set(guide.audience)
    assert {"admin", "teacher", "student", "guardian", "all"} <= roles


def test_guides_are_public(demo):  # noqa: F811
    client, _sessions, _tokens = demo
    listed = client.get("/public/help").json()
    assert len(listed) == len(GUIDES) and listed[0]["slug"] == "primeros-pasos"
    guide = client.get("/public/help/familias").json()
    assert guide["audience"] == ["guardian"] and "Pagar con tarjeta" in guide["text"]
    assert client.get("/public/help/no-existe").status_code == 404
