"""MINERD competency groups (Fase 3 F2).

Programs with ``report_card_format = "minerd_secondary"`` grade each subject
and period on the four groups of fundamental competencies of the official
secondary report card. Each group is one assessment of the period's section
(25 % each), so the period result (PC) is their average and every existing
workflow (drafts, publishing, closing, recovery) applies unchanged.
"""

from sqlalchemy.orm import Session

from app.models.assessment_model import Assessment, CompetencyGroup

MINERD_FORMAT = "minerd_secondary"
DEFAULT_GROUPS = (
    (1, "Comunicativa", "Comunicativa"),
    (
        2,
        "Pensamiento Lógico, Creativo y Crítico · Resolución de Problemas",
        "Pensamiento y resolución",
    ),
    (3, "Científica y Tecnológica · Ambiental y de la Salud", "Científica y ambiental"),
    (4, "Ética y Ciudadana · Desarrollo Personal y Espiritual", "Ética y desarrollo personal"),
)


def competency_groups(db: Session, create: bool = False) -> list[CompetencyGroup]:
    rows = db.query(CompetencyGroup).order_by(CompetencyGroup.position).all()
    if not rows and create:
        rows = [
            CompetencyGroup(position=position, name=name, short_name=short)
            for position, name, short in DEFAULT_GROUPS
        ]
        db.add_all(rows)
        db.flush()
    return rows


def uses_competencies(career) -> bool:
    return getattr(career, "report_card_format", "general") == MINERD_FORMAT


def ensure_competency_assessments(db: Session, sections) -> int:
    """One 25 % assessment per competency group in each section without assessments."""
    groups = competency_groups(db, create=True)
    weight = round(100 / len(groups), 2)
    created = 0
    for section in sections:
        if db.query(Assessment.assessment_id).filter_by(section_id=section.section_id).first():
            continue
        for group in groups:
            db.add(
                Assessment(
                    section_id=section.section_id,
                    name=group.short_name,
                    weight=weight,
                    closed=False,
                    competency_group_id=group.competency_group_id,
                )
            )
            created += 1
    db.flush()
    return created
