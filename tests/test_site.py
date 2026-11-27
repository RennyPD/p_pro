"""Public site (Fase 5 G1): static, self-contained and compatible with its CSP."""

import re
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.inline, self.ids, self.app_links = [], [], set(), []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if any(name.startswith("on") or name == "style" for name, _ in attrs):
            self.inline.append(tag)
        if tag == "script" and "src" not in values:
            self.inline.append("script")
        for name in ("href", "src"):
            if values.get(name):
                self.refs.append(values[name])
        if "data-app" in values:
            self.app_links.append(values["data-app"])


def page():
    collector = Collector()
    collector.feed((SITE / "index.html").read_text(encoding="utf-8"))
    return collector


def test_every_local_link_and_anchor_exists():
    collected = page()
    for ref in collected.refs:
        if ref.startswith("#"):
            assert ref[1:] in collected.ids, f"Ancla sin destino: {ref}"
        elif not re.match(r"^(https?:|mailto:|/)", ref):
            assert (SITE / ref).exists(), f"Archivo inexistente: {ref}"


def test_no_inline_code_or_third_party_scripts():
    collected = page()
    assert collected.inline == [], "La CSP del sitio bloquea código y estilos en línea"
    scripts = [ref for ref in collected.refs if ref.endswith(".js")]
    assert scripts == ["config.js", "site.js"]
    assert "innerHTML" not in (SITE / "site.js").read_text(encoding="utf-8")


def test_links_to_the_application_and_placeholders_for_the_build():
    collected = page()
    assert {"/registro", "/login", "/demo", "/legal/privacidad", "/legal/terminos"} <= set(
        collected.app_links
    )
    config = (SITE / "config.js").read_text(encoding="utf-8")
    dockerfile = (SITE / "Dockerfile").read_text(encoding="utf-8")
    for placeholder in ("__APP_URL__", "__API_URL__", "__CONTACT_EMAIL__"):
        assert placeholder in config and placeholder in dockerfile
    assert "__SITE_URL__" in (SITE / "sitemap.xml").read_text(encoding="utf-8")
