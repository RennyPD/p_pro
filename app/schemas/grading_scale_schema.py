from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

Grade = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class BandIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=120)
    min_value: Decimal = Grade
    max_value: Decimal = Grade
    stored_value: Decimal = Grade
    points: Decimal | None = Field(default=None, ge=0, le=10, max_digits=4, decimal_places=2)


class BandOut(BandIn):
    model_config = ConfigDict(from_attributes=True)

    min_value: float
    max_value: float
    stored_value: float
    points: float | None = None


class GradingScaleIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    kind: str = Field(pattern=r"^(numeric|letter|conceptual)$")
    passing_value: Decimal = Grade
    decimals: int = Field(default=0, ge=0, le=2)
    completivo_average_weight: Decimal = Field(
        default=Decimal("50"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    extraordinario_average_weight: Decimal = Field(
        default=Decimal("30"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    bands: list[BandIn] = Field(default_factory=list, max_length=20)


class GradingScaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grading_scale_id: int
    name: str
    kind: str
    passing_value: float
    decimals: int
    is_default: bool
    completivo_average_weight: float
    extraordinario_average_weight: float
    bands: list[BandOut]
    program_count: int = 0


class GradingScalePreset(BaseModel):
    key: str
    scale: GradingScaleIn


class ScaleAssignment(BaseModel):
    grading_scale_id: int | None = None


class BandBrief(BaseModel):
    label: str
    min_value: float
    stored_value: float
    points: float | None = None


class ScaleBrief(BaseModel):
    """What a screen needs to show and capture grades on a scale."""

    grading_scale_id: int | None
    name: str
    kind: str
    passing_value: float
    decimals: int = 0
    bands: list[BandBrief] = []
