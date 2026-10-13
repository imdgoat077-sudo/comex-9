import sys

def patch():
    with open("graph/tools.py", "r") as f:
        content = f.read()

    new_tool = """
def make_save_artifact_tool(graph_store, agent_id: str, step_ref: dict):
    @langchain_tool
    def save_artifact(title: str, artifact_type: str, content: str) -> str:
        \"\"\"Save a completed result or durable unstructured knowledge as an Artifact.
        Use this tool to persist final reports, collected lists, research summaries,
        or exact sets of questions.
        \"\"\"
        try:
            artifact_id = graph_store.save_artifact(agent_id, title, artifact_type, content)
            if artifact_id:
                try:
                    graph_store.record_tool_call(
                        agent_id, "save_artifact",
                        args_json=json.dumps({"title": title, "artifact_type": artifact_type, "content_length": len(content)}),
                        result_summary=f"Saved artifact {artifact_id} ({len(content)} chars)",
                        step_index=step_ref.get("value", 0),
                        success=True
                    )
                except Exception as re:
                    logger.warning(f"Graph: failed to record save_artifact tool call: {re}")
                return f"Successfully saved artifact '{title}' (ID: {artifact_id})."
            return "Failed to save artifact."
        except Exception as e:
            logger.warning(f"save_artifact failed: {e}")
            return f"save_artifact failed: {e}"
    
    return save_artifact
"""
    if "def make_save_artifact_tool" not in content:
        content = content + "\n" + new_tool
        with open("graph/tools.py", "w") as f:
            f.write(content)
            print("Patched graph/tools.py")

patch()
