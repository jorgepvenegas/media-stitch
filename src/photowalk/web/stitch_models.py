from typing import Literal

from pydantic import BaseModel, field_validator


class StitchRequest(BaseModel):
    output: str
    format: str | None = None
    draft: bool = False
    image_duration: float = 3.5
    margin: float = 15.0
    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = v.split("x")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError('Format must be "WIDTHxHEIGHT" (e.g. "1920x1080")')
        return v


class StitchStatus(BaseModel):
    state: Literal["idle", "running", "done", "cancelled", "error"]
    message: str
    output_path: str | None = None
