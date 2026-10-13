import sys

def patch():
    with open("graph/store.py", "r") as f:
        content = f.read()

    # Add save_artifact and get_artifact before find_recent_entities (or anywhere inside AgentGraphStore)
    new_methods = """
    def save_artifact(self, agent_id: str, title: str, artifact_type: str, content: str) -> str:
        with self._lock:
            now = _utcnow()
            artifact_id = f"art_{uuid.uuid4().hex}"
            query = \"\"\"
            MERGE (a:Artifact {id: $id})
            ON CREATE SET a.artifact_type = $type,
                          a.title = $title,
                          a.content = $content,
                          a.created_at = $now,
                          a.source_agent_id = $agent_id
            \"\"\"
            params = {
                "id": artifact_id,
                "type": artifact_type or "document",
                "title": title or "Untitled Artifact",
                "content": content or "",
                "now": now,
                "agent_id": agent_id
            }
            try:
                self.conn.execute(query, params)
                if agent_id:
                    rel_q = \"\"\"
                    MATCH (ag:Agent {id: $agent_id}), (a:Artifact {id: $id})
                    MERGE (ag)-[:CREATED_ARTIFACT]->(a)
                    \"\"\"
                    self.conn.execute(rel_q, {"agent_id": agent_id, "id": artifact_id})
                return artifact_id
            except Exception as e:
                logger.warning(f"Failed to save artifact: {e}")
                return ""

    def get_artifact(self, artifact_id: str) -> dict:
        with self._lock:
            query = "MATCH (a:Artifact {id: $id}) RETURN a.title, a.artifact_type, a.content, a.created_at, a.source_agent_id"
            try:
                res = self.conn.execute(query, {"id": artifact_id})
                if res.has_next():
                    row = res.get_next()
                    return {
                        "id": artifact_id,
                        "title": row[0],
                        "artifact_type": row[1],
                        "content": row[2],
                        "created_at": str(row[3]),
                        "source_agent_id": row[4]
                    }
            except Exception as e:
                logger.warning(f"Failed to get artifact {artifact_id}: {e}")
            return {}
"""

    if "def save_artifact" not in content:
        content = content.replace("    def find_recent_entities", new_methods + "\n    def find_recent_entities")

    # Update search_memory domains
    search_mem_start = """            if domain == "ENTITIES":
                domains_to_search = [("Entity", "Entity_FTS")]
            elif domain == "HISTORY":
                domains_to_search = [("Agent", "Agent_FTS"), ("ToolCall", "ToolCall_FTS")]
            else: # ALL
                domains_to_search = [("Entity", "Entity_FTS"), ("Agent", "Agent_FTS"), ("ToolCall", "ToolCall_FTS")]"""
    
    search_mem_new = """            if domain == "ENTITIES":
                domains_to_search = [("Entity", "Entity_FTS")]
            elif domain == "HISTORY":
                domains_to_search = [("Agent", "Agent_FTS"), ("ToolCall", "ToolCall_FTS")]
            elif domain == "ARTIFACTS":
                domains_to_search = [("Artifact", "Artifact_FTS")]
            else: # ALL
                domains_to_search = [("Entity", "Entity_FTS"), ("Agent", "Agent_FTS"), ("ToolCall", "ToolCall_FTS"), ("Artifact", "Artifact_FTS")]"""

    content = content.replace(search_mem_start, search_mem_new)

    # Update search_memory result parsing for Artifact
    toolcall_parse_end = """                            prov_q = "MATCH (tc:ToolCall {id: $id})<-[:EXECUTED]-(a:Agent) RETURN a.id LIMIT 1"
                            prov_res = self.conn.execute(prov_q, {"id": node.get("id")})
                            if prov_res.has_next():
                                result_dict["provenance"] = prov_res.get_next()[0]
                                """
                                
    artifact_parse_new = """
                        elif table_name == "Artifact":
                            result_dict["timestamp"] = str(node.get("created_at"))
                            title = node.get("title")
                            content = node.get("content")
                            atype = node.get("artifact_type")
                            result_dict["content_excerpt"] = f"Artifact [{atype}]: {title}\\n{content}"
                            
                            prov_q = "MATCH (a:Artifact {id: $id})<-[:CREATED_ARTIFACT]-(ag:Agent) RETURN ag.id LIMIT 1"
                            prov_res = self.conn.execute(prov_q, {"id": node.get("id")})
                            if prov_res.has_next():
                                result_dict["provenance"] = prov_res.get_next()[0]
"""

    if "elif table_name == \"Artifact\":" not in content:
        content = content.replace(toolcall_parse_end, toolcall_parse_end + artifact_parse_new)

    with open("graph/store.py", "w") as f:
        f.write(content)
        print("Patched graph/store.py")

patch()
