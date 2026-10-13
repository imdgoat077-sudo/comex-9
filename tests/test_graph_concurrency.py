import os
import json
import shutil
import tempfile
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from graph.store import AgentGraphStore


@pytest.fixture
def temp_graph_store():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_p6_concurrency.db")
    store = AgentGraphStore(db_path)
    yield store, db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


# =====================================================================
# GM-032 / GM-033 / GM-034: Concurrency & Dedup Stress Test
# =====================================================================

def test_concurrent_agent_lifecycles_and_dedup(temp_graph_store):
    store, _ = temp_graph_store
    num_workers = 5
    barrier = threading.Barrier(num_workers)

    # Overlapping products data across workers to verify dedup under concurrency:
    # Workers 0, 1, 2 write Product 1 (LG 27MR400 / ASIN B0CDR6LHKZ) with formatting/casing variations
    # Worker 3 writes Product 2 (Samsung Odyssey G5)
    # Worker 4 writes Product 3 (Acer Nitro)
    # Expected unique Entity count after deduplication = 3
    worker_products = [
        [
            ("product", "LG 27MR400", 14999.0, "INR", {"product_id": "B0CDR6LHKZ"}),
            ("product", "Worker 0 Product B", 8000.0, "INR", {}),
            ("product", "Worker 0 Product C", 9000.0, "INR", {})
        ],
        [
            ("product", "lg 27mr400", 14500.0, "INR", {"product_id": "B0CDR6LHKZ"}), # Dedup with Product 1
            ("product", "Worker 1 Product B", 8500.0, "INR", {}),
            ("product", "Worker 1 Product C", 9500.0, "INR", {})
        ],
        [
            ("product", "  LG   27MR400  ", 14999.0, "INR", {"product_id": "B0CDR6LHKZ"}), # Dedup with Product 1
            ("product", "Worker 2 Product B", 8200.0, "INR", {}),
            ("product", "Worker 2 Product C", 9200.0, "INR", {})
        ],
        [
            ("product", "Samsung Odyssey G5", 19999.0, "INR", {"product_id": "B08SDF1234"}),
            ("product", "Worker 3 Product B", 12000.0, "INR", {}),
            ("product", "Worker 3 Product C", 13000.0, "INR", {})
        ],
        [
            ("product", "Acer Nitro VG270", 10499.0, "INR", {"product_id": "B0C774SSFW"}),
            ("product", "Worker 4 Product B", 11000.0, "INR", {}),
            ("product", "Worker 4 Product C", 15000.0, "INR", {})
        ]
    ]

    agent_ids = [f"agent_worker_{i}" for i in range(num_workers)]
    exceptions = []

    def worker_task(worker_idx: int):
        try:
            agent_id = agent_ids[worker_idx]
            # Synchronize all threads at start to maximize lock contention
            barrier.wait(timeout=10)

            # 1. create_agent
            store.create_agent(agent_id, f"Concurrent task {worker_idx}", "RESEARCH")

            # 2. record_tool_call
            tc_id = store.record_tool_call(
                agent_id, "run_browser_harness",
                args_json=f'{{"worker": {worker_idx}}}',
                result_summary="ok",
                step_index=0,
                success=True
            )

            # 3. record_navigation
            url = f"https://amazon.in/dp/B0{worker_idx}"
            page_id = store.record_navigation(tc_id, url, f"Amazon Page {worker_idx}")

            # 4. upsert 3 entities per worker
            for item in worker_products[worker_idx]:
                store.upsert_entity(
                    tc_id, page_id,
                    etype=item[0], name=item[1], price=item[2], currency=item[3], attrs=item[4]
                )

            # 5. complete_agent
            store.complete_agent(agent_id, "completed", 1)
        except Exception as e:
            exceptions.append((worker_idx, e))

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task, i) for i in range(num_workers)]
        for f in as_completed(futures):
            f.result()

    # Assert 1: Zero exceptions
    assert len(exceptions) == 0, f"Exceptions occurred during concurrent execution: {exceptions}"

    # Assert 2: All 5 Agents created and completed cleanly
    stats = store.get_stats()
    assert stats["agent_count"] == num_workers
    assert stats["toolcall_count"] == num_workers
    assert stats["page_count"] == num_workers

    for agent_id in agent_ids:
        prov = store.get_agent_provenance(agent_id)
        assert prov["status"] == "completed"
        assert len(prov["tool_calls"]) == 1
        assert len(prov["tool_calls"][0]["entities"]) == 3

    # Assert 3: Entity deduplication count
    # Workers 0, 1, 2 overlap on Product 1 (1 unique item).
    # Remaining distinct products: 2 for W0 + 2 for W1 + 2 for W2 + 3 for W3 + 3 for W4 = 12 distinct items.
    # Total expected unique entities = 1 + 12 = 13.
    assert stats["entity_count"] == 13


