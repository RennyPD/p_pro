"""Grading scales: presets, validation, labels and passing grade per program (Fase 3 D).

Grades stay on 0–100. ``label`` turns a value into what the scale shows
(85 → "85", "B" or "Logrado"), ``points`` gives its index points and
``passing_for`` the passing value of a student's program.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.career_model import Career
from app.models.configuration_model import InstitutionSettings
from app.models.grading_scale_model import GradingScale, GradingScaleBand

DEFAULT_NAME = "Numérica 0–100"
HUNDRED = Decimal("100")


@dataclass
class Band:
    label: str
    min_value: Decimal
    max_value: Decimal
    stored_value: Decimal
    points: Decimal | None = None
    description: str | None = None


@dataclass
class ScaleView:
    """A scale detached from the session (also used when none is configured)."""

    grading_scale_id: int | None
    name: str
    kind: str
    passing_value: Decimal
    decimals: int = 0
    completivo_average_weight: Decimal = Decimal("50")
    extraordinario_average_weight: Decimal = Decimal("30")
    bands: list[Band] = field(default_factory=list)


def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


PRESETS = {
    "numeric": {
        "name": "Numérica 0–100 (MINERD)",
        "kind": "numeric",
        "passing_value": 70,
        "decimals": 0,
        "bands": [],
    },
    "letter": {
        "name": "Letras A–F con índice 4.0",
        "kind": "letter",
        "passing_value": 70,
        "decimals": 0,
        "bands": [
            {"label": "F", "min_value": 0, "max_value": 70, "stored_value": 60, "points": 0},
            {"label": "D", "min_value": 70, "max_value": 75, "stored_value": 72, "points": 1},
            {"label": "C", "min_value": 75, "max_value": 80, "stored_value": 77, "points": 2},
            {"label": "B", "min_value": 80, "max_value": 90, "stored_value": 85, "points": 3},
            {"label": "A", "min_value": 90, "max_value": 100, "stored_value": 95, "points": 4},
        ],
    },
    "conceptual": {
        "name": "Conceptual (inicial y primer ciclo)",
        "kind": "conceptual",
        "passing_value": 65,
        "decimals": 0,
        "bands": [
            {
                "label": "Iniciado",
                "description": "Empieza a lograr la competencia",
                "min_value": 0,
                "max_value": 65,
                "stored_value": 50,
            },
            {
                "label": "En proceso",
                "description": "Avanza hacia la competencia",
                "min_value": 65,
                "max_value": 85,
                "stored_value": 75,
            },
            {
                "label": "Logrado",
                "description": "Demuestra la competencia",
                "min_value": 85,
                "max_value": 100,
                "stored_value": 95,
            },
        ],
    },
}


def view_of(scale: GradingScale) -> ScaleView:
    return ScaleView(
        grading_scale_id=scale.grading_scale_id,
        name=scale.name,
        kind=scale.kind,
        passing_value=D(scale.passing_value),
        decimals=scale.decimals,
        completivo_average_weight=D(scale.completivo_average_weight),
        extraordinario_average_weight=D(scale.extraordinario_average_weight),
        bands=[
            Band(
                b.label,
                D(b.min_value),
                D(b.max_value),
                D(b.stored_value),
                D(b.points) if b.points is not None else None,
                b.description,
            )
            for b in sorted(scale.bands, key=lambda b: b.min_value)
        ],
    )


def default_scale(db: Session) -> ScaleView:
    scale = db.query(GradingScale).filter_by(is_default=True).first()
    if scale is not None:
        return view_of(scale)
    # Databases created without migrations: the institution's passing grade.
    settings = db.get(InstitutionSettings, 1)
    passing = D(settings.passing_grade) if settings else Decimal("70")
    return ScaleView(None, DEFAULT_NAME, "numeric", passing)


def scale_for_career(db: Session, career: Career | None) -> ScaleView:
    if career is not None and career.grading_scale is not None:
        return view_of(career.grading_scale)
    return default_scale(db)


def scale_for_student(db: Session, student) -> ScaleView:
    return scale_for_career(db, student.career if student is not None else None)


def passing_for(db: Session, student) -> float:
    return float(scale_for_student(db, student).passing_value)


def band_for(scale: ScaleView, value) -> Band | None:
    if value is None or not scale.bands:
        return None
    number = D(value)
    chosen = None
    for band in scale.bands:
        if number >= band.min_value:
            chosen = band
    return chosen


def label(scale: ScaleView, value) -> str | None:
    """What the scale shows for a 0–100 value (None stays None)."""
    if value is None:
        return None
    if scale.kind == "numeric" or not scale.bands:
        quantum = Decimal(1).scaleb(-scale.decimals)
        return str(D(value).quantize(quantum, rounding=ROUND_HALF_UP))
    band = band_for(scale, value)
    return band.label if band else None


def points(scale: ScaleView, value) -> Decimal | None:
    band = band_for(scale, value)
    return band.points if band else None


def ensure_capturable(scale: ScaleView, value) -> None:
    """Conceptual scales only accept the value of one of their bands."""
    if scale.kind != "conceptual" or value is None:
        return
    allowed = {band.stored_value for band in scale.bands}
    if D(value).quantize(Decimal("0.01")) not in allowed:
        names = ", ".join(band.label for band in scale.bands)
        raise HTTPException(422, f"En esta escala la nota se elige entre: {names}")


def academic_index(rows: list[tuple[float | None, float | None]], scale: ScaleView):
    """Credit-weighted index from (value, credits) of final results; None without points."""
    if not scale.bands or all(band.points is None for band in scale.bands):
        return None
    total_points = Decimal("0")
    total_credits = Decimal("0")
    for value, credits in rows:
        if value is None or not credits:
            continue
        band_points = points(scale, value)
        if band_points is None:
            continue
        total_points += band_points * D(credits)
        total_credits += D(credits)
    if not total_credits:
        return None
    return float((total_points / total_credits).quantize(Decimal("0.01"), ROUND_HALF_UP))


# --- Validation and writes -------------------------------------------------


def validate_bands(kind: str, passing, bands: list) -> None:
    if kind != "numeric" and not bands:
        raise HTTPException(422, "Las escalas de letras y conceptuales necesitan rangos")
    if not bands:
        return
    ordered = sorted(bands, key=lambda b: D(b.min_value))
    if D(ordered[0].min_value) != 0 or D(ordered[-1].max_value) != HUNDRED:
        raise HTTPException(422, "Los rangos deben cubrir de 0 a 100")
    labels = set()
    for index, band in enumerate(ordered):
        low, high, stored = D(band.min_value), D(band.max_value), D(band.stored_value)
        if low >= high:
            raise HTTPException(422, f"El rango {band.label} debe terminar después de empezar")
        if index and D(ordered[index - 1].max_value) != low:
            raise HTTPException(422, f"Hay un hueco o un solapamiento antes del rango {band.label}")
        top = index == len(ordered) - 1
        if not (low <= stored < high or (top and stored == high)):
            raise HTTPException(422, f"El valor guardado de {band.label} debe estar en su rango")
        if band.label.strip().casefold() in labels:
            raise HTTPException(422, f"La etiqueta {band.label} está repetida")
        labels.add(band.label.strip().casefold())
    if not any(D(b.min_value) == D(passing) for b in ordered) and kind != "numeric":
        raise HTTPException(
            422, "La nota mínima debe coincidir con el inicio de un rango de la escala"
        )


def apply_bands(scale: GradingScale, bands: list) -> None:
    scale.bands.clear()
    for band in sorted(bands, key=lambda b: D(b.min_value)):
        scale.bands.append(
            GradingScaleBand(
                label=band.label.strip(),
                description=(band.description or "").strip() or None,
                min_value=D(band.min_value),
                max_value=D(band.max_value),
                stored_value=D(band.stored_value),
                points=D(band.points) if band.points is not None else None,
            )
        )


def sync_default_passing(db: Session, scale: GradingScale) -> None:
    """The default scale and the institution's passing grade are the same value."""
    if not scale.is_default:
        return
    settings = db.get(InstitutionSettings, 1)
    if settings is not None:
        settings.passing_grade = float(scale.passing_value)


