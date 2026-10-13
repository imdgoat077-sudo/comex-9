# Comet agent: tool surface and execution model (client side)

Same target, method and labels as `README.md`: Comet agent extension 0.0.231, read-only, paraphrased, no code copied.
[observed] = read in the client code. [inferred] = follows from it. [unknown] = needs the server.

## 1. The whole tool set is small: six tools plus the spawn call

| Tool | What it takes | What comes back |
|---|---|---|
| `ComputerBatch` | a list of actions (below), `tab_id` | tab context, per-action messages, final screenshot, optional click screenshot |
| `FormInput` | element `ref`, `value` | tab context, message, screenshot |
| `GetPageText` | `tab_id` | tab context, page text as markdown (PDF supported). No screenshot |
| `Navigate` | `url`, or `back` / `forward` | tab context, message, screenshot |
| `ReadPage` | `filter` (interactive, all, viewport), optional `ref_id`, `depth` | tab context, accessibility tree as YAML |
| `TabsCreate` | optional `url` | tab context, new tab id, screenshot |
| `CreateSubagent` | `prompt`, `start_url`, `task_uuid` | empty (fire-and-forget) |

[observed] Actions inside `ComputerBatch`: screenshot, wait (1 to 30 s), left/right/double/triple click (by coordinate or by
element `ref`), type, key (chords such as `a+b`), scroll (coordinate plus direction/amount/"max"), left_click_drag
(start and end coordinate), scroll_to (by `ref`).

[observed] **Every browser tool except `GetPageText` and `ReadPage` returns a screenshot, and every tool returns the list of
the task's tabs** (id, title, URL) and which one is current. The model never needs a separate "look" call after acting.

## 2. Execution rules worth learning from

1. **Act and observe in one call.** Because the result carries the resulting screenshot and tab list, one model turn
   covers "do this, and show me what happened". [observed]
2. **Batch refusal on stale coordinates.** If the viewport changed since the last screenshot and the batch contains a
   click, scroll or drag, the whole batch is refused (nothing runs). The reply carries a fresh screenshot and an explicit
   message saying the old coordinates are no longer valid. [observed] Comex has the same gate.
3. **Failures keep partial progress.** An error inside a batch reports the results of the actions that succeeded, the name and
   index of the one that failed, and the error text. [observed] Comex's `browser_sequence` does this too.
4. **Click proof.** After the last click of a batch the client takes a quick screenshot with a filled circle drawn at the click
   point (radius scales with image width), returns it as a separate image, and drops the final screenshot if it was taken
   within 1 s of that one. The model can see where its click landed. [observed]
5. **Small human-like gaps.** Between actions in a batch: a base delay of 100 ms plus 0 to 100 ms random. Not applied after
   the last action. [observed]
6. **Page-settle waiting is event-driven and bounded.** After actions the client waits until network and accessibility
   activity goes quiet (500 ms idle), counting only meaningful requests (fetch, XHR, WebSocket, EventSource, document
   loads; low-priority ones ignored; analytics and CSS ignored) and accessibility-tree update events (250 to 350 ms debounce).
   Hard cap: 2.5 s after batch actions, 5 s after navigation or new tab. Some sites (Gmail, Amazon) get special handling. [observed]
7. **Screenshots:** JPEG quality 75 from the browser, resized in-page, delivered as PNG. Size budget 1.15 million pixels and
   at most 1568 px on the long side. The page's real layout viewport is measured by a hidden probe element so scrollbar
   width does not skew coordinates. [observed]
8. **Accessibility tree in screenshot coordinates.** `ReadPage` scales positions by the same factor as the screenshot, so a
   position read from the tree can be clicked without conversion. Default scope is the visible viewport; a subtree can be
   requested by `ref_id` with a depth limit. [observed]
9. **Native dropdowns:** after a click, if a native select popup opened, the reply appends a short reminder telling the
   model the screenshot may not show it and to use `FormInput` with the element's `ref`. Checkbox, radio, select, date,
   time, colour and range inputs are set through the page, not typed. [observed]
10. **Guards the model can read.** Internal browser pages and blocked URLs return plain-language errors that tell the model
    what to do ("navigate to another url or stop the task"). [observed]
11. **Scrolling:** a scroll is sent as a real wheel event; a temporary listener checks it actually scrolled something, and if
    not, it retries with a second wheel event. "Max" scrolls up to 99 viewports. [observed]
12. **Timeouts and recovery:** each server request has a 45 s ceiling and returns a timeout error instead of hanging. Debugger
    detached → reattach and retry once. Debugger command timed out → reload the tab and retry once. JavaScript dialogs are
    accepted automatically. [observed]
13. **Typing:** simple text is inserted directly; if that fails, the client saves the clipboard, pastes the text, and
    restores the clipboard. [observed]

## 3. What the client does NOT contain
- Any planning, task splitting or answer-merging logic. [observed]
- A way to wait for or collect a sub-agent's result. [observed, bounded by the names searched]
- The prompts that tell the model when to batch, when to read the page, or when to spawn. [unknown, server side]