# =====================================================================
# GM-035 / GM-036: Performance Latency Measurement (p50, p95, p99)
# =====================================================================

def test_operation_performance_latencies(temp_graph_store):
    store, _ = temp_graph_store
    num_samples = 100

    timings = {
        "create_agent": [],
        "record_tool_call": [],
        "record_navigation": [],
        "upsert_entity": [],
        "find_recent_entities": [],
        "complete_agent": []
    }

    agent_id = "agent_perf_master"
    store.create_agent(agent_id, "Master Perf Agent", "RESEARCH")

    for i in range(num_samples):
        # create_agent
        t0 = time.perf_counter()
        aid = f"agent_perf_{i}"
        store.create_agent(aid, f"Perf task {i}", "RESEARCH")
        timings["create_agent"].append((time.perf_counter() - t0) * 1000.0)

        # record_tool_call
        t0 = time.perf_counter()
        tc_id = store.record_tool_call(aid, "run_browser_harness", '{"step": 0}', "ok", 0, True)
        timings["record_tool_call"].append((time.perf_counter() - t0) * 1000.0)

        # record_navigation
        t0 = time.perf_counter()
        page_id = store.record_navigation(tc_id, f"https://example.com/page_{i}", f"Page {i}")
        timings["record_navigation"].append((time.perf_counter() - t0) * 1000.0)

        # upsert_entity
        t0 = time.perf_counter()
        store.upsert_entity(tc_id, page_id, "product", f"Perf Item {i}", 1000.0 + i, "INR", {"index": i})
        timings["upsert_entity"].append((time.perf_counter() - t0) * 1000.0)

        # find_recent_entities
        t0 = time.perf_counter()
        store.find_recent_entities("product", max_price=5000.0, since_minutes=30)
        timings["find_recent_entities"].append((time.perf_counter() - t0) * 1000.0)

        # complete_agent
        t0 = time.perf_counter()
        store.complete_agent(aid, "completed", 1)
        timings["complete_agent"].append((time.perf_counter() - t0) * 1000.0)

    # Calculate and report p50, p95, p99, max for each operation
    report_rows = []
    for op_name, samples in timings.items():
        sorted_samples = sorted(samples)
        p50 = sorted_samples[int(0.50 * len(sorted_samples))]
        p95 = sorted_samples[int(0.95 * len(sorted_samples))]
        p99 = sorted_samples[int(0.99 * len(sorted_samples))]
        max_val = max(sorted_samples)
        report_rows.append({
            "operation": op_name,
            "sample_count": len(samples),
            "p50_ms": round(p50, 3),
            "p95_ms": round(p95, 3),
            "p99_ms": round(p99, 3),
            "max_ms": round(max_val, 3)
        })
        # Assert target < 50ms p95 for single-threaded operations
        assert p95 < 50.0, f"Operation {op_name} p95 ({p95:.2f}ms) exceeded 50ms target"

    # Store stats in a file for report generation
    perf_summary_file = os.path.join(tempfile.gettempdir(), "comex_perf_results.json")
    with open(perf_summary_file, "w") as f:
        json.dump(report_rows, f, indent=2)
