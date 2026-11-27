"""Help center guides, versioned in the repository (Fase 5, step G5).

``audience``: who the guide is for (admin, teacher, student, guardian) or
"all". The help page lists first the guides of the reader's role.
"""

from dataclasses import dataclass
from pathlib import Path

FOLDER = Path(__file__).parent


@dataclass(frozen=True)
class Guide:
    slug: str
    title: str
    summary: str
    audience: tuple[str, ...]

    @property
    def text(self) -> str:
        return (FOLDER / f"{self.slug}.md").read_text(encoding="utf-8")


GUIDES = (
    Guide(
        "primeros-pasos", "Primeros pasos", "Deja tu institución lista para trabajar.", ("admin",)
    ),
    Guide(
        "calificaciones-y-periodos",
        "Calificaciones, períodos y boletines",
        "Escalas, evaluaciones, cierre de períodos y boletines.",
        ("admin",),
    ),
    Guide("finanzas", "Finanzas", "Planes de cobro, caja, transferencias y reportes.", ("admin",)),
    Guide("pagos-en-linea", "Pagos en línea", "Cobra con tarjeta directo a tu cuenta.", ("admin",)),
    Guide(
        "comprobantes-fiscales",
        "Comprobantes fiscales",
        "NCF, e-CF, notas de crédito y reportes 607 y 608.",
        ("admin",),
    ),
    Guide("docentes", "Guía para docentes", "Secciones, asistencia, notas y tareas.", ("teacher",)),
    Guide(
        "estudiantes", "Guía para estudiantes", "Horario, notas, selección y cuenta.", ("student",)
    ),
    Guide("familias", "Guía para familias", "Seguimiento de tus hijos y pagos.", ("guardian",)),
    Guide(
        "seguridad-de-la-cuenta",
        "Seguridad de tu cuenta",
        "Contraseña, segundo factor y sesiones.",
        ("all",),
    ),
    Guide("preguntas-frecuentes", "Preguntas frecuentes", "Respuestas rápidas.", ("all",)),
)
BY_SLUG = {guide.slug: guide for guide in GUIDES}
