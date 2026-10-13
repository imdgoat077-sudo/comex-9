# 13 — Capability Matrix across Web Interaction Categories

## 1. Category Evaluation Matrix

The following matrix evaluates Comet Browser's automation architecture across 10 demanding modern web automation scenarios:

| Category | Typical Benchmark Target | Architectural Mechanism | Recovered Capability | Risk / Failure Mode |
|---|---|---|---|---|
| **1. Standard SPAs** | React, Vue, Next.js apps | `Accessibility.getFullAXTree` + `historyApi` detection in `sN` | **Excellent (9/10)**: Rapid settlement, accurate element resolution. | Frame detach during rehydration can trigger retry. |
| **2. Infinite Scrolling** | Twitter, Pinterest, LinkedIn | `iP.ComputerBatch("SCROLL")` + `oN` idle waiting | **Good (8/10)**: Smooth wheel deltas; drifts caught by `_P`. | Virtualized lists may evict nodes, causing stale `ref`. |
| **3. Complex Form Controls** | Multi-selects, native `<select>`, sliders | `xP()` `@keyframes _selectOpen` + `FormInput` macro | **Superior (9/10)**: Native select detection gives explicit guidance to model. | Non-standard custom div dropdowns require coordinate clicking. |
| **4. Rich Text Editors** | Notion, Google Docs, ProseMirror | `uP()` clipboard swapping + `ControlOrMeta+KeyV` | **Superior (9.5/10)**: Bypasses synthetic event listeners reliably. | Sites blocking clipboard API prompt permission dialogs. |
| **5. Canvas / SVG Graphics** | Figma, Miro, Google Maps | Low-level coordinate clicking `[x, y]` | **Moderate (6/10)**: No DOM/AX nodes; model relies purely on vision. | Lack of semantic nodes increases hallucination rate. |
| **6. Browser Games** | Wordle, Chess.com | `ComputerBatch` keyboard press chords | **Good (8/10)**: Fast keystroke dispatch; jitter delay prevents jamming. | High-FPS canvas games cannot be tracked via AXTree. |
| **7. Multi-Tab Workflows** | Flight & hotel comparisons | `CreateSubagent` + `pM` tab grouping | **Superior (9.5/10)**: Background tabs isolated; `isHidden: true` prevents focus theft. | Extreme tab counts (>10) increase memory footprint. |
| **8. Authenticated Sessions** | Gmail, AWS Console, GitHub | Shared browser profile + `browser_get_cookies` | **Superior (10/10)**: Reuses existing logged-in sessions natively. | Security policies may block cookie exports on sensitive sites. |
| **9. Shadow DOM & Iframes** | Stripe checkout, Salesforce, Web Components | `DOM.getDocument` (`pierce: true`) + `SN` iframe traversal | **Excellent (8.5/10)**: Pierces shadow roots cleanly. | Cross-origin iframes without permissions cannot be inspected. |
| **10. Local System Tools** | SQLite, Git CLI, local filesystem | Native C++ MCP Daemon (`components/perplexity/mcp`) | **Unmatched (10/10)**: Native `/bin/zsh` pipe without external bridges. | Requires user authorization modal for untrusted servers. |
