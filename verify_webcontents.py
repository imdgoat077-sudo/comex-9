#!/usr/bin/env python3
"""Minimal Playwright CDP verification for the migrated WebContentsView.
Assumes the user has navigated the active tab to https://example.com via the UI.
It connects to the Electron CDP endpoint (http://127.0.0.1:9222), discovers the
native page target, and reads its title, URL, and the heading text "Example Domain".
"""
import asyncio
import json
import urllib.request
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"
TARGET_SUBSTRING = "example.com"

async def main():
    # Connect to the CDP server (not a specific target)
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(CDP_URL)

    # Find the page that loaded example.com
    target_page = None
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if TARGET_SUBSTRING in pg.url:
                target_page = pg
                break
        if target_page:
            break

    if not target_page:
        print("FAIL: Could not find a page with example.com loaded.")
        await playwright.stop()
        return

    title = await target_page.title()
    url = target_page.url
    heading = await target_page.evaluate('''() => {
        const el = document.querySelector('h1');
        return el ? el.innerText : '';
    }''')

    print('--- RESULT ---')
    print(f'Title: {title}')
    print(f'URL: {url}')
    print(f'Heading text: {heading}')

    await playwright.stop()

if __name__ == '__main__':
    asyncio.run(main())
