from typing import Literal, Union

from pydantic import BaseModel, Field, RootModel


class DurationSource(BaseModel):
    kind: Literal["duration"]
    text: str


class ReferenceSource(BaseModel):
    kind: Literal["reference"]
    wrong: str
    correct: str


OffsetSource = Union[DurationSource, ReferenceSource]


class OffsetEntry(BaseModel):
    id: str
    delta_seconds: float
    source: OffsetSource = Field(discriminator="kind")
    target_paths: list[str]


class ParseRequest(RootModel[OffsetSource]):
    pass


class PreviewRequest(BaseModel):
    offsets: list[OffsetEntry]
    image_duration: float | None = None


class ApplyRequest(BaseModel):
    offsets: list[OffsetEntry]
