# 08 — Error Recovery, Self-Healing RPC & Cancellation

## 1. Resilient Architecture Principles

Browser automation in production environments faces frequent non-deterministic disruptions:
- Pages crash or reload unexpectedly.
- Heavy JavaScript execution stalls the main thread, causing CDP commands to time out.
- Users click away, close tabs, or switch windows.
- Chrome's debugger automatically detaches when DevTools is opened or background workers sleep.

Comet implements an autonomous **Self-Healing RPC Dispatcher** (`class dM`) designed to recover transparently from debugger disconnections and timeouts without failing the user task.

---

## 2. The Self-Healing RPC Dispatcher (`class dM`)

```mermaid
flowchart TD
    IncomingRequest[Incoming RPC: dM.dispatchRpcRequest] --> VerifyTab[Verify Tab Existence & Permissions]
    VerifyTab --> WrapTimeout[Wrap in uM = 45000ms Timeout Promise]
    WrapTimeout --> Execute[Execute Action: browserTools[method]]
    
    Execute -- Success --> FormatResponse[Format Result & Size MB]
    FormatResponse --> ReturnPayload[Return request_id + response JSON]
    
    Execute -- Error Caught --> MatchError{Analyze Error Type}
    
    MatchError -- "Debugger is not attached" / "Detached while handling" --> LogDetached[Log warning & Reattach IA tabId]
    LogDetached --> RetryAction1[Retry execution: c true]
    RetryAction1 --> Execute
    
    MatchError -- "Debugger command timed out" --> LogTimeout[Log warning & Reload tab: chrome.tabs.reload]
    LogTimeout --> ReattachAfterReload[Reattach: IA tabId]
    ReattachAfterReload --> RetryAction2[Retry execution: c true]
    RetryAction2 --> Execute
    
    MatchError -- "ToolError (lM)" --> ReturnToolError[Return cM + error.message]
    MatchError -- Other Exception --> ReturnClientError[Return rP + error.message]
```

### Extracted Implementation Source:
```javascript
var uM = 45000; // 45-second execution deadline per RPC method
var cM = "Failed to execute action";
var rP = "Unexpected client error";

class lM extends Error {
  constructor(message, options) {
    super(message, options);
    this.name = "ToolError";
  }
}

class dM {
  deps;
  constructor(deps) { this.deps = deps; }

  async dispatchRpcRequest({ request_id, method, request }) {
    if (!request_id || !request || !method) throw Error("Invalid RPC request parameters");

    let startTime = performance.now();
    let tabId = undefined;
    let didTimeout = false;

    // Retryable execution closure
    const executeClosure = async (isRetry = false) => {
      try {
        let params = JSON.parse(request);
        if (typeof params === "object" && params && "tab_id" in params) {
          tabId = params.tab_id;
          let tab = await getTab(tabId);
          if (!tab?.id) throw new lM("No tab with provided ID");

          await this.deps.agentTabsManager.maybeFocusTab(tab);
          let url = tab.pendingUrl ?? tab.url ?? "";
          
          if (method !== "Navigate" && isInternalPage(url)) {
            throw new lM("This tab is an internal page, you cannot manipulate it.");
          }
          if (method !== "Navigate" && (await isUrlBlocked(url))) {
            throw new lM("Url on this tab is restricted by user or system.");
          }
        }

        return method === "CreateSubagent"
          ? await this.CreateSubagent(params)
          : await this.deps.browserTools[method](params);

      } catch (err) {
        try {
          let tab = tabId && (await getTab(tabId));
          // If already retried, aborted, or tab missing, bail out
          if (!tab || isRetry || didTimeout || this.deps.abortController?.signal.aborted) {
            return this.deps.browserTools.handleError(err, tabId);
          }

          // Case 1: Debugger detach recovery
          if (err instanceof Error && [
            "Debugger is not attached to the tab with id",
            "Detached while handling command"
          ].some(msg => err.message.includes(msg))) {
            this.deps.logger.warn("[dispatch rpc] Trying to retry after debugger error", err, { tabId });
            await IA(tabId); // Reattach debugger
            return executeClosure(true); // Retry once
          }

          // Case 2: Debugger command timeout recovery
          if (err instanceof sj && err.message.startsWith("Debugger command timed out:")) {
            this.deps.logger.warn("[dispatch rpc] Trying to retry after debugger timeout", err, { tabId });
            await chrome.tabs.reload(tabId); // Hard reload stalled tab
            await IA(tabId);                 // Reattach debugger
            return executeClosure(true); // Retry once
          }
        } catch (retryErr) {
          this.deps.logger.warn("[dispatch rpc] Unsuccessful retry on action", retryErr, { tabId });
        }
        return this.deps.browserTools.handleError(err, tabId);
      }
    };

    let result;
    try {
      result = await withTimeout(uM)(executeClosure)();
    } catch {
      didTimeout = true;
      result = await this.deps.browserTools.handleError(new lM(`Request timed out after ${uM / 1000} seconds`), tabId);
    }

    return {
      request_id,
      response: JSON.stringify(result)
    };
  }
}
```

---

## 3. Failure Classification Matrix

| Error Class | Identifier / Matcher | Recovery Action | Emitted Model Response |
|---|---|---|---|
| **Debugger Detached** | `"Debugger is not attached"`, `"Detached while handling command"` | Calls `IA(tabId)` to reattach CDP session 1.3; replays failed command. | Transparent retry; zero error surfaced if recovery succeeds. |
| **Command Timeout** | `sj` error starting with `"Debugger command timed out:"` | Calls `chrome.tabs.reload(tabId)`, waits for load, reattaches `IA(tabId)`, replays command. | Transparent retry; if second attempt fails, surfaces `ToolError`. |
| **Viewport Drift** | `_P(lastViewport, currentViewport) === true` | Aborts remaining batch actions immediately; captures fresh viewport screenshot. | `"Actions were not executed as viewport dimensions have been changed. Previous screenshots and coordinates are no longer valid. Use the new screenshot provided to continue."` |
| **Stale Element Ref** | Node lookup in `dP` fails (`DOM.resolveNode`) | Catches exception and formats user-friendly error message. | `"No element found with reference: '...'. The element may have been removed from the page."` |
| **Restricted Domain** | `isUrlBlocked(url)` or `isInternalPage(url)` | Rejects before CDP dispatch. | `"This url is restricted by user or system. You cannot navigate to this url."` |
| **Global 45s Timeout** | `withTimeout(45000)` rejects | Aborts method execution; logs timeout metric. | `"Failed to execute action: Request timed out after 45 seconds"` |

---

## 4. User Cancellation & Pause Architecture

When the user clicks the floating stop button (`#pplx-agent-0_0-overlay-stop-button`) or navigates away in the UI:
1. `content.js` dispatches runtime message: `{ type: "BROWSER_TASK_PAUSE_RESUME", payload: { is_paused: true } }`.
2. `background.js` triggers `this.deps.abortController.abort()`.
3. In `iP.ComputerBatch`:
   ```javascript
   for (let [idx, action] of actions.entries()) {
     if (this.deps.abortController?.signal.aborted) {
       break; // Immediately halts loop
     }
     // ...
   }
   ```
4. The debugger session is not abruptly terminated, preserving the tab state for inspection or resumption.
