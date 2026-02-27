"""
Backfill script for MCX CCL margin data.
Usage: python3 backfill.py YYYY-MM-DD
"""
import asyncio
import sys
import json
import time
from datetime import datetime, timedelta

import db
from scraper import scrape_margin, normalize_row, parse_pct

SYMBOLS_TO_STORE = {"NATURALGAS", "NATGASMINI"}
REQUEST_DELAY = 3

def generate_weekdays(start_date, end_date):
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates

def fetch_and_save(date_str):
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
    if len(sys.argv) < 2:
        print("Usage: python3 backfill.py YYYY-MM-DD")
        sys.exit(1)
    start_str = sys.argv[1]
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{start_str}'. Use YYYY-MM-DD.")
        sys.exit(1)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"[backfill] Initializing database...")
    db.init_db()
    existing_dates = set(db.get_all_dates())
    print(f"[backfill] Found {len(existing_dates)} dates already in DB")
    all_weekdays = generate_weekdays(start_date, today)
    print(f"[backfill] Total weekdays from {start_str} to {today.strftime('%Y-%m-%d')}: {len(all_weekdays)}")
    missing_dates = [d for d in all_weekdays if d not in existing_dates]
    print(f"[backfill] Dates to fetch: {len(missing_dates)} (skipping {len(all_weekdays) - len(missing_dates)} already in DB)")
    if not missing_dates:
        print("[backfill] All dates already in DB. Nothing to do.")
        return
    total_fetched = 0
    total_saved = 0
    total_errors = 0
    skipped_empty = 0
    for i, date_str in enumerate(missing_dates, 1):
        print(f"\n[backfill] Date {i}/{len(missing_dates)}: {date_str}")
        try:
            saved = fetch_and_save(date_str)
            if saved > 0:
                total_saved += saved
                total_fetched += 1
                print(f"[backfill] Date {i}/{len(missing_dates)}: {date_str} - {saved} records saved")
            else:
                skipped_empty += 1
                print(f"[backfill] Date {i}/{len(missing_dates)}: {date_str} - 0 records (holiday/no data)")
        except Exception as e:
            total_errors += 1
            print(f"[backfill] Date {i}/{len(missing_dates)}: {date_str} - ERROR: {e}")
            import traceback
            traceback.print_exc()
        if i < len(missing_dates):
            print(f"[backfill] Waiting {REQUEST_DELAY}s before next request...")
            time.sleep(REQUEST_DELAY)
    print(f"\n{'='*60}")
    print(f"[backfill] SUMMARY")
    print(f"{'='*60}")
    print(f"  Dates attempted:    {len(missing_dates)}")
    print(f"  Dates with data:    {total_fetched}")
    print(f"  Dates empty/holiday:{skipped_empty}")
    print(f"  Dates with errors:  {total_errors}")
    print(f"  Total records saved:{total_saved}")
    all_dates_now = db.get_all_dates()
    if all_dates_now:
        print(f"\n  DB date range: {min(all_dates_now)} to {max(all_dates_now)}")
        print(f"  Total dates in DB: {len(all_dates_now)}")

if __name__ == "__main__":
    main()
