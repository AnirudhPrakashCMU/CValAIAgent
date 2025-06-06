from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class IntentMsg(BaseModel):
    schema_version: str = Field(default="1.0")
    utterance_id: UUID
    component: str
    styles: list[str] = Field(default_factory=list)
    brand_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0)
    speaker: str | None = None
