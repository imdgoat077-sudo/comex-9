#!/usr/bin/env python3
"""
CDP Visibility Test for Electron <webview> Integration
Tests whether Playwright can connect to Electron via CDP and interact with <webview> contents.
"""

import asyncio
import sys
from playwright.async_api import async_playwright


async def test_cdp_connection():
    """Test CDP connection to Electron and webview accessibility."""
    
    results = {
        'CDP connection': 'FAIL',
        'Electron main page visible': 'FAIL',
        'Existing <webview> target visible': 'FAIL',
        'Webview DOM accessible': 'FAIL',
        'Webview element lookup': 'FAIL',
        'Webview interaction': 'FAIL'
    }
    
    playwright = None
    browser = None
    
    try:
        print("=" * 80)
        print("CDP VISIBILITY TEST - ELECTRON <WEBVIEW> INTEGRATION")
        print("=" * 80)
        print()
        
        # Step 1: Query CDP targets directly
        print("[STEP 1] Querying Electron CDP targets on http://127.0.0.1:9222/json/list...")
        import urllib.request
        import json
        
        try:
            req = urllib.request.urlopen('http://127.0.0.1:9222/json/list')
            targets = json.loads(req.read().decode())
            results['CDP connection'] = 'PASS'
            print(f"✓ CDP connection successful, found {len(targets)} targets")
        except Exception as e:
            print(f"✗ CDP connection failed: {e}")
            print()
            print("DIAGNOSIS: Electron is not running or CDP port 9222 is not enabled.")
            return results
        
        print()
        
        # Step 2 & 3: Find Webview Target
        print("[STEP 2 & 3] Searching for <webview> target...")
        webview_target = None
        main_page_target = None
        
        for t in targets:
            print(f"  Target: {t.get('title', 'Unknown')} (Type: {t.get('type')}) - URL: {t.get('url')}")
            if t.get('type') == 'page' and 'localhost' in t.get('url', ''):
                main_page_target = t
                results['Electron main page visible'] = 'PASS'
            elif t.get('type') == 'webview':
                webview_target = t
                results['Existing <webview> target visible'] = 'PASS'
                print(f"  ✓ Found <webview> target: {t.get('url')}")
                
        if not webview_target:
            print("  ✗ No <webview> target found in CDP list")
            return results
            
        print()
        
        # Step 3.5: Connect Playwright directly to the Webview's WebSocket
        print(f"[STEP 3.5] Connecting Playwright to Webview WebSocket: {webview_target['webSocketDebuggerUrl']}")
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(webview_target['webSocketDebuggerUrl'])
        
        # When connecting directly to a target's WS endpoint, the context has 1 page
        webview_page = browser.contexts[0].pages[0]
        
        print()
        
        # Step 4: Test DOM accessibility
        print("[STEP 4] Testing DOM access on webview page...")
        print(f"Target URL: {webview_page.url}")
        
        try:
            # Wait for page to be in a reasonable state
            await webview_page.wait_for_load_state('domcontentloaded', timeout=5000)
            results['Webview DOM accessible'] = 'PASS'
            print("✓ DOM content loaded successfully")
        except Exception as e:
            print(f"✗ DOM load failed: {e}")
            return results
        
        print()
        
        # Step 5: Element lookup test
        print("[STEP 5] Testing element lookup...")
        
        try:
            # Try to find common elements
            html = await webview_page.query_selector('html')
            body = await webview_page.query_selector('body')
            
            if html and body:
                results['Webview element lookup'] = 'PASS'
                print("✓ Successfully located <html> and <body> elements")
                
                # Get page title
                page_title = await webview_page.title()
                print(f"  Page title: {page_title}")
                
                # Get body text (first 200 chars)
                body_text = await body.inner_text()
                if body_text:
                    preview = body_text[:200].replace('\n', ' ')
                    print(f"  Body text preview: {preview}...")
            else:
                print("✗ Could not locate basic HTML elements")
                return results
                
        except Exception as e:
            print(f"✗ Element lookup failed: {e}")
            return results
        
        print()
        
        # Step 6: Interaction test
        print("[STEP 6] Testing interaction capability...")
        
        try:
            # Try a safe interaction: get viewport size
            viewport = webview_page.viewport_size
            print(f"  Viewport size: {viewport}")
            
            # Try to evaluate JavaScript in the page
            result = await webview_page.evaluate('() => document.readyState')
            print(f"  Document ready state: {result}")
            
            # Try to count visible elements
            element_count = await webview_page.evaluate('() => document.querySelectorAll("*").length')
            print(f"  Total DOM elements: {element_count}")
            
            results['Webview interaction'] = 'PASS'
            print("✓ Interaction test successful")
            
        except Exception as e:
            print(f"✗ Interaction failed: {e}")
            return results
        
        return results
        
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return results
        
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


def print_results(results):
    """Print final test results."""
    print()
    print("=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, status in results.items():
        icon = "✓" if status == "PASS" else "✗"
        print(f"{icon} {test_name}: {status}")
        if status == "FAIL":
            all_passed = False
    
    print("=" * 80)
    print()
    
    if all_passed:
        print("CONCLUSION: ✓ SUCCESS")
        print()
        print("Playwright can successfully connect to Electron via CDP and interact with")
        print("the contents of the <webview> tag. You can proceed with browser-use integration")
        print("using the current architecture without refactoring to BrowserView.")
    else:
        print("CONCLUSION: ✗ FAILED")
        print()
        
        if results['CDP connection'] == 'FAIL':
            print("The CDP connection failed. Make sure:")
            print("1. Electron is running (npm run electron:dev)")
            print("2. Port 9222 is not blocked by firewall")
            print("3. The remote-debugging-port switch is enabled in main.js")
        
        elif results['Existing <webview> target visible'] == 'FAIL':
            print("Playwright cannot see the <webview> as a separate page/target.")
            print()
            print("MINIMUM ARCHITECTURAL CHANGE REQUIRED:")
            print("Replace <webview> with Electron's BrowserView or WebContentsView.")
            print()
            print("WHY: Electron's <webview> runs as an out-of-process guest WebContents that")
            print("is not properly exposed as a CDP target. BrowserView/WebContentsView are")
            print("first-class browser contexts that Playwright can control directly.")
        
        elif results['Webview DOM accessible'] == 'FAIL':
            print("The <webview> page was found but DOM access failed.")
            print("This indicates the page may still be loading or has navigation issues.")
        
        else:
            print("Partial failure detected. Review the detailed output above.")


async def main():
    """Main entry point."""
    results = await test_cdp_connection()
    print_results(results)
    
    # Exit with appropriate code
    all_passed = all(status == 'PASS' for status in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    asyncio.run(main())
