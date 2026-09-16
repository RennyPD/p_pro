"""Create a placeholder career for historical unassigned students."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260916_0003"
down_revision: Union[str, None] = "20260915_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    careers = sa.table(
        "careers",
        sa.column("career_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(careers, [{
        "career_id": 0,
        "name": "Sin asignar",
        "description": "Carrera temporal para registros históricos pendientes de clasificación",
    }])


def downgrade() -> None:
    op.execute("DELETE FROM careers WHERE career_id = 0 AND name = 'Sin asignar'")
