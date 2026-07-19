from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models.user import User
from app.api.deps import get_current_user
from app.services import minio_service

router = APIRouter(prefix="/settings", tags=["settings"])


class MinioTestRequest(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    region: str | None = None
    sign_version: str = "v4"


@router.post("/minio/test")
async def test_minio_connection(data: MinioTestRequest, _: User = Depends(get_current_user)):
    return minio_service.test_connection(
        endpoint=data.endpoint,
        access_key=data.access_key,
        secret_key=data.secret_key,
        bucket=data.bucket,
        secure=data.secure,
        region=data.region,
        sign_version=data.sign_version,
    )
