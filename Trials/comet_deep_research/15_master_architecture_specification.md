# 15 — Master Architecture Specification: Designing Comex

## 1. Executive Summary & Purpose

The ultimate objective of this reverse-engineering mission is to transfer the architectural triumphs of Perplexity's Comet browser (`ai.perplexity.comet`) into **Comex**—an independently implemented, state-of-the-art AI browser automation environment.

While Comet is implemented as a proprietary Chromium C++ fork running Chrome Extensions, Comex is built upon:
- **Electron 43.4.0**: Providing cross-platform desktop UI, native window management, and native Chromium rendering.
- **FastAPI Python Daemon (Port 8000)**: Housing high-performance AI agent orchestration, LLM connectors (Anthropic, Gemini, OpenAI), and Model Context Protocol (MCP) tooling.
- **Chrome DevTools Protocol (Port 9222)**: Providing direct, raw WebSocket debugger automation.

This document translates Comet's verified mechanisms into production-ready specifications for Comex.

---

## 2. Architectural Comparison: Comet vs. Comex

```
+----------------------------------------------------------------------------------------------------+
|                                    COMET (Chromium Fork Architecture)                              |
|                                                                                                    |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
|  | C++ Chromium Core   |   | Background Worker   |   | Frontend SPA        |   | Native C++ MCP  | |
|  | - WebMCP in Blink   |-->| - dM (RPC Dispatch) |-->| - StreamMiddlewares |-->| - mcp_stdio_*   | |
|  | - libaperitif.dylib |   | - iP (ComputerBatch)|   | - Floating Sidecar  |   | - /bin/zsh pipe | |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
+----------------------------------------------------------------------------------------------------+

                                                  vs.

+----------------------------------------------------------------------------------------------------+
|                                    COMEX (Electron + FastAPI Architecture)                         |
|                                                                                                    |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
|  | Electron 43.4.0     |   | FastAPI Daemon      |   | Web Client UI       |   | Python MCP Hub  | |
|  | - BrowserWindow     |-->| (Port 8000)         |-->| (React / Vite)      |-->| - asyncio pipes | |
|  | - CDP Remote (9222) |   | - ComputerBatch     |   | - Real-time HUD     |   | - JSON-RPC 2.0  | |
|  | - Isolated Contexts |   | - Hybrid Perception |   | - Sidecar Assistant |   | - Pydantic tool | |
|  +---------------------+   +---------------------+   +---------------------+   +-----------------+ |
+----------------------------------------------------------------------------------------------------+
```

| Architectural Subsystem | Comet Implementation | Comex Recommended Target Port |
|---|---|---|
| **Core Runtime** | Proprietary Chromium 154.0.8037 C++ Fork | Electron 43.4.0 (`remote-debugging-port=9222`) |
| **Agent Controller** | Extension Service Worker (`background.js`) | FastAPI Python Daemon (`http://localhost:8000`) |
| **CDP Client** | Chrome Extension `chrome.debugger` API | Asynchronous `aiohttp` / `websockets` Python client |
| **Coordinate Scaling** | JavaScript `eP` / `gP` / `hP` / `_P` | Python `ViewportScaler` class |
| **Perception Engine** | JS `gN` (`Accessibility` + `DOMSnapshot`) | Python `HybridPerceptionEngine` compiling YAML |
| **Typing Emulation** | JS `uP` (ClipboardItem swap) | Python CDP `Input.dispatchKeyEvent` + Clipboard bridge |
| **Wait Coordinator** | JS `oN` / `sN` debouncer | Python `SmartWaitCoordinator` listening to CDP socket |
| **MCP Integration** | C++ `mcp_stdio_client.cc` + `/bin/zsh` | Native Python `asyncio.subprocess` MCP Server/Client |
| **Subagents** | Hidden Chrome Tab Groups (`pM`) | Headless Electron `WebContents` / Hidden Windows |

---

## 3. Comex Core Components Design

### Component 1: Python Viewport Scaling Engine (`ViewportScaler`)
Porting Comet's `eP`, `hP`, `gP`, and `_P`:

