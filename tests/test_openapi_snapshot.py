"""The frontend's API types come from frontend/openapi.json; keep it current."""

from scripts.export_openapi import TARGET, schema_text


def test_openapi_snapshot_is_current():
    assert TARGET.read_text(encoding="utf-8") == schema_text(), (
        "El esquema del API cambió. Ejecuta `python -m scripts.export_openapi` y, "
        "en frontend/, `npm run api:types`, y versiona ambos archivos."
    )
