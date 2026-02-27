"""
MCX CCL Daily Margin Scraper
Scrapes daily margin data from https://www.mcxccl.com/risk-management/daily-margin

Key findings:
- Must visit homepage first to bypass Akamai bot detection
- Date display format: DD/MM/YYYY (for #txtDate)
- Date hidden field format: YYYYMMDD (for cph_InnerContainerRight_C001_txtDate_hid_val)
- API endpoint: POST /backpage.aspx/GetDailyMargin
- API returns JSON: {"d": {"Summary": {"Count": N}, "Data": [...]}}
"""

import asyncio
import json
import sys
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

HOME_URL = "https://www.mcxccl.com/"
URL = "https://www.mcxccl.com/risk-management/daily-margin"

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-gpu",
    "--window-size=1920,1080",
]

CONTEXT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

STEALTH_SCRIPT = """
    delete Object.getPrototypeOf(navigator).webdriver;
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
"""


async def scrape_margin(date_str: str) -> list[dict]:
    """
    Scrape margin data for a given date.
    date_str: YYYY-MM-DD format
    Returns list of raw dicts from the API.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # Hidden field format: YYYYMMDD
    date_yyyymmdd = dt.strftime("%Y%m%d")
    # Display format: DD/MM/YYYY
    date_display = dt.strftime("%d/%m/%Y")

    print(f"[scraper] Fetching data for {date_str} (hidden: {date_yyyymmdd}, display: {date_display})")

    api_result = None
    api_event = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers=CONTEXT_HEADERS,
        )

        await context.add_init_script(STEALTH_SCRIPT)

        page = await context.new_page()

        async def handle_response(response):
            nonlocal api_result
            if "GetDailyMargin" in response.url:
                try:
                    body = await response.text()
                    print(f"[scraper] API response: status={response.status}, len={len(body)}")
                    api_result = body
                    api_event.set()
                except Exception as e:
                    print(f"[scraper] Error reading API response: {e}")
                    api_event.set()

        page.on("response", handle_response)

        try:
            # Step 1: Visit homepage to bypass Akamai bot detection
            print(f"[scraper] Visiting homepage to bypass bot detection...")
            await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
            home_title = await page.title()
            print(f"[scraper] Homepage title: {home_title}")

            if "Access Denied" in home_title:
                print("[scraper] Homepage blocked - cannot proceed")
                return []

            await asyncio.sleep(1)

            # Step 2: Navigate to daily margin page
            print(f"[scraper] Navigating to daily margin page...")
            await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            page_title = await page.title()
            print(f"[scraper] Daily margin title: {page_title}")

            if "Access Denied" in page_title:
                print("[scraper] Daily margin page blocked")
                return []

            await asyncio.sleep(2)

            # Step 3: Fill the date display field
            await page.wait_for_selector("#txtDate", timeout=15000)
            await page.fill("#txtDate", date_display)
            print(f"[scraper] Filled display date: {date_display}")

            # Step 4: Set the hidden field to YYYYMMDD format (this is what the API uses)
            await page.evaluate(f"""
                var hiddenField = document.getElementById('cph_InnerContainerRight_C001_txtDate_hid_val');
                if (hiddenField) {{
                    hiddenField.value = '{date_yyyymmdd}';
                }}
            """)

            # Verify hidden field
            hidden_val = await page.evaluate("""
                (() => {
                    var el = document.getElementById('cph_InnerContainerRight_C001_txtDate_hid_val');
                    return el ? el.value : 'NOT FOUND';
                })()
            """)
            print(f"[scraper] Hidden field value: {hidden_val}")

            # Step 5: Click Show button
            await page.wait_for_selector("#btnShow", timeout=10000)
            await page.click("#btnShow")
            print("[scraper] Clicked Show button")

            # Step 6: Wait for API response
            try:
                await asyncio.wait_for(api_event.wait(), timeout=30.0)
                print("[scraper] API response received")
            except asyncio.TimeoutError:
                print("[scraper] Timeout waiting for API response")

            # Step 7: Wait for overlay to disappear
            try:
                await page.wait_for_selector(".overlay2", state="hidden", timeout=15000)
                print("[scraper] Overlay hidden")
            except PlaywrightTimeoutError:
                pass

            await asyncio.sleep(1)

            # Step 8: Parse the API response
            if api_result:
                records = parse_api_response(api_result)
                print(f"[scraper] Parsed {len(records)} records")
                return records

            print("[scraper] No API response received")
            return []

        except Exception as e:
            print(f"[scraper] Error: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            await browser.close()


def parse_api_response(response_text: str) -> list[dict]:
    """Parse the API JSON response."""
    try:
        data = json.loads(response_text)

        # ASP.NET Web Services pattern: {"d": {"Summary": {...}, "Data": [...]}}
        if isinstance(data, dict) and "d" in data:
            inner = data["d"]
            if isinstance(inner, str):
                inner = json.loads(inner)

            summary = inner.get("Summary", {})
            count = summary.get("Count", 0)
            records = inner.get("Data")

            print(f"[scraper] API summary: Count={count}")

            if not records:
                print("[scraper] API returned no data (Data=null)")
                return []

            return records

        # Direct list
        if isinstance(data, list):
            return data

        print(f"[scraper] Unexpected API response format: {type(data)}")
        return []

    except json.JSONDecodeError as e:
        print(f"[scraper] JSON parse error: {e}")
        print(f"[scraper] Response: {response_text[:200]}")
        return []


def normalize_row(raw_row: dict, date_str: str) -> dict | None:
    """
    Normalize a raw API row into a standard format.
    The API returns fields like: Symbol, ExpiryDate, InitialMargin, ELMLong, ELMShort, etc.
    Returns None if the row should be skipped.
    """
    if not isinstance(raw_row, dict):
        return None

    symbol = raw_row.get("Symbol", "").strip()
    if not symbol:
        return None

    # Skip header/summary rows
    if symbol.lower() in ("symbol", "contract", "commodity", ""):
        return None

    expiry = raw_row.get("ExpiryDate", "").strip()

    # Use ELMLong as the ELM value (ELMShort is usually the same)
    elm = raw_row.get("ELMLong") or raw_row.get("ELMShort")

    return {
        "date": date_str,
        "symbol": symbol,
        "expiry": expiry,
        "instrument_id": raw_row.get("InstrumentID", ""),
        "file_id": raw_row.get("FileID"),
        "initial_margin_pct": raw_row.get("InitialMargin"),
        "elm_pct": elm,
        "tender_margin_pct": raw_row.get("TenderMargin"),
        "total_margin_pct": raw_row.get("TotalMargin"),
        "additional_long_margin_pct": raw_row.get("AdditionalLongMargin"),
        "additional_short_margin_pct": raw_row.get("AdditionalShortMargin"),
        "special_long_margin_pct": raw_row.get("SpecialLongMargin"),
        "special_short_margin_pct": raw_row.get("SpecialShortMargin"),
        "delivery_margin_pct": raw_row.get("DeliveryMargin"),
        "daily_volatility": raw_row.get("DailyVolatility"),
        "annualized_volatility": raw_row.get("AnnualizedVolatility"),
    }


def parse_pct(val) -> float | None:
    """Parse a percentage value, returning float or None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("%", "").replace(",", "")
    if not s or s == "-" or s.lower() == "n/a":
        return None
    try:
        return float(s)
    except ValueError:
        return None
