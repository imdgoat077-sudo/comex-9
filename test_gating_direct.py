import asyncio
from agent_service import execute_agent_loop
import os
import json

async def main():
    print("Testing GATED_PROCEDURAL directly...")
    res, meta = await execute_agent_loop(
        task="Go to https://the-internet.herokuapp.com/login and login",
        default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
        intent="VISIBLE_BROWSER_TASK",
        use_procedures=True,
        procedure_mode="gated"
    )
    print("Meta:")
    print(json.dumps(meta, indent=2))

asyncio.run(main())
