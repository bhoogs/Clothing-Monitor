#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

TARGET_URL = "http://pioneercreek.cps.golf"

async def debug():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-http2"])
        ctx = await browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ))
        page = await ctx.new_page()
        print(f"Loading {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(5_000)
        text = await page.inner_text("body")
        print(f"Page length: {len(text)} chars")
        print("=== PAGE TEXT ===")
        print(text[:3000])
        print("=== END ===")
        
        # Also check the URL we landed on (might have redirected)
        print(f"Final URL: {page.url}")
        await browser.close()

asyncio.run(debug())
