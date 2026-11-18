"""Audit M6: no English message may reach the interface."""

import ast
import pathlib
import re

from fastapi.testclient import TestClient

from app.services.validation_messages import spanish_message
from main import app

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGLISH = re.compile(
    r"\b(the|not|found|only|must|cannot|already|exists?|invalid|required|missing|"
    r"denied|allowed|outside|should|too many|successfully|succesfully|deleted|"
    r"your|you|is|are|be|has|have|with|for|of|and)\b",
    re.IGNORECASE,
)
SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(el|la|los|las|de|del|un|una|para|que|no|se)\b", re.I)


def literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return " ".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return None


def call_name(node: ast.Call) -> str:
    return getattr(node.func, "id", getattr(node.func, "attr", ""))


def user_facing_messages():
    files = [*sorted((ROOT / "app").rglob("*.py")), ROOT / "main.py"]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            candidates = []
            if isinstance(node, ast.Call) and call_name(node) == "HTTPException":
                candidates += [k.value for k in node.keywords if k.arg == "detail"]
                candidates += node.args[1:2]
            elif isinstance(node, ast.Call) and call_name(node) == "ValueError":
                if "schemas" in path.parts:
                    candidates += node.args[:1]
            elif isinstance(node, ast.Dict):
                candidates += [
                    value
                    for key, value in zip(node.keys, node.values, strict=True)
                    if isinstance(key, ast.Constant) and key.value in {"detail", "message"}
                ]
            for candidate in candidates:
                text = literal_text(candidate)
                if text:
                    yield f"{path.relative_to(ROOT)}:{candidate.lineno}", text


def test_api_messages_are_in_spanish():
    english = [
        f"{where}: {text}"
        for where, text in user_facing_messages()
        if ENGLISH.search(text) and not SPANISH.search(text)
    ]
    assert not english, "Mensajes en inglés:\n" + "\n".join(english)


def test_validation_errors_are_translated():
    with TestClient(app) as client:
        response = client.post("/auth/login", json={})
    assert response.status_code == 422
    messages = {item["msg"] for item in response.json()["detail"]}
    assert messages == {"Este campo es obligatorio"}
    assert all(item["type"] == "missing" for item in response.json()["detail"])


def test_validation_message_mapping():
    assert spanish_message({"type": "string_too_short", "ctx": {"min_length": 8}}) == (
        "Debe tener al menos 8 caracteres"
    )
    assert (
        spanish_message(
            {"type": "value_error", "msg": "Value error, Una cuenta solo puede vincularse"}
        )
        == "Una cuenta solo puede vincularse"
    )
    assert (
        spanish_message({"type": "value_error", "msg": "value is not a valid email address: x"})
        == "El correo electrónico no es válido"
    )
    assert spanish_message({"type": "something_new"}) == "El valor no es válido"
