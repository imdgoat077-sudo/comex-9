# 11 — Streaming Infrastructure, Agent Socket & UI HUD

## 1. Streaming Architecture Overview

Comet decouples model reasoning from client action execution via a bidirectional streaming pipeline:
1. **Model Generation Stream**: Server-Sent Events (SSE) or WebSocket packets streaming from Perplexity servers to the client React SPA shell (`spa-shell-DjX4AiQc.js`).
2. **Stream Interception Middleware (`StreamMiddlewares`)**: Intercepts tool calls on the client side before they reach UI renderers.
3. **Agent Streaming Interface (ASI)**: Direct, low-latency WebSocket connection (`ReconnectingAgentSocket`) between the background extension runtime and the agent orchestration backend.
4. **Live Visual In-Page HUD**: An injected shadow-DOM overlay (`content.js`) providing glowing boundaries, click feedback, and stop controls.

```
+-------------------------------------------------------------------------------+
|                             Perplexity Backend Cloud                          |
+-------------------+---------------------------------------+-------------------+
                    | SSE Stream                            | ASI WebSocket
                    v                                       v
+------------------------------------+       +------------------------------------+
|  Bundled SPA Shell (spa-shell.js)  |       | Background Extension Runtime (dM)  |
|  - StreamMiddlewares               |       | - ReconnectingAgentSocket          |
|  - entropy_request_content         |       | - Action Dispatcher                |
|  - connect_comet_to_asi_content    +------>| - CDP Client                       |
|  - MOVE_THREAD_TO_SIDECAR          |       +-----------------+------------------+
+------------------------------------+                         |
                                                               | chrome.tabs.sendMessage
                                                               v
                                             +------------------------------------+
                                             | In-Page HUD (content.js)           |
                                             | - #pplx-agent-0_0-overlay          |
                                             | - Stop / Pause Button              |
                                             | - Click Ripple Animations          |
                                             +------------------------------------+
```

---

## 2. Stream Interception Middlewares (`StreamMiddlewares`)

Extracted from `spa-shell-DjX4AiQc.js`:
The React UI pipeline uses functional middlewares to intercept tool invocations directly from incoming text streams:

```javascript
// Intercepts browser tools embedded in SSE model responses
var executeBrowserToolMiddleware = (tool, backendUuid, onComplete, contextUuid) => {
  // 1. Task submission from search stream
  if (tool.entropy_request_content) {
    let req = tool.entropy_request_content;
    req.tasks.forEach(task => {
      agentExtension.submitTask({
        action: "startAgentFromPerplexity",
        type: "START_AGENT",
        extra_headers: req.extra_headers,
        base_url: req.base_url,
        entryId: backendUuid,
        ...task
      });
    });
  }
  // 2. Direct connection to Agent Streaming Interface (ASI)
  else if (tool.connect_comet_to_asi_content) {
    let asi = tool.connect_comet_to_asi_content;
    agentExtension.connectAsi({
      ws_url: asi.ws_url,
      request_id: asi.request_id,
      entry_uuid: backendUuid,
      context_uuid: contextUuid
    });
  }
  // 3. Export browser cookies for authenticated sessions
  else if (tool.browser_get_cookies_content) {
    let cookies = await agentExtension.getCookies();
    await sendToolResponse(cookies, tool.uuid);
  }
  // 4. Visible tab screenshot capture with AWS S3 upload
  else if (tool.browser_get_visible_tab_screenshot_content) {
    let shot = await agentExtension.captureVisibleTab();
    let s3Res = await fetch(tool.s3_bucket_url, { method: "POST", body: shot });
    let { secure_url } = await s3Res.json();
    await sendToolResponse({ screenshot_url: secure_url }, tool.uuid);
  }
};
```

---

## 3. Transition to Floating Native Sidecar (`MOVE_THREAD_TO_SIDECAR`)

Comet allows full-tab browsing sessions to seamlessly collapse into a native macOS floating sidebar panel:
```javascript
case "MOVE_THREAD_TO_SIDECAR":
  // Transfers task context from active full tab to sidecar state store
  let sidecarUrl = `/sidecar/search/${payload.thread_url_slug ?? payload.entry_id}`;
  payload.task_tab_ids.forEach(tabId => {
    store.getState().actions.setSidecarUrlById(tabId, sidecarUrl);
  });
  // Dispatches native window frame repositioning via C++ API
  await chrome.perplexity.sidecar.open({
    active_task_uuid: payload.active_task_uuid,
    animate: payload.animate ?? true,
    takeFocus: payload.takeFocus ?? false
  });
  break;
```

---

## 4. In-Page HUD & Visual Overlay (`content.js`)

When an agent takes control of a tab, `content.js` injects an unmistakable visual indicator:
1. **Glowing Boundary**: A rotating conic-gradient border (`#pplx-agent-0_0-overlay`) rendered at the perimeter of the viewport:
   ```css
   #pplx-agent-0_0-overlay {
     position: fixed;
     inset: 0;
     border: 4px solid transparent;
     border-image: conic-gradient(from 180deg at 50% 50%, #20b8cd, #8f44fd, #f25555, #20b8cd) 1;
     pointer-events: none;
     z-index: 2147483647;
   }
   ```
2. **Stop Button**: Floating pill button (`#pplx-agent-0_0-overlay-stop-button`) in the upper-right corner allowing instant human takeover.
3. **Ripple Click Feedback**: Listens for runtime message `OVERLAY_CLICK_FEEDBACK` and renders expanding radial ripples at the exact `(x, y)` coordinate where the agent clicked.
