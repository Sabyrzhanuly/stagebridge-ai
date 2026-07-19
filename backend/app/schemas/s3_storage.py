from datetime import datetime
from pydantic import BaseModel, field_validator


def _clean_region(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_sign_version(value: str | None) -> str:
    if value and str(value).strip().lower() in ("v2", "2"):
        return "v2"
    return "v4"


def _clean_api_type(value: str | None) -> str:
    if value and str(value).strip().lower() == "swift":
        return "swift"
    return "s3"


def _clean_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class S3StorageCreate(BaseModel):
    name: str
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    region: str | None = None
    sign_version: str = "v4"
    api_type: str = "s3"
    swift_project: str | None = None
    swift_domain: str | None = None

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        return _clean_region(value)

    @field_validator("sign_version", mode="before")
    @classmethod
    def normalize_sign_version(cls, value: str | None) -> str:
        return _clean_sign_version(value)

    @field_validator("api_type", mode="before")
    @classmethod
    def normalize_api_type(cls, value: str | None) -> str:
        return _clean_api_type(value)

    @field_validator("swift_project", "swift_domain", mode="before")
    @classmethod
    def normalize_swift_fields(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)


class S3StorageUpdate(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    bucket: str | None = None
    secure: bool | None = None
    region: str | None = None
    sign_version: str | None = None
    api_type: str | None = None
    swift_project: str | None = None
    swift_domain: str | None = None

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        return _clean_region(value)

    @field_validator("sign_version", mode="before")
    @classmethod
    def normalize_sign_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_sign_version(value)

    @field_validator("api_type", mode="before")
    @classmethod
    def normalize_api_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_api_type(value)

    @field_validator("swift_project", "swift_domain", mode="before")
    @classmethod
    def normalize_swift_fields(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)


class S3StorageOut(BaseModel):
    id: int
    name: str
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool
    region: str | None
    sign_version: str
    api_type: str
    swift_project: str | None
    swift_domain: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class S3StorageTestRequest(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    region: str | None = None
    sign_version: str = "v4"
    api_type: str = "s3"
    swift_project: str | None = None
    swift_domain: str | None = None

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        return _clean_region(value)

    @field_validator("sign_version", mode="before")
    @classmethod
    def normalize_sign_version(cls, value: str | None) -> str:
        return _clean_sign_version(value)

    @field_validator("api_type", mode="before")
    @classmethod
    def normalize_api_type(cls, value: str | None) -> str:
        return _clean_api_type(value)

    @field_validator("swift_project", "swift_domain", mode="before")
    @classmethod
    def normalize_swift_fields(cls, value: str | None) -> str | None:
        return _clean_optional_str(value)


class ServerStorageAssign(BaseModel):
    storage_id: int | None = None
