import asyncio
from agent_service import execute_agent_loop

async def main():
    try:
        res, meta = await execute_agent_loop(
            task="Go to https://the-internet.herokuapp.com/login and login",
            default_cdp_url="ws://127.0.0.1:9222/devtools/browser/xyz",
            intent="VISIBLE_BROWSER_TASK",
            use_procedures=False,
            procedure_mode="none"
        )
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