def scale_in_use(db: Session, scale: GradingScale) -> bool:
    return bool(
        scale.is_default
        or db.query(Career.career_id).filter_by(grading_scale_id=scale.grading_scale_id).first()
    )


def brief(scale: ScaleView) -> dict:
    return {
        "grading_scale_id": scale.grading_scale_id,
        "name": scale.name,
        "kind": scale.kind,
        "passing_value": float(scale.passing_value),
        "decimals": scale.decimals,
        "bands": [
            {
                "label": band.label,
                "min_value": float(band.min_value),
                "stored_value": float(band.stored_value),
                "points": float(band.points) if band.points is not None else None,
            }
            for band in scale.bands
        ],
    }


class ScaleCache:
    """One scale lookup per program while building a list."""

    def __init__(self, db: Session):
        self.db = db
        self.by_career: dict[int | None, ScaleView] = {}

    def for_student(self, student) -> ScaleView:
        key = student.career_id if student is not None else None
        if key not in self.by_career:
            self.by_career[key] = scale_for_student(self.db, student)
        return self.by_career[key]

    def distinct(self) -> list[ScaleView]:
        seen, result = set(), []
        for scale in self.by_career.values():
            if scale.grading_scale_id not in seen:
                seen.add(scale.grading_scale_id)
                result.append(scale)
        return result
