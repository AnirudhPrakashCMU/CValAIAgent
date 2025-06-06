from intent_extractor.regex_rules import detect


def test_detect_basic():
    res = detect("Add a pill button for Stripe connect")
    assert res
    assert res["component"] == "button"
    assert "pill" in res["styles"]
    assert "Stripe" in res["brand_refs"]
