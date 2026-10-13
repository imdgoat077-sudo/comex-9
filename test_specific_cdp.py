import asyncio
import urllib.request
import json
from playwright.async_api import async_playwright

async def run():
    req = urllib.request.urlopen("http://127.0.0.1:9222/json/list")
    targets = json.loads(req.read())
    
    # Find the Comex React shell target (http://localhost:5173/)
    target = next(t for t in targets if "5173" in t.get("url", ""))
    ws_url = target["webSocketDebuggerUrl"]
    print(f"Connecting directly to: {ws_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_url)
        context = browser.contexts[0]
        page = context.pages[0]
        title = await page.title()
        print(f"Connected to page title: {title}")
        
        await browser.close()

asyncio.run(run())
