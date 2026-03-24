"""
Smart fetch: scrapes today's margin data with retry logic.

Checks the DB first — if today's data already exists, skips immediately.
Otherwise fetches from mcxccl.com and retries if the site hasn't published yet.

Exit codes:
  0 — new data saved (pipeline should proceed)
  2 — no new data after all retries (not a failure, just nothing to commit)
"""

import asyncio
import sys
import time
import argparse
from datetime import date

import src.db as db
from src.scraper import scrape_margin, normalize_row, parse_pct

SYMBOLS_TO_STORE = {"NATURALGAS", "NATGASMINI"}


def has_todays_data(date_str: str) -> bool:
    records = db.get_margins(date=date_str)
    return len(records) > 0


def fetch_and_store(date_str: str) -> int:
    """Fetch from mcxccl.com and store. Returns number of new records saved."""
    raw_rows = asyncio.run(scrape_margin(date_str))
    if not raw_rows:
        return 0

    saved = 0
    for raw_row in raw_rows:
        normalized = normalize_row(raw_row, date_str)
        if normalized is None:
            continue
        if normalized.get("symbol") not in SYMBOLS_TO_STORE:
            continue

        normalized["initial_margin_pct"] = parse_pct(normalized.get("initial_margin_pct"))
        normalized["elm_pct"] = parse_pct(normalized.get("elm_pct"))
        normalized["tender_margin_pct"] = parse_pct(normalized.get("tender_margin_pct"))
        normalized["total_margin_pct"] = parse_pct(normalized.get("total_margin_pct"))
        normalized["additional_long_margin_pct"] = parse_pct(normalized.get("additional_long_margin_pct"))
        normalized["additional_short_margin_pct"] = parse_pct(normalized.get("additional_short_margin_pct"))
        normalized["special_long_margin_pct"] = parse_pct(normalized.get("special_long_margin_pct"))
        normalized["special_short_margin_pct"] = parse_pct(normalized.get("special_short_margin_pct"))
        normalized["delivery_margin_pct"] = parse_pct(normalized.get("delivery_margin_pct"))

        if db.upsert_margin(normalized):
            saved += 1

    return saved


def main():
    parser = argparse.ArgumentParser(description="Fetch today's MCX margin data with retry logic")
    parser.add_argument("--retries", type=int, default=5, help="Max fetch attempts (default: 5)")
    parser.add_argument("--wait", type=int, default=15, help="Minutes between retries (default: 15)")
    args = parser.parse_args()

    db.init_db()
    today = date.today().strftime("%Y-%m-%d")
    print(f"[fetch_today] Target date: {today}")

    if has_todays_data(today):
        print(f"[fetch_today] Data already exists for {today}, nothing to do.")
        sys.exit(0)

    for attempt in range(1, args.retries + 1):
        print(f"[fetch_today] Attempt {attempt}/{args.retries} for {today}")
        saved = fetch_and_store(today)

        if saved > 0:
            print(f"[fetch_today] SUCCESS: {saved} new records saved for {today}")
            sys.exit(0)

        print(f"[fetch_today] mcxccl.com has not published data for {today} yet.")
        if attempt < args.retries:
            print(f"[fetch_today] Waiting {args.wait} minutes before next attempt...")
            time.sleep(args.wait * 60)

    print(f"[fetch_today] No data found after {args.retries} attempts. Will retry on next scheduled run.")
    sys.exit(2)


if __name__ == "__main__":
    main()
