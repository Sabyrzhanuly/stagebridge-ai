from pydantic import BaseModel


class CronScheduleCreate(BaseModel):
    name: str
    cron_expression: str
    description: str = ""


class CronScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    description: str | None = None


class CronScheduleOut(BaseModel):
    id: int
    name: str
    cron_expression: str
    description: str
    is_builtin: bool

    model_config = {"from_attributes": True}