```python
import math
from typing import Tuple, List, Optional
from pydantic import BaseModel

class ViewportInfo(BaseModel):
    viewport_width: int
    viewport_height: int
    screenshot_width: int
    screenshot_height: int

class ViewportScaler:
    MAX_AREA: float = 1.15 * 10**6  # 1,150,000 pixels (Anthropic budget)
    MAX_DIM: int = 1568             # 1568 px max dimension

    @classmethod
    def calculate_scaled_dimensions(cls, width: int, height: int) -> ViewportInfo:
        area = width * height
        if area > cls.MAX_AREA:
            scale = math.sqrt(cls.MAX_AREA / area)
        elif width > cls.MAX_DIM:
            scale = cls.MAX_DIM / width
        elif height > cls.MAX_DIM:
            scale = cls.MAX_DIM / height
        else:
            scale = 1.0

        return ViewportInfo(
            viewport_width=width,
            viewport_height=height,
            screenshot_width=round(width * scale),
            screenshot_height=round(height * scale)
        )

    @classmethod
    def model_to_cdp_coords(cls, coords: List[int], info: ViewportInfo) -> Tuple[int, int]:
        scale = info.viewport_width / info.screenshot_width
        return round(coords[0] * scale), round(coords[1] * scale)

    @classmethod
    def has_viewport_drifted(cls, old_info: Optional[ViewportInfo], new_info: ViewportInfo) -> bool:
        if not old_info:
            return False
        return (old_info.viewport_width != new_info.viewport_width or 
                old_info.viewport_height != new_info.viewport_height)
```

---

### Component 2: Python Hybrid Perception Engine (`HybridPerceptionEngine`)
Porting Comet's `gN`, `pN`, and `_N`:

```python
import asyncio
from typing import Dict, Any, List

class HybridPerceptionEngine:
    def __init__(self, cdp_session):
        self.cdp = cdp_session

    async def capture_state(self, viewport_info: ViewportInfo) -> Dict[str, Any]:
        # 1. Concurrent CDP queries
        dpr_task = self.cdp.send("Runtime.evaluate", {"expression": "window.devicePixelRatio || 1"})
        snap_task = self.cdp.send("DOMSnapshot.captureSnapshot", {
            "computedStyles": ["cursor"],
            "includePaintOrder": False,
            "includeDOMRects": False
        })
        ax_task = self.cdp.send("Accessibility.getFullAXTree", {})
        shot_task = self.cdp.send("Page.captureScreenshot", {
            "format": "jpeg",
            "quality": 75,
            "fromSurface": True
        })

        dpr_res, snap_res, ax_res, shot_res = await asyncio.gather(
            dpr_task, snap_task, ax_task, shot_task
        )

        dpr = dpr_res.get("result", {}).get("value", 1.0)
        scale_mult = viewport_info.screenshot_width / viewport_info.viewport_width

        # 2. Extract DOMSnapshot bounds & pointer styles (pN)
        node_map = self._extract_snapshot(snap_res, dpr, scale_mult, viewport_info)

        # 3. Construct indexed YAML representation (_N)
        yaml_tree = self._build_yaml_tree(ax_res["nodes"], node_map)

        return {
            "base64_image": shot_res["data"],
            "yaml_tree": yaml_tree,
            "viewport": viewport_info
        }

    def _extract_snapshot(self, snapshot, dpr, scale_mult, vp):
        # Maps backendNodeId to coordinates and cursor style
        # (Direct port of Comet's pN algorithm)
        ...

    def _build_yaml_tree(self, ax_nodes, node_map):
        # Traverses AXTree, prunes depth > 15, truncates text > 100 ch, adds refs
        # (Direct port of Comet's _N algorithm)
        ...
```

---

### Component 3: Resilient CDP Connection Manager
Porting Comet's self-healing `dM` logic into Python:

```python
class ResilientCDPSession:
    def __init__(self, tab_id: int, ws_url: str):
        self.tab_id = tab_id
        self.ws_url = ws_url
        self.ws = None

    async def execute_tool_with_retry(self, action_func, *args, **kwargs):
        try:
            return await asyncio.wait_for(action_func(*args, **kwargs), timeout=45.0)
        except Exception as e:
            err_msg = str(e)
            if "Debugger is not attached" in err_msg or "closed" in err_msg:
                # Re-attach and retry once
                await self.reconnect()
                return await action_func(*args, **kwargs)
            elif "timed out" in err_msg.lower():
                # Hard reload tab and retry
                await self.reload_tab()
                await self.reconnect()
                return await action_func(*args, **kwargs)
            raise e
```

---

## 4. Implementation Phasing for Comex

1. **Phase 1: Viewport Geometry & Resilient Input Engine**
   - Implement `ViewportScaler` with Anthropic $1.15\text{M px}$ area budget.
   - Implement `_P` viewport drift check before all batched click actions.
   - Implement clipboard-swapping typing fallback for complex textboxes.

2. **Phase 2: Hybrid Perception Pipeline**
   - Replace raw HTML serialization with dual-tier CDP capture (`Accessibility.getFullAXTree` + `DOMSnapshot.captureSnapshot`).
   - Format output into compact, token-efficient YAML.

3. **Phase 3: Smart Waiting Heuristics**
   - Implement event-driven CDP wait coordinator replacing hardcoded `time.sleep()`.

4. **Phase 4: Python Native Model Context Protocol (MCP) Daemon**
   - Provide native `/bin/zsh` stdio subprocess execution directly in the FastAPI daemon.
