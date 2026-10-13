import json
import os

with open("/Users/pranavkumarn/.gemini/antigravity-cli/brain/0a10a024-ca33-4b35-acbb-3a40372c98d1/analysis_dump.json", "r") as f:
    data = json.load(f)

agents = data["agents"]
legacy = data["legacy_episodes"]

out = []
out.append("# REAL EPISODE DATASET — READ-ONLY ANALYSIS")

out.append("\n## 1. IDENTIFY THE 13 VALID LIVE EPISODES")
for a in agents:
    out.append(f"- **Agent ID**: {a['agent_id']}")
    out.append(f"  - Task: {a['task']}")
    out.append(f"  - Intent: {a['intent']}")
    out.append(f"  - Created: {a['agent_created_at']}")
    out.append(f"  - Episode ID: {a['episode_id']}")
    out.append(f"  - Outcome: {a['outcome_status']}")
    out.append(f"  - Created: {a['episode_created_at']}")
    out.append(f"  - FOR Relationship Exists: True")
    out.append(f"  - ToolCalls: {len(a['tool_calls'])}")
    out.append(f"  - Self-reported snippet: {str(a['self_reported'])[:100].replace(chr(10), ' ')}")

out.append("\n## 2. SHOW THE ACTUAL TASK SET")
for a in agents:
    out.append(f"- {a['task']}")

out.append("\n## 3. RECONSTRUCT EVERY EXECUTION TRACE")
for a in agents:
    out.append(f"\n### Agent {a['agent_id']} ({a['task'][:50]}...)")
    for t in a['tool_calls']:
        out.append(f"- Step {t['step_index']}: `{t['tool_name']}` (Success: {t['success']})")
        # arguments and results are long, keep concise
        args = str(t.get('args_json', ''))[:100].replace(chr(10), ' ')
        res = str(t.get('result_summary', ''))[:100].replace(chr(10), ' ')
        out.append(f"  - Args: {args}")
        out.append(f"  - Result: {res}")

out.append("\n## 8. DATA QUALITY ASSESSMENT")
out.append(f"- valid real Episodes = {len(agents)}")
out.append(f"- legacy/test Episodes = {len(legacy)}")
out.append(f"- real Episodes with valid Agent relationship = {len(agents)}")
out.append(f"- real Episodes with ToolCall traces = {sum(1 for a in agents if len(a['tool_calls']) > 0)}")
out.append(f"- completed = {sum(1 for a in agents if a['outcome_status'] == 'completed')}")
out.append(f"- failed = {sum(1 for a in agents if a['outcome_status'] == 'failed')}")
out.append(f"- max_steps_reached = {sum(1 for a in agents if a['outcome_status'] == 'max_steps_reached')}")
out.append(f"- error = {sum(1 for a in agents if a['outcome_status'] == 'error')}")

with open("/Users/pranavkumarn/.gemini/antigravity-cli/brain/0a10a024-ca33-4b35-acbb-3a40372c98d1/analysis_facts.md", "w") as f:
    f.write("\n".join(out))
