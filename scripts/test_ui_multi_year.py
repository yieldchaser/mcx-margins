import asyncio
import http.server
import socketserver
import threading
import time
from pathlib import Path
from playwright.async_api import async_playwright

PORT = 8899

def start_server():
    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

async def run():
    httpd = start_server()
    time.sleep(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        
        # Listen for console errors
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))
        
        url = f"http://localhost:{PORT}/docs/index.html"
        await page.goto(url, wait_until="networkidle")

        # Switch to Lifecycle & Capital Calculator tab
        await page.click('#btn-history')
        await asyncio.sleep(1)

        # Open calculator accordion if collapsed
        body_open = await page.eval_on_selector('#calculatorBody', 'el => el.classList.contains("is-open")')
        if not body_open:
            await page.click('#calculatorHeader')
            await asyncio.sleep(1)

        # Test commodities (values in #calcSymbol are lowercase)
        test_symbols = ["gold", "silver", "crudeoil", "copper", "zinc", "ng"]
        for sym in test_symbols:
            await page.select_option("#calcSymbol", sym)
            await asyncio.sleep(0.8)

            years = await page.eval_on_selector_all("#calcYear option", "options => options.map(o => o.value)")
            curr_yr = await page.input_value("#calcYear")
            expiries = await page.eval_on_selector_all("#calcExpiry option", "options => options.map(o => o.value)")
            curr_exp = await page.input_value("#calcExpiry")
            print(f"[{sym.upper()}] Current Year: {curr_yr} | Current Expiry: {curr_exp}")
            print(f"  Years available ({len(years)}): {years}")
            print(f"  Expiries available for {curr_yr}: {len(expiries)}")

            # Test switching to 2018 or an older year
            target_yr = "2018" if "2018" in years else (years[2] if len(years) > 2 else years[1])
            await page.select_option("#calcYear", target_yr)
            await asyncio.sleep(0.8)
            old_expiries = await page.eval_on_selector_all("#calcExpiry option", "options => options.map(o => o.value)")
            sel_exp = await page.input_value("#calcExpiry")
            print(f"  Switched to {target_yr} -> Expiries: {len(old_expiries)} | Selected: {sel_exp}")

            # Verify metrics render
            lev = await page.text_content("#calcLeverageDisplay")
            print(f"  Effective leverage display: {lev.strip() if lev else 'N/A'}")

        # Take a screenshot with Silver in 2018 loaded
        await page.select_option("#calcSymbol", "silver")
        await page.select_option("#calcYear", "2018")
        await asyncio.sleep(1.5)
        screenshot_path = "C:/Users/Dell/.gemini/antigravity/brain/e90b5b2c-13aa-474e-9bfa-a42b74b47f3c/calculator_multi_year_verified.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\nVerification screenshot saved to: {screenshot_path}")

        await browser.close()

    httpd.shutdown()

if __name__ == "__main__":
    asyncio.run(run())
