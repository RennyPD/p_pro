"""Legal documents of Nexo, versioned in the repository (Fase 5, step G3).

Changing a text means changing its file and its version here: accounts that
must accept it are asked again at their next sign-in.
"""

from dataclasses import dataclass
from pathlib import Path

FOLDER = Path(__file__).parent


@dataclass(frozen=True)
class LegalDocument:
    kind: str
    title: str
    version: str
    filename: str
    slug: str  # public address: /legal/<slug>

    @property
    def text(self) -> str:
        return (FOLDER / self.filename).read_text(encoding="utf-8")


DOCUMENTS = {
    "terms": LegalDocument("terms", "Términos de uso", "2026-11-26", "terminos.md", "terminos"),
    "privacy": LegalDocument(
        "privacy", "Política de privacidad", "2026-11-26", "privacidad.md", "privacidad"
    ),
    "cookies": LegalDocument(
        "cookies", "Política de cookies", "2026-11-26", "cookies.md", "cookies"
    ),
    "dpa": LegalDocument(
        "dpa", "Acuerdo de tratamiento de datos", "2026-11-26", "dpa.md", "tratamiento-de-datos"
    ),
}
BY_SLUG = {document.slug: document for document in DOCUMENTS.values()}
# What an institution's administrator accepts on its behalf.
INSTITUTION_DOCUMENTS = ("terms", "dpa")
SIGNUP_DOCUMENTS = ("terms", "privacy")
