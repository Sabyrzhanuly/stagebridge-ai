from pydantic import BaseModel


class DiagnosticCheck(BaseModel):
    name: str
    status: str
    details: str | None = None


class DiagnosticReport(BaseModel):
    server_name: str
    checks: list[DiagnosticCheck]
    warnings: int
    ok: int
