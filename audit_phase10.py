import os
import shutil
import time
from graph.store import AgentGraphStore

# 1. Trigger Policy Test
def test_triggers():
    print("--- TRIGGER POLICY TESTS ---")
    trigger_phrases = [
        "previously", "earlier", "last time", "what did you find", "you found",
        "that test", "compare with", "remember", "previous", "exact information",
        "we collected", "we found", "you collected", "what did i ask", "history"
    ]
    
    true_positives = [
        "What monitors did you find before?",
        "Which monitors had you found under ₹15,000?",
        "Can you remind me which monitors you found?",
        "Which monitors are in your records?",
        "What were those monitors you showed me?",
        "Tell me the monitor options from our earlier work.",
        "Compare the monitors you already collected.",
        "Use what you already know about the monitors."
    ]
    
    false_positives = [
        "Previously, define a binary tree.",
        "Earlier, what is recursion?",
        "Give me a history of Python.",
        "Create a new test called previously_fetched."
    ]
    
    def triggers(task):
        t = task.lower()
        return any(p in t for p in trigger_phrases)

    print("Expected True Positives:")
    for tp in true_positives:
        print(f"  {tp!r} -> {triggers(tp)}")

    print("\nExpected False Positives (Should Ideally Not Trigger or Harmless if they do):")
    for fp in false_positives:
        print(f"  {fp!r} -> {triggers(fp)}")

# 2. BM25 Natural Language Variation Test
def test_bm25_variations():
    print("\n--- BM25 NATURAL LANGUAGE VARIATIONS ---")
    db_path = os.path.expanduser("~/.comex/audit_graph.db")
    if os.path.exists(db_path):
        if os.path.isdir(db_path): shutil.rmtree(db_path)
        else: os.remove(db_path)
        
    store = AgentGraphStore(db_path)
    store.save_artifact("ag1", "Programming Test — Exact Questions", "report", "Q1: What is Python?")
    
    queries = [
        "What were the programming questions?Can you remind me about that test?",
        "What questions were in the earlier programming test?",
        "What did we solve in the programming assessment?",
        "programming! test? exact: questions.",
        "PROGRAMMING TEST EXACT QUESTIONS",
        "Can you find the coding quiz?"
    ]
    
    import re
    for q in queries:
        clean = re.sub(r'[^\w\s]', '', q)
        res = store.search_memory(clean, "ALL")
        print(f"Query: {q!r} -> Hits: {len(res)}")

# 3. Automatic Context Relevance
def test_relevance():
    print("\n--- AUTOMATIC CONTEXT RELEVANCE ---")
    db_path = os.path.expanduser("~/.comex/audit_graph.db")
    if os.path.exists(db_path):
        if os.path.isdir(db_path): shutil.rmtree(db_path)
        else: os.remove(db_path)
        
    store = AgentGraphStore(db_path)
    store.save_artifact("agA", "Monitor research.", "report", "Monitors")
    store.save_artifact("agB", "Mechanical keyboard research.", "report", "Keyboards")
    store.save_artifact("agC", "A programming test.", "report", "Code")
    store.save_artifact("agD", "A random unrelated artifact with overlapping words: monitor test.", "report", "Noise")
    
    queries = [
        "What monitors did you find earlier?",
        "Which keyboard did you find?",
        "What were the test questions?",
        "Tell me about the monitors I researched."
    ]
    import re
    for q in queries:
        clean = re.sub(r'[^\w\s]', '', q)
        res = store.search_memory(clean, "ALL", limit=3)
        print(f"\nQuery: {q!r}")
        for r in res:
            print(f"  - {r.get('content_excerpt')[:40]} (Score: {r.get('relevance_score'):.3f})")

# 4. Ranking vs Limit
def test_ranking_limit():
    print("\n--- RANKING VS LIMIT ---")
    db_path = os.path.expanduser("~/.comex/audit_graph.db")
    if os.path.exists(db_path):
        if os.path.isdir(db_path): shutil.rmtree(db_path)
        else: os.remove(db_path)
        
    store = AgentGraphStore(db_path)
    # 10 weakly matching
    for i in range(10):
        store.save_artifact(f"agW{i}", f"Weak match {i}", "report", "Something about the keyword.")
    # 1 strongly matching
    store.save_artifact("agS", "Strong Keyword match", "report", "The keyword is deeply discussed keyword keyword keyword.")
    
    res = store.search_memory("keyword", "ALL", limit=3)
    print("Top 3 results for 'keyword':")
    for r in res:
        print(f"  - {r.get('content_excerpt')} (Score: {r.get('relevance_score'):.3f})")

if __name__ == "__main__":
    test_triggers()
    test_bm25_variations()
    test_relevance()
    test_ranking_limit()
