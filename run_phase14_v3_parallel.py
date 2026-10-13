import asyncio
import json
import tempfile
import os
import urllib.parse
import time
import random
import uuid

from graph.store import AgentGraphStore
from agent_service import execute_agent_loop

async def run_trial_isolated(i: int, run_info: dict, procs: dict, tasks: dict):
    # Setup isolated graph store
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"graph_{i}.db")
    
    # We must patch os.environ for the duration of the setup, or better yet, instantiate explicitly
    # Unfortunately agent_service relies on global `active_graph_store`.
    # BUT wait! If we run concurrently, global `active_graph_store` will be overwritten by different tasks!
    # Ah!! This is why I ran it sequentially! `agent_service.py` uses global state.
    pass
