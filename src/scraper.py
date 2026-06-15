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

            # Step 3: Wait for page load selector (new ID is #fromDate)
            await page.wait_for_selector("#fromDate", timeout=15000)

            # Step 4: Fetch daily margin directly via browser evaluate
            print(f"[scraper] Fetching daily margin directly via API...")
            api_result = await page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch('/risk-management/daily-margin/GetDailyMargin?symbol=ALL&fromDate=' + encodeURIComponent('{date_display}') + '&expiryDate=ALL&fileID=ALL&pageNumber=1&pageSize=10000&isExport=false', {{
                            headers: {{
                                'X-Requested-With': 'XMLHttpRequest',
                                'Content-Type': 'application/json',
                                'Referer': 'https://www.mcxccl.com/risk-management/daily-margin'
                            }}
                        }});
                        return await resp.text();
                    }} catch (e) {{
                        return null;
                    }}
                }}
            """)

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

        if isinstance(data, dict):
            if "Data" in data:
                return data["Data"]
            if "d" in data:
                inner = data["d"]
                if isinstance(inner, str):
                    inner = json.loads(inner)
                return inner.get("Data") or []

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

    symbol = (raw_row.get("symbol") or raw_row.get("Symbol") or "").strip()
    if not symbol:
        return None

    # Skip header/summary rows
    if symbol.lower() in ("symbol", "contract", "commodity", ""):
        return None

    expiry = (raw_row.get("expiryDate") or raw_row.get("ExpiryDate") or "").strip()

    # Use elmLong/elmShort or ELMLong/ELMShort
    elm = raw_row.get("elmLong") or raw_row.get("elmShort") or raw_row.get("ELMLong") or raw_row.get("ELMShort")

    # Volatility keys (note: spelling in new API is 'aailyVolatility'!)
    daily_vol = raw_row.get("dailyVolatility") or raw_row.get("aailyVolatility") or raw_row.get("DailyVolatility")
    ann_vol = raw_row.get("annualizedVolatility") or raw_row.get("AnnualizedVolatility")

    return {
        "date": date_str,
        "symbol": symbol,
        "expiry": expiry,
        "instrument_id": raw_row.get("instrumentID") or raw_row.get("InstrumentID") or "",
        "file_id": raw_row.get("fileID") or raw_row.get("FileID"),
        "initial_margin_pct": raw_row.get("initialMargin") or raw_row.get("InitialMargin"),
        "elm_pct": elm,
        "tender_margin_pct": raw_row.get("tenderMargin") or raw_row.get("TenderMargin"),
        "total_margin_pct": raw_row.get("totalMargin") or raw_row.get("TotalMargin"),
        "additional_long_margin_pct": raw_row.get("additionalLongMargin") or raw_row.get("AdditionalLongMargin"),
        "additional_short_margin_pct": raw_row.get("additionalShortMargin") or raw_row.get("AdditionalShortMargin"),
        "special_long_margin_pct": raw_row.get("specialLongMargin") or raw_row.get("SpecialLongMargin"),
        "special_short_margin_pct": raw_row.get("specialShortMargin") or raw_row.get("SpecialShortMargin"),
        "delivery_margin_pct": raw_row.get("deliveryMargin") or raw_row.get("DeliveryMargin"),
        "daily_volatility": daily_vol,
        "annualized_volatility": ann_vol,
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
