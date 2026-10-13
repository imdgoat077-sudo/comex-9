import urllib.request
import json
import asyncio
import websockets

CDP_URL = "http://127.0.0.1:9222"

async def test():
    req = urllib.request.urlopen(f"{CDP_URL}/json/list")
    targets = json.loads(req.read())
    ui_ws = None
    for t in targets:
        if t.get("type") == "page" and ("localhost:5173" in t.get("url", "") or "index.html" in t.get("url", "")):
            ui_ws = t.get("webSocketDebuggerUrl")
            print("Found UI tab:", t.get("title"))
            break
    
    if not ui_ws:
        print("UI tab not found")
        return
        
    async with websockets.connect(ui_ws) as ws:
        msg = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "window.nexusNative.tabs.createHiddenAgentTab('test-bg-tab', 'https://example.com')"
            }
        }
        await ws.send(json.dumps(msg))
        resp = await ws.recv()
        print("Response:", resp)

asyncio.run(test())
