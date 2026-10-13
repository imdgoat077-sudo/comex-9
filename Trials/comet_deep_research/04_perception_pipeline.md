# 04 — Perception Pipeline: Dual-Tier Vision & DOM Synthesis

## 1. Architecture Overview

Comet's perception pipeline combines **visual perception** (lossy, downsampled screenshot images for multimodal LLMs) with **semantic structural perception** (lossless, token-optimized YAML trees synthesized from Chrome DevTools Protocol).

Unlike naive browser automation tools that either send raw HTML (exploding LLM context windows) or rely purely on vision (susceptible to hallucinated bounding boxes), Comet executes a **dual-tier hybrid perception algorithm** (`gN`):

```
                        +----------------------------+
                        |   CDP Debugger Session     |
                        +--------------+-------------+
                                       |
             +-------------------------+-------------------------+
             |                                                   |
             v                                                   v
+-------------------------+                         +-------------------------+
|   Visual Perception     |                         |  Structural Perception  |
|  Page.captureScreenshot |                         |   gN() Composite Scan   |
+------------+------------+                         +------------+------------+
             |                                                   |
             | JPEG (q=75, surface)                              | 4 Concurrent Queries:
             v                                                   | 1. Runtime.evaluate (DPR)
+-------------------------+                                      | 2. DOMSnapshot.captureSnapshot
|  Canvas Resizer & Mark  |                                      | 3. Accessibility.getFullAXTree
|    eP() / ZN / QN       |                                      | 4. Runtime.evaluate (origin)
+------------+------------+                                      v
             |                                      +-------------------------+
             | Bounded to <= 1.15M px               | Snapshot Extractor pN() |
             | Max dimension <= 1568px              | - Cursor styles (pointer)|
             | Optional pink click dot              | - Viewport culling      |
             v                                      | - Center coords [x, y]  |
+-------------------------+                         +------------+------------+
|  Base64 Screenshot Image|                                      |
+------------+------------+                                      v
             |                                      +-------------------------+
             |                                      | YAML Tree Generator _N()|
             |                                      | - Truncate text (100 ch)|
             |                                      | - Filter non-interactive|
             |                                      | - Inject ref & coords   |
             |                                      +------------+------------+
             |                                                   |
             +-------------------------+-------------------------+
                                       |
                                       v
                     +-----------------------------------+
                     | Final Model Context Payload       |
                     | - base64_image (Vision Input)     |
                     | - tab_context.result (YAML Tree)  |
                     +-----------------------------------+
```

---

## 2. Visual Perception Engine (`$N` & `eP`)

### Resolution Scaling and Area Budget
Anthropic's Claude 3.5 Sonnet Computer-Use API enforces a maximum image budget of approximately $1.15 	ext{ megapixels}$ and a maximum bounding dimension of $1568	ext{ px}$. Comet directly embeds these constants in `background.js`:

```javascript
const ZN = 1.15 * 10 ** 6; // 1,150,000 pixels maximum area budget
const QN = 1568;           // 1568 px maximum single-dimension limit
```

The scaling multiplier $o$ is computed dynamically in `eP`:
$$	ext{Area} = W_v 	imes H_v$$
$$o = egin{cases}
\sqrt{rac{ZN}{	ext{Area}}} & 	ext{if } 	ext{Area} > ZN \
rac{QN}{W_v} & 	ext{else if } W_v > QN \
rac{QN}{H_v} & 	ext{else if } H_v > QN \
1.0 & 	ext{otherwise}
\end{cases}$$

$$	ext{screenshotWidth} = 	ext{round}(W_v 	imes o)$$
$$	ext{screenshotHeight} = 	ext{round}(H_v 	imes o)$$

### Surface Screenshot Capture
Screenshots are captured using CDP `Page.captureScreenshot`:
```javascript
const screenshot = await chrome.debugger.sendCommand({ tabId }, "Page.captureScreenshot", {
  format: "jpeg",
  quality: 75,
  fromSurface: true,
  optimizeForSpeed: true,
  screenshotNewSurface: true
});
```

### Visual Click Ripple Feedback
When visual verification of a click is required, the canvas manipulation helper draws an OKLCH colored circle at the interaction coordinate:
```javascript
// Draws a 20px scaled dot at the click coordinates
let t = Math.round((screenshotWidth / viewportWidth) * 20);
ctx.fillStyle = "oklch(71.92% 0.112 205.51)";
ctx.beginPath();
ctx.arc(clickX, clickY, t, 0, 2 * Math.PI);
ctx.fill();
```

---

## 3. Structural Perception Engine (`gN`, `pN`, `_N`)

