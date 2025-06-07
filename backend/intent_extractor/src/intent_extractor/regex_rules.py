import regex as re

COMPONENT_PATTERN = re.compile(r"\b(button|dropdown|modal|tab|form)\b", re.IGNORECASE)
STYLE_PATTERN = re.compile(r"\b(hover|pill|rounded|outline)\b", re.IGNORECASE)
BRAND_PATTERN = re.compile(r"\b(stripe|github|google)\b", re.IGNORECASE)

def detect(text: str):
    component_match = COMPONENT_PATTERN.search(text)
    if not component_match:
        return None
    component = component_match.group(1).lower()
    styles = [m.group(1).lower() for m in STYLE_PATTERN.finditer(text)]
    brand_refs = [m.group(1).title() for m in BRAND_PATTERN.finditer(text)]
    return {
        "component": component,
        "styles": styles,
        "brand_refs": brand_refs,
    }
