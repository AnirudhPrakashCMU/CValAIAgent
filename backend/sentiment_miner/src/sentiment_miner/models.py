from pydantic import BaseModel, Field
from uuid import UUID
from typing import List


class InsightPost(BaseModel):
    text: str
    sentiment: float
    tags: List[str] = Field(default_factory=list)


class InsightMsg(BaseModel):
    spec_id: UUID
    query: str
    posts: List[InsightPost]