### Concurrent CDP Extraction
`gN` executes four operations concurrently using `Promise.all`:
1. `Runtime.evaluate`: `window.devicePixelRatio || 1`
2. `DOMSnapshot.captureSnapshot`: Queries computed styles `["cursor"]`, ignoring paint order and background colors to minimize serialize overhead.
3. `Accessibility.getFullAXTree`: Retrieves Chromium's internal accessibility hierarchy.
4. `Runtime.evaluate`: `window.location.origin`

### Snapshot Node Extraction (`pN`)
`pN` indexes layout bounds from the DOMSnapshot document and scales them by Device Pixel Ratio (DPR) and `scaleMultiplier`:
```javascript
const pN = (snapshot, dpr, scaleMultiplier) => {
  const doc = snapshot.documents[0];
  const nodeMap = new Map();
  const vpWidth = doc.layout.bounds?.[0]?.[2] || 1920;
  const vpHeight = doc.layout.bounds?.[0]?.[3] || 1080;

  snapshot.documents.forEach(({ nodes, layout, scrollOffsetX, scrollOffsetY }) => {
    const scrollX = scrollOffsetX || 0;
    const scrollY = scrollOffsetY || 0;

    layout.nodeIndex.forEach((nodeIdx, layoutIdx) => {
      const backendId = nodes.backendNodeId?.[nodeIdx];
      const tag = (snapshot.strings[nodes.nodeName[nodeIdx]] ?? "div").toLowerCase();
      const bounds = layout.bounds?.[layoutIdx];

      let centerCoords, offsetCoords, inViewport = false;
      if (bounds && bounds.length >= 4) {
        const x = (bounds[0] - scrollX) / dpr * scaleMultiplier;
        const y = (bounds[1] - scrollY) / dpr * scaleMultiplier;
        const w = bounds[2] / dpr * scaleMultiplier;
        const h = bounds[3] / dpr * scaleMultiplier;

        centerCoords = [Math.round(x + w / 2), Math.round(y + h / 2)];
        offsetCoords = [x, y];
        inViewport = y < vpHeight && y + h > 0 && x < vpWidth && x + w > 0;
      }

      const isPointer = snapshot.strings[layout.styles[layoutIdx][0]] === "pointer";
      nodeMap.set(backendId, {
        cursorPointer: isPointer,
        tag,
        isInViewport: inViewport,
        coords: centerCoords,
        offset: offsetCoords
      });
    });
  });
  return nodeMap;
};
```

### YAML Tree Construction (`_N`)
`_N` iterates through the full AXTree nodes, resolves parent-child relationships, filters out irrelevant elements, and constructs the final YAML output:

```yaml
- body:
  - header:
    - a [ref=142] (x=120,y=45): "Perplexity Home"
    - nav:
      - a [ref=148] (x=450,y=45): "Discover"
      - a [ref=152] (x=530,y=45): "Library"
  - main:
    - input [ref=210] (x=640,y=350): "Ask anything..."
    - button [ref=215] (x=980,y=350): "Search"
```

#### Pruning Rules
1. **Depth Ceiling**: Traversal terminates at `depth > 15` (or user-defined depth).
2. **Overlay Filtering**: Nodes bearing the `pplx-agent-0_0-overlay` prefix are excluded.
3. **Text Truncation**: Text strings in `StaticText` nodes are truncated to 100 characters (`fN = 100`).
4. **Interactive Filtering**: Non-interactive nodes (divs without pointer cursor, click listeners, or input roles) are discarded unless explicitly requested under `filter: "ALL"`.
5. **Viewport Culling**: Nodes located outside the current visual viewport are culled when `filter: "VIEWPORT"` is active.

---

## 4. Information Loss & Failure Modes

| Potential Failure Mode | Root Cause in Perception Pipeline | Comet Mitigation Strategy |
|---|---|---|
| **Stale References (`ref`)** | Single-page apps mutate DOM trees after network requests, invalidating `backendDOMNodeId`. | If `resolveRef` fails in `dP`, error is caught with `lM("No element found with reference")`, prompting agent to re-read. |
| **Canvas / WebGL Loss** | HTML `<canvas>` elements have no child DOM or AX nodes. | Model must fall back to vision/coordinate clicking (`LEFT_CLICK` with `[x,y]`). |
| **Shadow DOM Encapsulation** | Closed Shadow DOM roots hide internal button nodes from standard AX traversal. | CDP `DOM.getDocument` is invoked with `{ depth: 1, pierce: true }`. |
| **Native Select Dropdowns** | Native OS `<select>` popup menus render out-of-process and do not appear in CDP screenshots. | Comet injects `xP()` animation listener to catch `@keyframes _selectOpen` and emits `<system-reminder>` instructing the agent to use `ref` with `form_input`. |
