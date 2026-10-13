# 09 — Worker Orchestration & Multi-Tab Isolation

## 1. Subagent Orchestration Architecture

Complex research and browsing workflows (e.g. comparing flight prices across 5 airline websites) require parallel execution. Comet supports autonomous subagent delegation via the `CreateSubagent` tool method.

Subagents are isolated worker instances created in the background without stealing the user's primary browsing focus:

```
                            +-----------------------------+
                            |      Primary Agent Task     |
                            |  (Tab 101 - Google Flights) |
                            +--------------+--------------+
                                           |
                                           | CreateSubagent({ prompt, start_url })
                                           v
                            +-----------------------------+
                            |   dM.CreateSubagent()       |
                            |   - is_subagent: true       |
                            |   - isHidden: true          |
                            |   - windowId: senderWindow  |
                            +--------------+--------------+
                                           |
                    +----------------------+----------------------+
                    |                                             |
                    v                                             v
     +------------------------------+              +------------------------------+
     |   Subagent 1: United Airlines|              |   Subagent 2: Delta Airlines |
     |   - Tab 102 (Hidden TabGroup)|              |   - Tab 103 (Hidden TabGroup)|
     |   - Dedicated CDP Debugger   |              |   - Dedicated CDP Debugger   |
     |   - Independent Action Engine|              |   - Independent Action Engine|
     +------------------------------+              +------------------------------+
```

---

## 2. Tab Management & Tab Grouping (`class pM`)

Tab lifecycles and window assignments are managed by `pM` (`deps.agentTabsManager`):
- **Tab Grouping**: If task contains $\ge 2$ tabs (`minTabsSizeToGroup = 2`), Comet automatically organizes them into a Chrome Tab Group named after the query.
- **Hidden Background Execution**: When `initialPayload.is_subagent === true`, `pM.isHidden` is set to `true`. Calls to `maybeFocusTab` do not steal window focus.
- **Modal Dialog Suppression**: Listens for `Page.javascriptDialogOpening` and automatically handles alerts/prompts to prevent worker freezing.

### Extracted Implementation Source:
```javascript
class pM {
  deps;
  tabRegistry = new Set();
  tabGroupId;
  windowId;
  minTabsSizeToGroup = 2;
  isHidden = false;
  groupTitle;

  constructor(deps) {
    this.deps = deps;
    let query = deps.initialPayload?.query ?? "";
    let words = query.split(" ").filter(w => w.length > 0);
    this.groupTitle = words.length > 2 ? `${words.slice(0, 2).join(" ")}...` : query;
    
    // Flag subagents as hidden background tabs
    if (this.deps.initialPayload?.is_subagent) {
      this.isHidden = true;
    }
    this.windowId = this.deps.taskContextPayload?.windowId ?? chrome.windows.WINDOW_ID_CURRENT;
  }

  setupListeners() {
    chrome.debugger.onEvent.addListener((source, method, params) => {
      // Auto-dismiss unexpected JavaScript alert/confirm dialogs
      if (source.tabId && this.tabRegistry.has(source.tabId) && method === "Page.javascriptDialogOpening") {
        chrome.debugger.sendCommand(source, "Page.handleJavaScriptDialog", {
          accept: true,
          promptText: ""
        }).catch(() => {});
      }
    });
  }

  async maybeFocusTab(tab) {
    if (this.isHidden) {
      return; // Do not focus subagent tabs!
    }
    await chrome.tabs.update(tab.id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  }

  async addTabToTask(tabId) {
    this.tabRegistry.add(tabId);
    if (this.tabRegistry.size >= this.minTabsSizeToGroup) {
      await this.ensureTabGroup();
    }
  }
}
```

---

## 3. Subagent Creation Protocol (`CreateSubagent`)

When the model issues a `CreateSubagent` tool call:
```json
{
  "method": "CreateSubagent",
  "request": "{\"prompt\":\"Check flight prices on kayak.com\",\"start_url\":\"https://www.kayak.com\",\"task_uuid\":\"f84a-...\"}"
}
```

In `class dM`:
```javascript
async CreateSubagent(params) {
  if (!this.deps.initialPayload) throw Error("Initial payload is not set");
  let extraHeaders = {};
  try {
    extraHeaders = JSON.parse(params.extra_headers ?? "{}");
  } catch {
    return { error: "Invalid request parameters." };
  }

  try {
    await kP({
      query: params.prompt || "",
      taskId: params.task_uuid || "",
      start_url: params.start_url || "",
      source: "create_subagent_tool",
      extra_headers: extraHeaders,
      entryId: this.deps.initialPayload.entryId,
      base_url: this.deps.initialPayload.base_url,
      senderTabId: this.deps.initialPayload.senderTabId,
      senderWindowId: this.deps.initialPayload.senderWindowId,
      is_subagent: true // Launches in hidden background mode
    }, {
      windowId: this.deps.initialPayload.senderWindowId ?? chrome.windows.WINDOW_ID_CURRENT
    });
  } catch (err) {
    return { error: `Failed to start subagent: ${err.message}` };
  }

  return { tab_context: undefined };
}
```

---

## 4. Multi-Worker Concurrency Guarantees

| Boundary Dimension | Primary Agent | Background Subagents |
|---|---|---|
| **Tab Grouping** | Visible Tab Group with title | Hidden Tab Group or distinct sub-group |
| **Window Focus** | Actively focused on turn start | Background tab; `active: false`, `focused: false` |
| **CDP Debugger** | Distinct debuggee session `{ tabId: 101 }` | Dedicated debuggee session `{ tabId: 102 }` |
| **Overlay HUD** | Injected glowing border + Pause HUD | No overlay injected (avoids flickering foreground display) |
| **Storage / Cookies** | Shares Chrome browser profile | Shares Chrome browser profile (authenticated state preserved) |
