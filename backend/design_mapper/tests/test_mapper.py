import os
from pathlib import Path

os.environ.setdefault(
    "MAPPINGS_FILE_PATH",
    str(Path(__file__).resolve().parents[3] / "data/mappings/mappings.json"),
)
os.environ.setdefault("ENABLE_HOT_RELOAD", "False")
os.environ.setdefault("ENABLE_LRU_CACHE", "False")

from design_mapper.models.schemas import MappingRequest
from design_mapper.service.mapper import map_request


def test_map_request_basic():
    request = MappingRequest(
        styles=["pill_button"],
        brand_refs=["stripe"],
        component="button",
    )
    response = map_request(request)
    tokens = response.theme_tokens
    assert tokens.border_radius == "full"
    assert tokens.primary_color_scheme == "blue-purple-gradient"
    assert "rounded-full" in response.tailwind_classes


def test_map_request_hover():
    request = MappingRequest(
        styles=["hover_lift"],
        brand_refs=["apple"],
        component="card",
    )
    response = map_request(request)
    tokens = response.theme_tokens
    assert tokens.animation_ease == "ease-in-out-quart"
    assert any("hover:scale-105" in cls for cls in response.tailwind_classes)
