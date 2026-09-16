from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    audit_log_id: int
    user_id: int | None
    action: str
    resource: str
    detail: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
