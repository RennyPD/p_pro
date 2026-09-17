"""Add internal student finance ledger."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str="20260917_0007"
down_revision: Union[str,None]="20260917_0006"
branch_labels: Union[str,Sequence[str],None]=None
depends_on: Union[str,Sequence[str],None]=None
def upgrade()->None:
    op.create_table("student_accounts",sa.Column("student_account_id",sa.Integer(),primary_key=True),sa.Column("student_id",sa.Integer(),sa.ForeignKey("students.student_id"),nullable=False,unique=True),sa.Column("cutoff_day",sa.Integer(),nullable=False),sa.Column("due_day",sa.Integer(),nullable=False))
    op.create_table("charges",sa.Column("charge_id",sa.Integer(),primary_key=True),sa.Column("student_account_id",sa.Integer(),sa.ForeignKey("student_accounts.student_account_id"),nullable=False),sa.Column("description",sa.String(200),nullable=False),sa.Column("amount",sa.Float(),nullable=False),sa.Column("due_date",sa.Date(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_table("payments",sa.Column("payment_id",sa.Integer(),primary_key=True),sa.Column("student_account_id",sa.Integer(),sa.ForeignKey("student_accounts.student_account_id"),nullable=False),sa.Column("amount",sa.Float(),nullable=False),sa.Column("reference",sa.String(100),nullable=False),sa.Column("note",sa.String(250),nullable=False),sa.Column("paid_at",sa.DateTime(),nullable=False))
    op.create_index("idx_charges_account_due","charges",["student_account_id","due_date"])
    op.create_index("idx_payments_account_date","payments",["student_account_id","paid_at"])
def downgrade()->None:
    op.drop_index("idx_payments_account_date",table_name="payments");op.drop_index("idx_charges_account_due",table_name="charges");op.drop_table("payments");op.drop_table("charges");op.drop_table("student_accounts")
