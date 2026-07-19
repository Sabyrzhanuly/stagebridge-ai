from datetime import datetime
from pydantic import BaseModel


class AuditLogOut(BaseModel):
  id: int
  user_id: int | None
  username: str
  action: str
  entity_type: str
  entity_id: str | None
  payload: dict | None
  result: str
  ip_address: str | None
  created_at: datetime
  model_config = {"from_attributes": True}
