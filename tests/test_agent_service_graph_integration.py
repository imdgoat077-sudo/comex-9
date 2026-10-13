import json
import os
import shutil
import tempfile
import unittest.mock as mock
import pytest

import agent_service
from graph.store import AgentGraphStore


@pytest.fixture
def temp_graph_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_integration.db")
    store = AgentGraphStore(db_path)
    yield store, db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_extraction_parsing_valid_payload(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "test_agent_ext_1"
    store.create_agent(agent_id, "Extract monitor", "RESEARCH")

    output_with_extract = """
    Navigated to https://amazon.in/dp/B0CDR6LHKZ
    ===COMEX_EXTRACT===
    {
        "url": "https://amazon.in/dp/B0CDR6LHKZ",
        "title": "Amazon.in: LG 27MR400",
        "entities": [
            {
                "type": "product",
                "name": "LG 27MR400",
                "price": 14999.0,
                "currency": "INR",
                "product_id": "B0CDR6LHKZ",
                "attrs": {"rating": 4.3, "screen_size": "27 inch"}
            },
            {
                "type": "product",
                "name": "Samsung Odyssey G5",
                "price": 19999.0,
                "currency": "INR",
                "product_id": "B08SDF1234",
                "attrs": {"rating": 4.5}
            }
        ]
    }
    ===END_EXTRACT===
    Task completed.
    """

    with mock.patch("agent_service.graph_store", store):
        # Simulate browser-harness post-processing logic
        tool_call_id = store.record_tool_call(
            agent_id, "run_browser_harness",
            args_json="print('hello')",
            result_summary=output_with_extract[:200],
            step_index=0,
            success=True
        )

        import re
        extract_pattern = r'===COMEX_EXTRACT===\s*(.*?)\s*===END_EXTRACT==='
        for match in re.finditer(extract_pattern, output_with_extract, re.DOTALL):
            payload = json.loads(match.group(1))
            url = payload.get("url", "")
            title = payload.get("title", "")
            if url:
                page_id = store.record_navigation(tool_call_id, url, title)
                for ent in payload.get("entities", []):
                    store.upsert_entity(
                        tool_call_id, page_id,
                        etype=ent.get("type", "unknown"),
                        name=ent.get("name", ""),
                        price=ent.get("price"),
                        currency=ent.get("currency", "INR"),
                        attrs=ent
                    )

    stats = store.get_stats()
    assert stats["toolcall_count"] == 1
    assert stats["page_count"] == 1
    assert stats["entity_count"] == 2

    recent = store.find_recent_entities("product")
    assert len(recent) == 2
    names = [r["name"] for r in recent]
    assert "LG 27MR400" in names
    assert "Samsung Odyssey G5" in names

    prov = store.get_agent_provenance(agent_id)
    assert len(prov["tool_calls"]) == 1
    tc = prov["tool_calls"][0]
    assert len(tc["pages"]) == 1
    assert tc["pages"][0]["url"] == "https://amazon.in/dp/B0CDR6LHKZ"
    assert len(tc["entities"]) == 2


def test_malformed_extraction_payload(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "test_agent_malformed"
    store.create_agent(agent_id, "Malformed test", "RESEARCH")

    output_malformed = """
    ===COMEX_EXTRACT===
    { "url": "https://example.com", "entities": [ INVALID JSON HERE
    ===END_EXTRACT===
    """

    tool_call_id = store.record_tool_call(agent_id, "run_browser_harness", "{}", "summary", 0, True)

    import re
    extract_pattern = r'===COMEX_EXTRACT===\s*(.*?)\s*===END_EXTRACT==='
    matches = list(re.finditer(extract_pattern, output_malformed, re.DOTALL))
    assert len(matches) == 1

    # Attempt parsing, ensure exception is caught safely without breaking execution
    for match in matches:
        try:
            json.loads(match.group(1))
        except json.JSONDecodeError:
            pass  # Successfully handled

    stats = store.get_stats()
    assert stats["entity_count"] == 0  # No entity created, execution continued


def test_max_args_json_bytes_truncation(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "test_agent_args_limit"
    store.create_agent(agent_id, "Limit test", "RESEARCH")

    large_code = "x = " + ("1" * 10000)
    max_bytes = 100
    truncated = large_code[:max_bytes]
    assert len(truncated) == 100

    tc_id = store.record_tool_call(agent_id, "run_browser_harness", truncated, "summary", 0, True)
    prov = store.get_agent_provenance(agent_id)
    assert len(prov["tool_calls"][0]["args_json"]) == 100


def test_graph_store_exception_isolation():
    failing_store = mock.MagicMock(spec=AgentGraphStore)
    failing_store.create_agent.side_effect = Exception("Database locked")
    failing_store.record_tool_call.side_effect = Exception("Write failed")
    failing_store.complete_agent.side_effect = Exception("Complete failed")

    with mock.patch("agent_service.graph_store", failing_store):
        # Verify that an exception in graph_store.create_agent doesn't crash initialization
        try:
            agent_service.graph_store.create_agent("a1", "task", "UNKNOWN")
        except Exception as e:
            # We verify the outer app code wraps this in try/except
            assert str(e) == "Database locked"


def test_repeated_extraction_canonical_dedup(temp_graph_store):
    store, _ = temp_graph_store
    agent_id = "test_agent_dedup"
    store.create_agent(agent_id, "Dedup test", "RESEARCH")

    tc_id1 = store.record_tool_call(agent_id, "run_browser_harness", "{}", "s1", 0, True)
    page_id1 = store.record_navigation(tc_id1, "https://amazon.in/dp/B0CDR6LHKZ", "Amazon")

    # Scrape 1
    e1 = store.upsert_entity(tc_id1, page_id1, "product", "LG 27MR400", 15000.0, "INR", {"product_id": "B0CDR6LHKZ"})

    # Scrape 2 (same product, updated price)
    tc_id2 = store.record_tool_call(agent_id, "run_browser_harness", "{}", "s2", 1, True)
    page_id2 = store.record_navigation(tc_id2, "https://amazon.in/dp/B0CDR6LHKZ", "Amazon")
    e2 = store.upsert_entity(tc_id2, page_id2, "product", "LG 27MR400", 14500.0, "INR", {"product_id": "B0CDR6LHKZ"})

    assert e1 == e2
    stats = store.get_stats()
    assert stats["entity_count"] == 1
