from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class DesignSpec(BaseModel):
    schema_version: str = Field(default="1.0")
    spec_id: UUID = Field(default_factory=uuid4)
    component: str
    theme_tokens: dict[str, str] = Field(default_factory=dict)
    interaction: str | None = None
    source_utts: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
