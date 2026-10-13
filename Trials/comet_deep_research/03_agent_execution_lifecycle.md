# 03 — Agent Execution Lifecycle & State Machine

## 1. Executive Overview

The Comet Browser agent execution lifecycle is an asynchronous, event-driven, hybrid perception-action loop coordinated between three distinct layers:
1. **Frontend Presentation & Stream Layer**: Bundled React Single Page Application (`spa-shell-DjX4AiQc.js`) running inside extension `mjdcklhepheaaemphcopihnmjlmjpcnh`.
2. **Core Agent Automation Runtime**: Background Service Worker / extension process (`background.js` in `npclhjbddhklpbnacpjloidibaggcgon`), hosting the Remote Procedure Call (RPC) Dispatcher (`class dM`), Tab Manager (`class pM`), and Computer-Use Action Engine (`class iP`).
3. **Native Chromium / Blink Engine**: Modified Chromium browser process (`Comet Framework.framework`), exposing native Chrome DevTools Protocol (CDP 1.3), Model Context Protocol (MCP) C++ daemon, and Declarative WebMCP.

This document traces the complete lifecycle from the initial user prompt down to CDP execution, perception polling, subagent spawning, and task completion.

---

## 2. End-to-End Execution Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Frontend SPA (spa-shell)
    participant Core as Comet Core Bridge (mcjlamoh)
    participant Agent as Agent Extension (background.js: dM)
    participant ASI as Perplexity ASI (WebSocket / SSE)
    participant CDP as Chromium DevTools Protocol (1.3)
    participant Tab as Target Web Page (DOM / Blink)

    User->>UI: Enter prompt / goal (e.g., "Find cheapest flight to Tokyo")
    UI->>ASI: POST /api/agent/start or SSE query stream
    ASI-->>UI: Chunk: entropy_request_content / connect_comet_to_asi_content
    UI->>Agent: chrome.runtime.sendMessage({ type: "START_AGENT", payload: {...} })
    
    activate Agent
    Agent->>CDP: chrome.debugger.attach({ tabId })
    Agent->>CDP: Page.enable, DOM.enable, Accessibility.enable
    Agent->>Tab: Inject overlay HUD (content.js: pplx-agent-0_0-overlay)
    Agent->>ASI: ReconnectingAgentSocket (ws://... / wss://...)
    
    loop Agent Perception-Action Cycle
        ASI->>Agent: RPC dispatch: ComputerBatch, ReadPage, FormInput, Navigate
        Agent->>Agent: dM.dispatchRpcRequest(method, payload)
        
        alt Viewport Drift Validation
            Agent->>Tab: eP(tabId) -> query visualViewport
            opt Viewport dimensions changed (_P === true)
                Agent-->>ASI: Abort batch + return fresh screenshot
            end
        end
        
        Agent->>CDP: Dispatch batch actions (Input.dispatchMouseEvent, Input.dispatchKeyEvent)
        CDP->>Tab: Synthesize native hardware events
        
        opt Select Picker Encountered
            Tab-->>CDP: animationstart (_selectOpen)
            Agent->>Agent: Inject <system-reminder> Native select picker opened
        end
        
        Agent->>Tab: Smart wait coordinator (oN / sN) -> wait for DOM / AX idle
        
        Agent->>CDP: Page.captureScreenshot (JPEG q=75)
        Agent->>CDP: Accessibility.getFullAXTree + DOMSnapshot.captureSnapshot
        Agent->>Agent: pN() + _N() -> Generate indexed YAML tree & coordinates
        
        Agent-->>ASI: Return { tab_context, base64_image, message, result }
        ASI-->>UI: Stream step status, actions taken, thought process
        UI->>User: Render real-time progress & glowing viewport border
    end
    
    ASI->>Agent: RPC: TaskCompleted or User abort
    Agent->>CDP: chrome.debugger.detach({ tabId })
    Agent->>Tab: Remove overlay HUD
    Agent-->>UI: Task Finalized
    deactivate Agent
```

---

## 3. Finite State Machine (FSM)

The agent lifecycle is formally governed by a 7-state deterministic state machine:

```mermaid
stateDiagram-v2
    [*] --> UNINITIALIZED
    
    UNINITIALIZED --> INITIALIZING : START_AGENT / connectAsi
    INITIALIZING --> RUNNING : Debugger Attached & ASI Connected
    INITIALIZING --> FAILED : Debugger Attach Failure / Invalid URL
    
    state RUNNING {
        [*] --> RECEIVING_RPC
        RECEIVING_RPC --> EXECUTING_ACTIONS : ComputerBatch / Navigate / FormInput
        EXECUTING_ACTIONS --> SMART_WAITING : Actions dispatched
        SMART_WAITING --> PERCEIVING : Frame/AX idle reached
        PERCEIVING --> EMITTING_RESULT : Screenshot & AXTree compiled
        EMITTING_RESULT --> RECEIVING_RPC : Awaiting next model turn
    }
    
    RUNNING --> PAUSED : BROWSER_TASK_PAUSE_RESUME (Stop Button)
    PAUSED --> RUNNING : BROWSER_TASK_PAUSE_RESUME (Resume)
    
    RUNNING --> WAITING_CONFIRMATION : Sensitive Action / Financial Checkout
    WAITING_CONFIRMATION --> RUNNING : User Approves (ALLOW_ONCE / ALWAYS_ALLOW)
    WAITING_CONFIRMATION --> FAILED : User Rejects (SKIP / ABORT)
    
    RUNNING --> SUBAGENT_DELEGATING : CreateSubagent invoked
    SUBAGENT_DELEGATING --> RUNNING : Subagent spawned in hidden background tab
    
    RUNNING --> ERROR_RECOVERING : "Debugger is not attached" / Timeout
    ERROR_RECOVERING --> RUNNING : Reattachment / Reload succeeded
    ERROR_RECOVERING --> FAILED : Retry budget exhausted (>45s)
    
    RUNNING --> TERMINATING : Goal Reached / Task Finished / User Stop
    PAUSED --> TERMINATING : User Abort
    
    TERMINATING --> [*] : Clean detachment & Overlay removed
    FAILED --> [*] : Error logged to Sentry / UI notification
```

---

## 4. Lifecycle Stage Deep Dive

### Stage 1: Ingestion and Task Provisioning (`START_AGENT`)
The task initiation originates in `spa-shell-DjX4AiQc.js` through `StreamMiddlewares`. When the Perplexity backend emits an `entropy_request_content` payload, the middleware extracts task parameters and dispatches a Chrome runtime message:

```typescript
// Incoming Perplexity SSE chunk handling
if (chunk.entropy_request_content) {
  const tool = chunk.entropy_request_content;
  tool.tasks.forEach(task => {
    agentExtension.sendMessage({
      action: "startAgentFromPerplexity",
      type: "START_AGENT",
      extra_headers: tool.extra_headers,
      base_url: tool.base_url,
      entryId: entry_uuid,
      task_id: task.uuid,
      use_current_page: task.use_current_page && false,
      capture_screenshot: !task.use_current_page && !task.tab_id,
      thread_url_slug: slug,
      ...task
    });
  });
}
```

### Stage 2: Debugger Attachment & Target Acquisition
In `background.js`, `START_AGENT` triggers the initialization of `class dM`:
1. **Tab Verification**: Validates `tab_id`. Calls `maybeFocusTab(tab)` unless `is_subagent === true`.
2. **Internal URL Gate**: Evaluates `Nj.isInternalPage(url)`. Navigation to `chrome://`, `chrome-extension://`, or `devtools://` is rejected with `ToolError`.
3. **Organizational Domain Whitelist/Blacklist**: Evaluates organizational policies defined in `managed_schema.json` (`BlockedDomains`).
4. **CDP Attachment (`IA(tabId)`)**: Calls `chrome.debugger.attach({ tabId }, "1.3")`.
   - Enables domains: `Page.enable`, `DOM.enable`, `Accessibility.enable`, `Input.setInterceptDrags({ enabled: true })`.
5. **HUD Overlay Injection**: Sends `INJECT_OVERLAY` to `content.js` to establish the floating bounding frame and pause button.

### Stage 3: ASI WebSocket Connection & RPC Dispatch
The agent connects to the Agent Streaming Interface (ASI) using `ReconnectingAgentSocket`:
- Frames are serialized as JSON-RPC 2.0.
- When an incoming method arrives, `dM.dispatchRpcRequest` wraps execution inside a 45-second execution deadline (`uM = 45000`).
- The method name is matched against `this.deps.browserTools[method]` (e.g., `ComputerBatch`, `Navigate`, `ReadPage`, `FormInput`, `GetPageText`, `TabsCreate`, or `CreateSubagent`).

### Stage 4: Execution, Viewport Validation & Perception
1. Before any click or scroll action, `_P(lastViewport, currentViewport)` checks for resize or layout shift. If detected, the actions are aborted immediately, returning a fresh screenshot to prevent misclicks.
2. Actions are executed sequentially with a randomized jitter delay of $100	ext{--}200	ext{ ms}$ (`Math.floor(Math.random() * 101) + 100`).
3. Upon completing the batch, the Smart Wait Coordinator (`oN` / `sN`) monitors CDP events (`Accessibility.loadComplete`, `Accessibility.nodesUpdated`) until network and layout quiescence is reached.
4. `Page.captureScreenshot` captures a downscaled surface JPEG (quality 75). Concurrently, `gN` extracts the full accessibility tree and computed cursor styles, compiling them into a compact, token-efficient YAML document indexed by `ref` IDs.

### Stage 5: Termination & Teardown
When the goal is met or the task is aborted:
- `chrome.debugger.detach({ tabId })` is called gracefully.
- The content overlay is dismissed.
- The tab group metadata is updated via `class pM`.
- If the thread is moved to the native sidecar, `MOVE_THREAD_TO_SIDECAR` transfers the session context to `chrome.perplexity.sidecar.open()`.
