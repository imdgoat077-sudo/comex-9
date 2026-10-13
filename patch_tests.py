import sys

def patch():
    with open("tests/test_phase9_artifact_memory.py", "r") as f:
        content = f.read()

    # Fix Agent task to avoid BM25 collision
    content = content.replace(
        'fresh_store.create_agent(agent_id, "test task", "UNKNOWN")',
        'fresh_store.create_agent(agent_id, "unrelated objective", "UNKNOWN")'
    )

    # Make side_effect_a async
    content = content.replace(
        'def side_effect_a(*args, **kwargs):',
        'async def side_effect_a(*args, **kwargs):'
    )

    # Make side_effect_b async
    content = content.replace(
        'def side_effect_b(*args, **kwargs):',
        'async def side_effect_b(*args, **kwargs):'
    )

    # Make side_effect_c async
    content = content.replace(
        'def side_effect_c(*args, **kwargs):',
        'async def side_effect_c(*args, **kwargs):'
    )

    with open("tests/test_phase9_artifact_memory.py", "w") as f:
        f.write(content)
        print("Patched tests")

patch()
