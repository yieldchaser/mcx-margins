#!/usr/bin/env python3
"""
scripts/harvest_historical_archive.py
High-speed historical harvester and columnar compression pipeline for MCX commodities.
- Scrapes full historical MCX CCL daily margins (back to 2010) in fast parallel browser chunks.
- Scrapes full historical MCX Bhavcopy prices (back to 2007).
- Stores all commodity records locally in compressed Zstandard Parquet format in data/mcx_vault/historical/.
- Allows exporting any year directly into the web calculator without bloating SQLite or exceeding Git limits.
"""

import os
import sys
import time
import json
import asyncio
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import duckdb
from playwright.async_api import async_playwright

from src.scraper import (
    BROWSER_ARGS, CONTEXT_HEADERS, STEALTH_SCRIPT, HOME_URL, URL,
    normalize_row, parse_pct
)
EXCLUDED_SYMBOLS = {'MCXBULLDEX', 'MCXMETLDEX', 'BULLDEX', 'METLDEX'}
from scripts.fetch_prices import (
    BHAVCOPY_URL, DATE_INPUT_SELECTOR, parse_response,
    BhavSession, normalize as normalize_price
)

IST = timezone(timedelta(hours=5, minutes=30))
HISTORICAL_DIR = REPO_ROOT / "data" / "mcx_vault" / "historical"
MARGINS_HIST_DIR = HISTORICAL_DIR / "margins"
PRICES_HIST_DIR = HISTORICAL_DIR / "prices"

MARGINS_HIST_DIR.mkdir(parents=True, exist_ok=True)
PRICES_HIST_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"[{ts}] {msg}", flush=True)

def get_weekdays(start_date: str, end_date: str) -> list[str]:
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    out = []
    while cur <= end_dt:
        if cur.weekday() < 5:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out

def get_harvested_margin_dates() -> set[str]:
    con = duckdb.connect()
    dates = set()
    for p in MARGINS_HIST_DIR.glob("*.parquet"):
        try:
            res = con.execute(f"SELECT DISTINCT date FROM read_parquet('{p}')").fetchall()
            dates.update(str(r[0]) for r in res)
        except Exception:
            pass
    # Also check margins.db
    try:
        import sqlite3
        conn = sqlite3.connect(REPO_ROOT / "data" / "margins.db")
        res = conn.execute("SELECT DISTINCT date FROM margins GROUP BY date HAVING count(distinct symbol) >= 15").fetchall()
        dates.update(r[0] for r in res)
        conn.close()
    except Exception:
        pass
    return dates

def get_harvested_price_dates() -> set[str]:
    con = duckdb.connect()
    dates = set()
    for p in PRICES_HIST_DIR.glob("*.parquet"):
        try:
            res = con.execute(f"SELECT DISTINCT date FROM read_parquet('{p}')").fetchall()
            dates.update(str(r[0]) for r in res)
        except Exception:
            pass
    # Also check prices.db
    try:
        import sqlite3
        conn = sqlite3.connect(REPO_ROOT / "data" / "prices.db")
        res = conn.execute("SELECT DISTINCT date FROM prices GROUP BY date HAVING count(distinct symbol) >= 15").fetchall()
        dates.update(r[0] for r in res)
        conn.close()
    except Exception:
        pass
    return dates

