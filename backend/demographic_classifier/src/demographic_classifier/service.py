from .models import ClassifyRequest, TagList

KEYWORDS = {
    "gen z": ["tiktok", "snapchat"],
    "frontend dev": ["javascript", "react"],
    "designer": ["figma", "adobe"],
}


def classify(text: str) -> list[str]:
    text_lower = text.lower()
    tags = []
    for tag, words in KEYWORDS.items():
        if any(w in text_lower for w in words):
            tags.append(tag.title())
    if not tags:
        tags.append("General")
    return tags


def classify_request(req: ClassifyRequest) -> TagList:
    return TagList(tags=classify(req.text))
