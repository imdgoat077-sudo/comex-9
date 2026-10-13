import pytest
from graph.entity_resolution import canonical_key, normalize_name, extract_domain


def test_extract_domain():
    assert extract_domain("https://amazon.in/dp/B0CDR6LHKZ") == "amazon.in"
    assert extract_domain("http://www.google.com/search?q=test") == "www.google.com"
    assert extract_domain("") == "unknown"
    assert extract_domain(None) == "unknown"


def test_normalize_name():
    assert normalize_name(" LG 27MR400 Monitor ") == "lg 27mr400 monitor"
    assert normalize_name("LG  27MR400!!!") == "lg 27mr400"
    assert normalize_name("") == ""
    assert normalize_name(None) == ""


def test_canonical_key_same_name_same_domain():
    k1 = canonical_key("amazon.in", name="LG 27MR400")
    k2 = canonical_key("amazon.in", name="lg 27mr400")
    assert k1 == k2


def test_canonical_key_extra_whitespace():
    k1 = canonical_key("amazon.in", name="LG 27MR400")
    k2 = canonical_key("amazon.in", name="  LG   27MR400 ")
    assert k1 == k2


def test_canonical_key_product_id_priority():
    k1 = canonical_key("amazon.in", product_id="B0CDR6LHKZ", name="LG 27MR400 Monitor")
    k2 = canonical_key("amazon.in", product_id="B0CDR6LHKZ", name="LG Monitor 27-inch IPS")
    assert k1 == k2


def test_canonical_key_different_domains():
    k1 = canonical_key("amazon.in", name="LG 27MR400")
    k2 = canonical_key("flipkart.com", name="LG 27MR400")
    assert k1 != k2


def test_canonical_key_different_names_no_id():
    k1 = canonical_key("amazon.in", name="LG 27MR400")
    k2 = canonical_key("amazon.in", name="Samsung Odyssey G5")
    assert k1 != k2
