# WebContentsView Covering UI - Reproduction Test

## Setup

1. Start the Python agent service:
```bash
python3 agent_service.py
```

2. In a separate terminal, start the Electron app with logging:
```bash
npm run electron:dev
```

## Reproduction Steps

### Test 1: Normal Manual Navigation (Expected: UI Visible)

1. Launch Comex browser
2. Manually type `https://amazon.in` in address bar
3. Press Enter
4. **Expected Result**: Address bar, tabs, and ChatDrawer remain visible
5. **Check Console**: Look for `[CANVAS]` and `[SYNC]` logs

### Test 2: AI-Driven Navigation (Bug: UI Disappears)

1. Launch Comex browser (should start at launchpad)
2. Open ChatDrawer (Cmd+J or click AI icon)
3. Ensure **Single Agent** mode is selected (not Swarm Mode)
4. Type: "Open Amazon"
5. Press Send
6. **Bug Occurs**: Address bar and ChatDrawer disappear after navigation
7. **Check Console**: Compare `[CANVAS]` and `[SYNC]` logs with Test 1

## What to Look For in Logs

### Expected Log Sequence

```
[CANVAS] sendBounds called
[CANVAS] activeTab.url: https://amazon.in
[CANVAS] isInternalUrl: false
[CANVAS] isChatOpen: true
[CANVAS] Sending bounds to main process: {"x":0,"y":138,"width":XXX,"height":YYY,"isHidden":false}
[MAIN] tabs-set-bounds received: {"x":0,"y":138,"width":XXX,"height":YYY,"isHidden":false}
[SYNC] syncActiveView called. activeTabId: tab-1 isHidden: false
[SYNC] currentBounds: {"x":0,"y":138,"width":XXX,"height":YYY,"isHidden":false}
[SYNC] Active view URL: https://amazon.in
[SYNC] Adding child view to mainWindow.contentView
[SYNC] contentView children before add: X
[SYNC] contentView children after add: Y
[SYNC] Set view visible
[SYNC] Setting view bounds: {"x":0,"y":138,"width":XXX,"height":YYY}
[SYNC] Attempting to reorder base view to front
[SYNC] baseView exists: true/false is same as webview: true/false
```

### Key Questions to Answer

1. **How many children does contentView have?**
   - Before adding WebContentsView?
   - After adding WebContentsView?

2. **Does the baseView reorder attempt succeed?**
   - Is `baseView` found?
   - Is it different from the WebContentsView?
   - Does `addChildView(baseView)` move it to front?

3. **Are bounds correct?**
   - x: 0 (expected)
   - y: 138 (CHROME_TOP_WITH_BOOKMARKS_PX=110 + CONTENT_VIEW_TOP_OFFSET_PX=28)
   - width: window width minus chat drawer if open
   - height: window height minus 110 (chrome)

4. **Is there a difference between manual navigation and AI navigation?**
   - Compare log sequences
   - Check timing of events
   - Look for multiple calls to `syncActiveView()`

## Architectural Diagnosis

### Current Electron Architecture

```
mainWindow.contentView
├── [0] Base WebContents (React renderer) ← invisible layer?
└── [1] WebContentsView (browser tab) ← painted on top?
```

### The Problem

Electron's child views are **always painted above the parent window's base WebContents**. 
Even though we set `y: 138` on the WebContentsView, the **entire view layer** covers the React chrome.

### Possible Root Causes

1. **Base WebContents is not a child view**
   - The React renderer might not be exposed as a reorderable child
   - `mainWindow.contentView.children[0]` might return the WebContentsView itself

2. **Child views always cover parent WebContents**
   - This is fundamental Electron behavior
   - Setting bounds only positions the view, doesn't create a "hole" for React chrome

3. **WebContentsView doesn't respect z-index/layering**
   - Native views don't follow CSS stacking rules
   - They render in a separate compositing layer

### Potential Solutions to Test

#### Solution A: Use BrowserWindow for React Chrome (Not Recommended)
Create a separate frameless BrowserWindow for the chrome, positioned above content.

#### Solution B: Render Chrome in Native View (Complex)
Move navbar/tabs/drawer into native Electron views instead of React.

#### Solution C: Non-Overlapping Layout (Recommended)
Ensure WebContentsView bounds NEVER overlap React chrome:
- React occupies y: 0-138
- WebContentsView occupies y: 138-bottom

But this requires ensuring the WebContentsView truly starts at y=138 and doesn't cover above.

#### Solution D: Disable WebContentsView for browser-use Control
Keep using `<webview>` tag or BrowserView API instead of WebContentsView.

## Next Steps After Diagnosis

1. Run reproduction test and collect logs
2. Confirm which architectural problem is occurring
3. Implement the minimal correct fix
4. Verify all 7 test cases pass
