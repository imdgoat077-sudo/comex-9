"""
One-off visible demo (not a benchmark): the new-code agent draws a detailed rocket on excalidraw.com in a visible Chrome window.
Isolated: own Chrome profile, own backend on port 8091 with a throwaway graph database. Leaves the window open until
`benchmarks/demo/stop` exists (or 20 minutes), so the result can be looked at.
"""
import asyncio, base64, os, shutil, sys, tempfile, time
from pathlib import Path

os.environ["COMEX_LAB_VISIBLE"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmarks"))
import httpx  # noqa: E402
import hybrid_scenarios as H  # noqa: E402
from nervous.cdp_session import WebSocketCDPClient  # noqa: E402
from tests.browser_lab import BrowserLab  # noqa: E402

TASK = ("This tab has a whiteboard drawing app (Excalidraw). Draw a beautiful, detailed rocket on the canvas: a pointed nose cone, "
        "a tall body with a round porthole window and a couple of stripes, two fins on the sides, an engine base with nozzles, "
        "flames coming out underneath, and a few stars in the background. Use colours and fills so it looks good. "
        "When you are done, look at the canvas and tell me what you drew and anything you could not do.")


TASK_V2 = ("This tab has a whiteboard drawing app (Excalidraw). Draw a colourful, detailed rocket on the canvas, using the colour and fill "
           "controls so every important shape has a solid fill. First draw one large dark navy rectangle, solid fill, covering most of the "
           "canvas as the night sky. On top of it draw: a red pointed nose cone; a white rounded rocket body; two red stripes across the body; "
           "a round porthole window with a dark blue rim and light blue glass; two red fins, one on each side, as filled triangles; a dark grey "
           "engine base with two grey nozzles; flames below the nozzles with an orange outer flame and a smaller yellow inner flame; and about "
           "six small yellow stars in the sky around the rocket. Take a screenshot to check the result, and fix anything that is missing, "
           "unfilled or in the wrong place. When you are done, tell me what you drew and anything you could not do.")
NAME = sys.argv[1] if len(sys.argv) > 1 else "v1"
if NAME.endswith("v2"):
    TASK = TASK_V2
SUFFIX = "" if NAME == "v1" else f"_{NAME}"


async def main():
    out = ROOT / "benchmarks/demo"
    lab = BrowserLab.start()
    db = tempfile.mkdtemp(prefix="comex-demo-db-")
    BACKEND = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT
    proc = H.start_backend(BACKEND, lab.cdp_http, db, out / f"rocket{SUFFIX}_backend.log")
    try:
        page = H._open(lab, "https://excalidraw.com/")
        await H._reset_excalidraw(page)
        lab.only(page)
        print("started: agent is drawing", flush=True)
        async with httpx.AsyncClient() as client:
            events, wall, final, err = await H.run_agent(client, TASK, 600)
        answer = (final or {}).get("content") or (final or {}).get("text") or ""
        print(f"finished in {wall:.0f}s error={err}\n--- agent answer ---\n{answer}\n", flush=True)
        (out / f"rocket{SUFFIX}_answer.md").write_text(answer)
        cdp = WebSocketCDPClient(page.ws_url)
        await cdp.connect()
        shot = await cdp.send("Page.captureScreenshot", {"format": "png"})
        (out / f"rocket{SUFFIX}_final.png").write_bytes(base64.b64decode(shot["data"]))
        await cdp.close()
        print(f"saved benchmarks/demo/rocket{SUFFIX}_final.png; window stays open until benchmarks/demo/stop exists", flush=True)
        for _ in range(int(os.getenv("DEMO_HOLD_S", "1200")) // 5):
            if (out / "stop").exists():
                break
            await asyncio.sleep(5)
    finally:
        proc.terminate()
        lab.stop()
        shutil.rmtree(db, ignore_errors=True)


asyncio.run(main())
