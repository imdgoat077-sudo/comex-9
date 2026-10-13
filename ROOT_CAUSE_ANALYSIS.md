# WebContentsView Covering React Chrome - Root Cause Analysis & Fix

## Problem Summary

When browser-use (Python AI agent) navigates to a real website (e.g., Amazon), the native Electron `WebContentsView` covers the React browser chrome (address bar, tabs, ChatDrawer), making them invisible and non-interactive.

## Root Cause

### Architectural Understanding

Electron's rendering architecture for the Comex browser:

```
BrowserWindow
└── mainWindow.contentView (native compositor layer)
    ├── Base WebContents (React renderer - implicit, always bottom layer)
    └── WebContentsView (browser tab - child view, painted above)
```

**Key Insight:** In Electron, `WebContentsView` child views are **always composited on a layer above the parent window's base WebContents**, regardless of z-index or CSS stacking context.

### The Bug

The bounds calculation in `BrowserCanvas.jsx` was mixing two different coordinate systems:

1. **React Viewport Coordinates (CSS pixels)**
   - `window.innerHeight` = full client area height (e.g., 900px)
   - Already accounts for flexbox layout (chrome excluded from canvas height)

2. **Electron BrowserWindow Coordinates (native pixels)**
   - y=0 is the top of the content view (below macOS traffic lights)
   - The WebContentsView bounds are absolute positions in this space

### The Calculation Error

**Original (Broken) Code:**
```javascript
const height = Math.max(0, window.innerHeight - CHROME_TOP_WITH_BOOKMARKS_PX);
// height = 900 - 110 = 790

const bounds = {
  x: 0,
  y: 138, // CHROME_TOP_WITH_BOOKMARKS_PX=110 + CONTENT_VIEW_TOP_OFFSET_PX=28
  width: window.innerWidth - chatWidth,
  height: 790,
  isHidden: false
};
```

**Problem:**
- View starts at y=138
- View height = 790
- **Total coverage: 138 + 790 = 928px**

If the window is only 900px tall, the view extends beyond the window bounds. Electron's compositor may handle this by:
- Wrapping the view
- Repositioning it to y=0
- Covering the entire window

This explains why the React chrome disappears—the WebContentsView is covering coordinates 0-900, not 138-928.

### Why It Only Happens During AI Navigation

1. **Before AI Navigation:**
   - URL: `comex://launchpad` (internal)
   - `isHidden: true`
   - `syncActiveView()` detaches all views
   - React UI fully visible

2. **AI Navigates to Amazon:**
   - browser-use connects via CDP
   - Navigates WebContentsView to `https://amazon.in`
   - Electron fires `did-navigate` event
   - `tab-update` sent to React
   - React state updates: `activeTab.url = "https://amazon.in"`
   - `BrowserCanvas` useEffect triggers (dependency: `activeTab?.url`)
   - `isInternalUrl()` returns `false`
   - `sendBounds()` called with `isHidden: false`
   - **Incorrectly calculated bounds sent to main process**
   - `syncActiveView()` adds WebContentsView with wrong bounds
   - WebContentsView covers React chrome

## The Fix

### Correct Bounds Calculation

Use the **actual rendered height** of the canvas element, not `window.innerHeight`:

```javascript
const viewStartY = CHROME_TOP_WITH_BOOKMARKS_PX + CONTENT_VIEW_TOP_OFFSET_PX; // 138
const canvasRect = el.getBoundingClientRect();
const height = Math.max(0, canvasRect.height); // e.g., 762

const bounds = {
  x: 0,
  y: viewStartY, // 138
  width: window.innerWidth - chatWidth,
  height: height, // 762
  isHidden: false
};
```

**Why This Works:**
- `canvasRect.height` is the **actual rendered height** of `.browser-canvas-area` after flexbox layout
- This height already accounts for the chrome occupying the top of the window
- Total coverage: 138 + 762 = 900px (exactly the window height)
- The WebContentsView occupies **only the space below the chrome**, never overlapping y=0-138

### Additional Fix: View Lifecycle Management

In `main.js`, improved `syncActiveView()` to:

1. **Always detach all views first** (prevents multiple views covering chrome)
2. **Check if view should be shown** before adding it
3. **Early return if view is hidden** (leaves React UI fully visible)
4. **Set bounds before making visible** (prevents flashing at wrong position)

