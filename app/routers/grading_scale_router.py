"""Grading scales (Fase 3, block D): presets, create, edit, default and delete."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.career_model import Career
from app.models.grading_scale_model import GradingScale
from app.schemas.grading_scale_schema import (
    GradingScaleIn,
    GradingScaleOut,
    GradingScalePreset,
)
from app.services import grading_scales as service
from app.services.governance_workflow import history, lock_governance, record

router = APIRouter(tags=["grading scales"])
scale_manager = require_permissions("settings.manage")


def scale_out(db: Session, scale: GradingScale) -> GradingScaleOut:
    count = (
        db.query(func.count(Career.career_id))
        .filter(Career.grading_scale_id == scale.grading_scale_id)
        .scalar()
    )
    return GradingScaleOut.model_validate(scale).model_copy(update={"program_count": count})


def scale_or_404(db: Session, scale_id: int) -> GradingScale:
    scale = db.get(GradingScale, scale_id)
    if scale is None:
        raise HTTPException(404, "Escala no encontrada")
    return scale


def ensure_unique_name(db: Session, name: str, current: GradingScale | None = None) -> None:
    other = db.query(GradingScale).filter(func.lower(GradingScale.name) == name.lower()).first()
    if other is not None and other is not current:
        raise HTTPException(409, f"Ya existe la escala {name}")


def summary(scale: GradingScale) -> str:
    bands = ", ".join(f"{b.label} {b.min_value}–{b.max_value}" for b in scale.bands)
    return (
        f"{scale.name}; {scale.kind}; mínima {scale.passing_value}; "
        f"completivo {scale.completivo_average_weight} %; "
        f"extraordinario {scale.extraordinario_average_weight} %"
        + (f"; rangos: {bands}" if bands else "")
    )


@router.get("/grading-scales/", response_model=list[GradingScaleOut])
def list_scales(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    scales = db.query(GradingScale).order_by(GradingScale.is_default.desc(), GradingScale.name)
    return [scale_out(db, scale) for scale in scales]


@router.get(
    "/grading-scales/presets",
    response_model=list[GradingScalePreset],
    dependencies=[Depends(scale_manager)],
)
def scale_presets():
    return [{"key": key, "scale": preset} for key, preset in service.PRESETS.items()]


@router.post("/grading-scales/", response_model=GradingScaleOut)
def create_scale(data: GradingScaleIn, db: Session = Depends(get_db), user=Depends(scale_manager)):
    lock_governance(db)
    name = data.name.strip()
    ensure_unique_name(db, name)
    service.validate_bands(data.kind, data.passing_value, data.bands)
    scale = GradingScale(
        **data.model_dump(exclude={"bands", "name"}),
        name=name,
        is_default=db.query(GradingScale.grading_scale_id).first() is None,
    )
    service.apply_bands(scale, data.bands)
    db.add(scale)
    db.flush()
    record(
        db,
        user,
        "grading_scale.created",
        f"grading-scale:{scale.grading_scale_id}",
        summary(scale),
    )
    service.sync_default_passing(db, scale)
    db.commit()
    return scale_out(db, scale)


@router.put("/grading-scales/{scale_id}", response_model=GradingScaleOut)
def update_scale(
    scale_id: int,
    data: GradingScaleIn,
    db: Session = Depends(get_db),
    user=Depends(scale_manager),
):
    """Existing selections keep the passing grade they were created with."""
    lock_governance(db)
    scale = scale_or_404(db, scale_id)
    name = data.name.strip()
    ensure_unique_name(db, name, scale)
    service.validate_bands(data.kind, data.passing_value, data.bands)
    before = summary(scale)
    for key, value in data.model_dump(exclude={"bands", "name"}).items():
        setattr(scale, key, value)
    scale.name = name
    service.apply_bands(scale, data.bands)
    db.flush()
    db.refresh(scale)
    record(
        db,
        user,
        "grading_scale.updated",
        f"grading-scale:{scale_id}",
        f"{before} → {summary(scale)}",
    )
    service.sync_default_passing(db, scale)
    db.commit()
    return scale_out(db, scale)


@router.post("/grading-scales/{scale_id}/default", response_model=GradingScaleOut)
def make_default(scale_id: int, db: Session = Depends(get_db), user=Depends(scale_manager)):
    lock_governance(db)
    scale = scale_or_404(db, scale_id)
    db.query(GradingScale).filter(GradingScale.grading_scale_id != scale_id).update(
        {GradingScale.is_default: False}, synchronize_session=False
    )
    scale.is_default = True
    record(
        db,
        user,
        "grading_scale.default",
        f"grading-scale:{scale_id}",
        f"Predeterminada: {scale.name}",
    )
    service.sync_default_passing(db, scale)
    db.commit()
    return scale_out(db, scale)


@router.delete("/grading-scales/{scale_id}")
def delete_scale(scale_id: int, db: Session = Depends(get_db), user=Depends(scale_manager)):
    lock_governance(db)
    scale = scale_or_404(db, scale_id)
    if service.scale_in_use(db, scale):
        raise HTTPException(409, "La escala es la predeterminada o la usa algún programa")
    record(db, user, "grading_scale.deleted", f"grading-scale:{scale_id}", scale.name)
    db.delete(scale)
    db.commit()
    return {"message": "Escala eliminada"}


@router.get("/grading-scales/{scale_id}/history", dependencies=[Depends(scale_manager)])
def scale_history(scale_id: int, db: Session = Depends(get_db)):
    return history(db, f"grading-scale:{scale_id}")
