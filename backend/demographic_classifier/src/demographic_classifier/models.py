from pydantic import BaseModel
from typing import List


class ClassifyRequest(BaseModel):
    text: str


class TagList(BaseModel):
    tags: List[str]