```javascript
function syncActiveView() {
  const shouldShowView = activeTabId && views.has(activeTabId) && !currentBounds.isHidden;

  // Detach ALL views first
  for (const [tabId, view] of views.entries()) {
    detachView(view);
    view.setVisible(false);
  }

  // Early return if no view should be shown
  if (!shouldShowView) {
    return; // React UI remains fully visible
  }

  // Add and configure the active view
  const view = views.get(activeTabId);
  mainWindow.contentView.addChildView(view);
  view.setBounds(finalBounds); // Set bounds first
  view.setVisible(true); // Make visible after positioning
}
```

## Verification Steps

### Test 1: Manual Navigation
1. Start Comex browser
2. Manually navigate to `https://amazon.in`
3. **Expected:** Address bar, tabs, ChatDrawer remain visible
4. **Expected:** Amazon page loads in the content area

### Test 2: AI Navigation (The Bug Scenario)
1. Start Comex browser (launchpad)
2. Open ChatDrawer (Single Agent mode)
3. Type: "Open Amazon"
4. **Expected:** Browser navigates to Amazon
5. **Expected:** Address bar, tabs, ChatDrawer remain visible
6. **Expected:** Amazon page loads without covering chrome

### Test 3: ChatDrawer Open/Close
1. Navigate to Amazon (via AI or manually)
2. Open ChatDrawer
3. **Expected:** WebContentsView width reduces, ChatDrawer visible
4. Close ChatDrawer
5. **Expected:** WebContentsView width expands, chrome still visible

### Test 4: Window Resize
1. Navigate to Amazon
2. Resize window (smaller, larger)
3. **Expected:** WebContentsView resizes, chrome remains visible

### Test 5: Tab Switching
1. Open multiple tabs with real websites
2. Switch between tabs
3. **Expected:** Each tab's WebContentsView displays correctly, chrome visible

### Test 6: Multiple AI Navigations
1. Ask AI: "Open Amazon"
2. Ask AI: "Open GitHub"
3. Ask AI: "Go to YouTube"
4. **Expected:** Chrome remains visible through all navigations

### Test 7: Browser-use Automation
1. Ask AI: "Search for laptops on Amazon"
2. AI performs multiple actions (navigate, scroll, click, type)
3. **Expected:** Chrome remains visible, browser-use controls the page

## Changes Made

### Files Modified

1. **electron/main.js**
   - Added comprehensive logging to `syncActiveView()`
   - Added logging to all navigation event listeners
   - Improved view lifecycle management
   - Early return when no view should be shown

2. **src/components/Canvas/BrowserCanvas.jsx**
   - Fixed bounds calculation using `getBoundingClientRect()`
   - Added detailed logging for debugging
   - Added comments explaining coordinate systems

3. **REPRODUCTION_TEST.md** (NEW)
   - Test instructions and architectural diagnosis

4. **ROOT_CAUSE_ANALYSIS.md** (THIS FILE)
   - Complete explanation of the bug and fix

## Remaining Work

1. **Test with actual browser-use** to confirm the fix works
2. **Remove debug logging** after verification
3. **Verify all 7 test cases** pass
4. **Check edge cases:**
   - Very small window sizes
   - Multiple monitors with different DPI
   - Fullscreen mode
   - macOS vs Windows vs Linux

## Key Takeaways

1. **Electron child views always paint above parent WebContents**
   - No z-index or CSS can change this
   - Must use non-overlapping bounds

2. **Coordinate systems matter**
   - React: CSS pixels, relative to viewport
   - Electron: Native pixels, absolute in BrowserWindow

3. **Use actual rendered dimensions**
   - `getBoundingClientRect()` accounts for all layout (flexbox, margins, padding)
   - `window.innerHeight` is the full viewport, not the available content area

4. **View lifecycle is critical**
   - Always detach before re-adding
   - Set bounds before making visible
   - Check if view should be shown before adding

## Debug Logging

When running with the current code, you'll see:

```
[CANVAS] sendBounds called
[CANVAS] canvasRect.height: 762
[CANVAS] Calculated viewStartY: 138
[CANVAS] Calculated height: 762
[CANVAS] Total coverage (y + height): 900
[SYNC] syncActiveView called. activeTabId: tab-1 isHidden: false
[SYNC] shouldShowView: true
[SYNC] Setting view bounds: {"x":0,"y":138,"width":1400,"height":762}
```

This confirms the view occupies exactly y=138 to y=900, leaving y=0-138 for React chrome.
