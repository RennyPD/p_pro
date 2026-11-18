"""Write the API's OpenAPI schema to frontend/openapi.json.

The frontend generates its API types from this file (npm run api:types), and
tests/test_openapi_snapshot.py fails when it falls behind the backend.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "openapi.json"


def schema_text() -> str:
    from main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    TARGET.write_text(schema_text(), encoding="utf-8")
    print(f"OpenAPI escrito en {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
