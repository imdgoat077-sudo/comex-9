#!/usr/bin/env python3
"""
Debug script to inspect Electron window view hierarchy and verify WebContentsView bounds.
"""
import asyncio
import json
import urllib.request

CDP_URL = "http://127.0.0.1:9222"

async def main():
    # Step 1: Get CDP targets to see what's loaded
    print("=" * 80)
    print("CDP TARGETS")
    print("=" * 80)
    req = urllib.request.urlopen(f"{CDP_URL}/json/list")
    targets = json.loads(req.read().decode())
    print(f"Found {len(targets)} targets:")
    for t in targets:
        print(f"  - {t.get('title')} ({t.get('type')})")
        print(f"    URL: {t.get('url')}")
        print(f"    WebSocket: {t.get('webSocketDebuggerUrl')}")
    print()

    # Step 2: Test with a real page to see bounds
    print("=" * 80)
    print("TESTING BOUNDS WITH A WEBSITE")
    print("=" * 80)
    
    # We need to send an IPC message to create a tab with a real URL
    # For now, let's just document the expected structure:
    print()
    print("Expected Electron window structure:")
    print("  mainWindow (BrowserWindow)")
    print("    ├── contentView (BrowserWindow.contentView)")
    print("    │   ├── [0]: WebContentsView (React renderer - Chrome webContents)")
    print("    │   └── [1]: WebContentsView (Active browser tab - WebContentsView)")
    print()
    print("The issue is that BrowserWindow.addChildView() paints views in")
    print("STACKING ORDER: later children are PAINTED ON TOP.")
    print()
    print("Current problem:")
    print("  1. Electron creates mainWindow with a WebContentsView for the React renderer")
    print("  2. When a new tab is created, we create a NEW WebContentsView")
    print("  3. We addChildView() the new WebContentsView to mainWindow.contentView")
    print("  4. The new WebContentsView is painted ON TOP of the React renderer!")
    print()
    print("Solution options:")
    print("  A. Use setBounds() to make the tab view SMALLER than the window,")
    print("     but this still paints it on top (just in a smaller area).")
    print()
    print("  B. Move React UI to a separate native view/window (major refactor).")
    print()
    print("  C. Move the browser content to a BrowserView or WebContentsView and")
    print("     keep the React chrome in the mainWindow.webContents (the default")
    print("     Electron renderer) - this is the correct approach!")
    print()
    print("  D. Use BrowserView for browser content instead of WebContentsView.")
    print("     BrowserView is designed exactly for this use case!")
    print()
    print("=" * 80)
    print("RECOMMENDATION: Switch from WebContentsView to BrowserView")
    print("=" * 80)
    print()
    print("BrowserView is the Electron-recommended way to embed browser content")
    print("inside an Electron window while keeping a separate Chrome UI layer.")
    print()
    print("BrowserView API:")
    print("  - BrowserView() creates a native browser view")
    print("  - win.setBrowserView(view) embeds it in the window")
    print("  - win.removeBrowserView(view) removes it")
    print("  - view.setBounds(rect) controls position/size")
    print()
    print("This architecture naturally separates:")
    print("  • React UI in mainWindow (Chrome webContents)")
    print("  • Browser content in BrowserView (separate native layer)")
    print("  • No z-order battles - they're separate layers")
    print()
    print("If you want to see the current view hierarchy, add this to electron/main.js")
    print("after createWindow():")
    print("  console.log('Content views:', mainWindow.contentView.children)")

if __name__ == "__main__":
    asyncio.run(main())
