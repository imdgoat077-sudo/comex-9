import os
import shutil
import tempfile
import pytest
from datetime import datetime, timedelta, timezone

from graph.store import AgentGraphStore
from graph.entity_resolution import canonical_key, normalize_name, extract_domain


@pytest.fixture
def temp_graph_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_p4.db")
    store = AgentGraphStore(db_path)
    yield store, db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# GM-021: Entity Resolution Edge Cases
# =====================================================================

def test_identical_product_single_entity(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_1"
    store.create_agent(agent_id, "Dedup identical", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {})
    e2 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {})

    assert e1 == e2
    stats = store.get_stats()
    assert stats["entity_count"] == 1


def test_casing_variation_single_entity(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_2"
    store.create_agent(agent_id, "Dedup casing", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {})
    e2 = store.upsert_entity(tc_id, page_id, "product", "lg 27mr400", 14999.0, "INR", {})

    assert e1 == e2
    stats = store.get_stats()
    assert stats["entity_count"] == 1


def test_whitespace_variation_single_entity(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_3"
    store.create_agent(agent_id, "Dedup whitespace", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {})
    e2 = store.upsert_entity(tc_id, page_id, "product", "  LG   27MR400  ", 14999.0, "INR", {})

    assert e1 == e2
    stats = store.get_stats()
    assert stats["entity_count"] == 1


def test_product_id_precedence(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_4"
    store.create_agent(agent_id, "Dedup ASIN precedence", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B0CDR6LHKZ", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {"product_id": "B0CDR6LHKZ"})
    e2 = store.upsert_entity(tc_id, page_id, "product", "LG Borderless 27-inch Monitor", 14999.0, "INR", {"product_id": "B0CDR6LHKZ"})

    assert e1 == e2
    stats = store.get_stats()
    assert stats["entity_count"] == 1


def test_distinct_products_no_id_two_entities(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_5"
    store.create_agent(agent_id, "Dedup distinct products", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "LG 27MR400", 14999.0, "INR", {})
    e2 = store.upsert_entity(tc_id, page_id, "product", "Samsung Odyssey G5", 19999.0, "INR", {})

    assert e1 != e2
    stats = store.get_stats()
    assert stats["entity_count"] == 2


def test_different_domains_distinct_entities(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_dedup_6"
    store.create_agent(agent_id, "Dedup cross domain", "RESEARCH")

    tc1 = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_amazon = store.record_navigation(tc1, "https://amazon.in/dp/B01", "Amazon")
    e1 = store.upsert_entity(tc1, page_amazon, "product", "LG 27MR400", 14999.0, "INR", {})

    tc2 = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 1, True)
    page_flipkart = store.record_navigation(tc2, "https://flipkart.com/p/1", "Flipkart")
    e2 = store.upsert_entity(tc2, page_flipkart, "product", "LG 27MR400", 14500.0, "INR", {})

    assert e1 != e2
    stats = store.get_stats()
    assert stats["entity_count"] == 2


# =====================================================================
# GM-022 - GM-024: Staleness Verification
# =====================================================================

def test_fresh_entity_returned_by_default(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_1"
    store.create_agent(agent_id, "Fresh test", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    store.upsert_entity(tc_id, page_id, "product", "Fresh Monitor", 10000.0, "INR", {})

    recent = store.find_recent_entities("product", since_minutes=30)
    assert len(recent) == 1
    assert recent[0]["name"] == "Fresh Monitor"


def test_31_min_stale_entity_excluded_by_default(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_2"
    store.create_agent(agent_id, "Stale 31min test", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    ent_id = store.upsert_entity(tc_id, page_id, "product", "Stale Monitor", 10000.0, "INR", {})

    # Set last_seen_at to 31 minutes ago
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=31)
    with store._lock:
        store.conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.last_seen_at = $stale_time",
            {"id": ent_id, "stale_time": stale_time}
        )

    recent = store.find_recent_entities("product", since_minutes=30)
    assert len(recent) == 0


def test_stale_entity_included_when_include_stale_true(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_3"
    store.create_agent(agent_id, "Include stale test", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    ent_id = store.upsert_entity(tc_id, page_id, "product", "Stale Monitor", 10000.0, "INR", {})

    # Set last_seen_at to 31 minutes ago
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=31)
    with store._lock:
        store.conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.last_seen_at = $stale_time",
            {"id": ent_id, "stale_time": stale_time}
        )

    stale_included = store.find_recent_entities("product", since_minutes=30, include_stale=True)
    assert len(stale_included) == 1
    assert stale_included[0]["name"] == "Stale Monitor"


def test_stale_data_retained_no_deletion(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_4"
    store.create_agent(agent_id, "No deletion check", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")
    ent_id = store.upsert_entity(tc_id, page_id, "product", "Retained Stale Monitor", 10000.0, "INR", {})

    # Set last_seen_at to 60 minutes ago
    old_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    with store._lock:
        store.conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.last_seen_at = $old_time",
            {"id": ent_id, "old_time": old_time}
        )

    # Default query excludes it
    assert len(store.find_recent_entities("product", since_minutes=30)) == 0

    # Physical DB node count remains 1
    stats = store.get_stats()
    assert stats["entity_count"] == 1

    # `include_stale=True` retrieves it
    assert len(store.find_recent_entities("product", since_minutes=30, include_stale=True)) == 1


def test_mixed_fresh_and_stale_entities(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_5"
    store.create_agent(agent_id, "Mixed fresh stale", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    ent_fresh = store.upsert_entity(tc_id, page_id, "product", "Fresh Item", 5000.0, "INR", {})
    ent_stale = store.upsert_entity(tc_id, page_id, "product", "Stale Item", 6000.0, "INR", {})

    # Make ent_stale 35 minutes old
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=35)
    with store._lock:
        store.conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.last_seen_at = $stale_time",
            {"id": ent_stale, "stale_time": stale_time}
        )

    default_res = store.find_recent_entities("product", since_minutes=30)
    assert len(default_res) == 1
    assert default_res[0]["name"] == "Fresh Item"

    all_res = store.find_recent_entities("product", since_minutes=30, include_stale=True)
    assert len(all_res) == 2
    names = [r["name"] for r in all_res]
    assert "Fresh Item" in names
    assert "Stale Item" in names


def test_staleness_composes_with_max_price_and_type(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "agent_stale_6"
    store.create_agent(agent_id, "Staleness composition", "RESEARCH")

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "ok", 0, True)
    page_id = store.record_navigation(tc_id, "https://amazon.in/dp/B01", "Amazon")

    e1 = store.upsert_entity(tc_id, page_id, "product", "Fresh Cheap", 9000.0, "INR", {})
    e2 = store.upsert_entity(tc_id, page_id, "product", "Fresh Expensive", 25000.0, "INR", {})
    e3 = store.upsert_entity(tc_id, page_id, "product", "Stale Cheap", 8000.0, "INR", {})

    # Set e3 to 40 mins ago
    old_time = datetime.now(timezone.utc) - timedelta(minutes=40)
    with store._lock:
        store.conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.last_seen_at = $old_time",
            {"id": e3, "old_time": old_time}
        )

    # Under 15000 + fresh only -> should only return e1 ("Fresh Cheap")
    res = store.find_recent_entities("product", max_price=15000.0, since_minutes=30)
    assert len(res) == 1
    assert res[0]["name"] == "Fresh Cheap"

    # Under 15000 + include_stale=True -> returns e1 ("Fresh Cheap") and e3 ("Stale Cheap")
    res_stale = store.find_recent_entities("product", max_price=15000.0, since_minutes=30, include_stale=True)
    assert len(res_stale) == 2
    names = [r["name"] for r in res_stale]
    assert "Fresh Cheap" in names
    assert "Stale Cheap" in names