async def harvest_margins(dates: list[str], batch_size: int = 10, session_limit: int = 50):
    """
    Harvests MCX CCL margins using high-speed parallel browser requests in batches of 10.
    Stores records compressed by year in Parquet format.
    """
    if not dates:
        log("No margin dates to harvest.")
        return 0

    log(f"Starting high-speed MCX CCL margin harvest for {len(dates)} dates...")
    total_saved = 0

    for s_idx in range(0, len(dates), session_limit):
        s_chunk = dates[s_idx:s_idx + session_limit]
        log(f"Session Chunk {s_idx // session_limit + 1}: {len(s_chunk)} dates ({s_chunk[0]} to {s_chunk[-1]})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers=CONTEXT_HEADERS,
            )
            await context.add_init_script(STEALTH_SCRIPT)
            page = await context.new_page()

            try:
                await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)
                await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector("#fromDate", timeout=15000)
            except Exception as e:
                log(f"Error establishing margin stealth session: {e}")
                await browser.close()
                continue

            for b_idx in range(0, len(s_chunk), batch_size):
                batch_dates = s_chunk[b_idx:b_idx + batch_size]
                dates_display = [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y") for d in batch_dates]
                
                t0 = time.time()
                try:
                    results = await page.evaluate(f"""
                        async () => {{
                            const dates = {dates_display};
                            const fetchDate = async (d) => {{
                                try {{
                                    const resp = await fetch('/DailyMargin/GetDailyMargin?fromDate=' + encodeURIComponent(d), {{
                                        headers: {{
                                            'X-Requested-With': 'XMLHttpRequest',
                                            'Content-Type': 'application/json',
                                            'Referer': 'https://www.mcxccl.com/risk-management/daily-margin'
                                        }}
                                    }});
                                    const txt = await resp.text();
                                    return {{ date: d, ok: true, data: txt }};
                                }} catch(e) {{
                                    return {{ date: d, ok: false, error: e.toString() }};
                                }}
                            }};
                            return await Promise.all(dates.map(d => fetchDate(d)));
                        }}
                    """)
                except Exception as e:
                    log(f"  Evaluate error on batch {batch_dates}: {e}")
                    continue

                batch_rows_by_year = {}
                for item in results:
                    if not item.get("ok") or not item.get("data"):
                        continue
                    try:
                        raw_json = json.loads(item["data"])
                        raw_records = raw_json if isinstance(raw_json, list) else (raw_json.get("Data") or raw_json.get("d") or [])
                    except Exception:
                        continue

                    # Find date_str from display date
                    d_disp = item["date"]
                    d_str = datetime.strptime(d_disp, "%d/%m/%Y").strftime("%Y-%m-%d")
                    yr = d_str[:4]

                    for r in raw_records:
                        norm = normalize_row(r, d_str)
                        if not norm:
                            continue
                        sym = (norm.get("symbol") or "").strip().upper()
                        inst = (norm.get("instrument_id") or "").strip().upper()
                        if not sym or sym in EXCLUDED_SYMBOLS or inst == "FUTIDX":
                            continue

                        row_dict = {
                            "date": d_str,
                            "symbol": sym,
                            "expiry": norm.get("expiry"),
                            "instrument_id": inst,
                            "initial_margin_pct": parse_pct(norm.get("initial_margin_pct")),
                            "elm_pct": parse_pct(norm.get("elm_pct")),
                            "tender_margin_pct": parse_pct(norm.get("tender_margin_pct")),
                            "total_margin_pct": parse_pct(norm.get("total_margin_pct")),
                            "additional_long_margin_pct": parse_pct(norm.get("additional_long_margin_pct")),
                            "additional_short_margin_pct": parse_pct(norm.get("additional_short_margin_pct")),
                            "special_long_margin_pct": parse_pct(norm.get("special_long_margin_pct")),
                            "special_short_margin_pct": parse_pct(norm.get("special_short_margin_pct")),
                            "delivery_margin_pct": parse_pct(norm.get("delivery_margin_pct")),
                            "daily_volatility": norm.get("daily_volatility"),
                            "annualized_volatility": norm.get("annualized_volatility"),
                        }
                        batch_rows_by_year.setdefault(yr, []).append(row_dict)

                # Append to Year-Partitioned Zstandard Parquet
                for yr, rows in batch_rows_by_year.items():
                    if not rows:
                        continue
                    df_new = pd.DataFrame(rows)
                    p_file = MARGINS_HIST_DIR / f"margins_{yr}.parquet"
                    if p_file.exists():
                        df_existing = pd.read_parquet(p_file)
                        df_comb = pd.concat([df_existing, df_new], ignore_index=True)
                        df_comb = df_comb.drop_duplicates(subset=["date", "symbol", "expiry"], keep="last")
                    else:
                        df_comb = df_new
                    df_comb.sort_values(by=["date", "symbol", "expiry"]).reset_index(drop=True).to_parquet(
                        p_file, compression="zstd", index=False
                    )
                    total_saved += len(df_new)

                elapsed = time.time() - t0
                saved_count = sum(len(r) for r in batch_rows_by_year.values())
                log(f"  Batch {batch_dates[0]}..{batch_dates[-1]}: {saved_count:,} records saved ({elapsed:.2f}s)")
                await asyncio.sleep(0.2)

            await browser.close()

    log(f"Margin harvest completed. Total records saved: {total_saved:,}")
    return total_saved

async def harvest_prices(dates: list[str], batch_size: int = 10, session_limit: int = 50):
    """
    Harvests MCX Bhavcopy prices using high-speed parallel browser requests in batches of 10.
    Stores records compressed by year in Parquet format.
    """
    if not dates:
        log("No price dates to harvest.")
        return 0

    log(f"Starting high-speed MCX Bhavcopy price harvest for {len(dates)} dates in batches of {batch_size}...")
    total_saved = 0

    for s_idx in range(0, len(dates), session_limit):
        s_chunk = dates[s_idx:s_idx + session_limit]
        log(f"Bhavcopy Session Chunk {s_idx // session_limit + 1}: {len(s_chunk)} dates ({s_chunk[0]} to {s_chunk[-1]})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers=CONTEXT_HEADERS,
            )
            await context.add_init_script(STEALTH_SCRIPT)
            page = await context.new_page()

            try:
                await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)
                await page.goto(BHAVCOPY_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(DATE_INPUT_SELECTOR, timeout=15000)
            except Exception as e:
                log(f"Error establishing Bhavcopy stealth session: {e}")
                await browser.close()
                continue

            token = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[name="X-XSRF-Token"]');
                    if (!meta) return null;
                    const content = meta.getAttribute('content');
                    const div = document.createElement('div');
                    div.innerHTML = content;
                    const input = div.querySelector('input');
                    return input ? input.value : null;
                }
            """)
            if not token:
                log("Error: Request verification token not found in meta tag")
                await browser.close()
                continue

            for b_idx in range(0, len(s_chunk), batch_size):
                batch_dates = s_chunk[b_idx:b_idx + batch_size]
                dates_display = [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y") for d in batch_dates]
                
                t0 = time.time()
                try:
                    results = await page.evaluate(f"""
                        async () => {{
                            const dates = {dates_display};
                            const fetchDate = async (d) => {{
                                try {{
                                    const resp = await fetch('/market-data/bhavcopy/GetDateWiseBhavCopy?InstrumentName=ALL&fromDate=' + encodeURIComponent(d), {{
                                        headers: {{
                                            '__requestverificationtoken': '{token}',
                                            'X-Requested-With': 'XMLHttpRequest',
                                            'Content-Type': 'application/json'
                                        }}
                                    }});
                                    const txt = await resp.text();
                                    return {{ date: d, ok: true, data: txt }};
                                }} catch(e) {{
                                    return {{ date: d, ok: false, error: e.toString() }};
                                }}
                            }};
                            return await Promise.all(dates.map(d => fetchDate(d)));
                        }}
                    """)
                except Exception as e:
                    log(f"  Evaluate error on bhavcopy batch {batch_dates}: {e}")
                    continue

                batch_rows_by_year = {}
                for item in results:
                    if not item.get("ok") or not item.get("data"):
                        continue
                    try:
                        raw_rows = parse_response(item["data"])
                    except Exception:
                        continue

                    d_disp = item["date"]
                    d_str = datetime.strptime(d_disp, "%d/%m/%Y").strftime("%Y-%m-%d")
                    yr = d_str[:4]

                    normalized = [r for raw in raw_rows if (r := normalize_price(raw, d_str))]
                    if normalized:
                        batch_rows_by_year.setdefault(yr, []).extend(normalized)

                # Append to Year-Partitioned Zstandard Parquet
                for yr, rows in batch_rows_by_year.items():
                    if not rows:
                        continue
                    df_new = pd.DataFrame(rows)
                    p_file = PRICES_HIST_DIR / f"prices_{yr}.parquet"
                    if p_file.exists():
                        df_existing = pd.read_parquet(p_file)
                        df_comb = pd.concat([df_existing, df_new], ignore_index=True)
                        df_comb = df_comb.drop_duplicates(subset=["date", "symbol", "expiry"], keep="last")
                    else:
                        df_comb = df_new
                    df_comb.sort_values(by=["date", "symbol", "expiry"]).reset_index(drop=True).to_parquet(
                        p_file, compression="zstd", index=False
                    )
                    total_saved += len(df_new)

                elapsed = time.time() - t0
                saved_count = sum(len(r) for r in batch_rows_by_year.values())
                log(f"  Batch {batch_dates[0]}..{batch_dates[-1]}: {saved_count:,} price rows saved ({elapsed:.2f}s)")
                await asyncio.sleep(0.2)

            await browser.close()

    log(f"Price harvest completed. Total records saved: {total_saved:,}")
    return total_saved

def main():
    parser = argparse.ArgumentParser(description="High-Speed Historical Multi-Commodity Archive Pipeline")
    parser.add_argument("--mode", choices=["margins", "prices", "all"], default="all")
    parser.add_argument("--start", type=str, default="2024-01-01", help="Start date YYYY-MM-DD (e.g. 2010-01-01)")
    parser.add_argument("--end", type=str, default="2025-12-31", help="End date YYYY-MM-DD")
    parser.add_argument("--reverse", action="store_true", help="Harvest newest to oldest first")
    parser.add_argument("--limit", type=int, default=0, help="Max dates to harvest")
    args = parser.parse_args()

    all_weekdays = get_weekdays(args.start, args.end)
    if args.reverse:
        all_weekdays.reverse()

    if args.mode in ["margins", "all"]:
        harvested_m = get_harvested_margin_dates()
        pending_m = [d for d in all_weekdays if d not in harvested_m]
        if args.limit > 0:
            pending_m = pending_m[:args.limit]
        log(f"Pending MCX CCL margin dates ({args.start} to {args.end}): {len(pending_m)}")
        asyncio.run(harvest_margins(pending_m))

    if args.mode in ["prices", "all"]:
        harvested_p = get_harvested_price_dates()
        pending_p = [d for d in all_weekdays if d not in harvested_p]
        if args.limit > 0:
            pending_p = pending_p[:args.limit]
        log(f"Pending Bhavcopy price dates ({args.start} to {args.end}): {len(pending_p)}")
        asyncio.run(harvest_prices(pending_p))

if __name__ == "__main__":
    main()
