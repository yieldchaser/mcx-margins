"""
Main entry point for MCX CCL margin scraper.
Usage: python3 main.py YYYY-MM-DD
"""

import asyncio
import sys
import json
from datetime import datetime

import db
from scraper import scrape_margin, normalize_row, parse_pct


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 main.py YYYY-MM-DD")
        sys.exit(1)

    date_str = sys.argv[1]

    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{date_str}'. Use YYYY-MM-DD.")
        sys.exit(1)

    print(f"[main] Starting scrape for {date_str}")

    # Initialize database
    db.init_db()

    # Run the scraper
    raw_rows = asyncio.run(scrape_margin(date_str))

    if not raw_rows:
        print(f"[main] No data returned for {date_str}")
        sys.exit(0)

    print(f"[main] Got {len(raw_rows)} raw rows")
    if raw_rows:
        print(f"[main] Sample raw row: {json.dumps(raw_rows[0], indent=2)}")

    # Normalize and store
    saved = 0
    skipped = 0

    for raw_row in raw_rows:
        normalized = normalize_row(raw_row, date_str)
        if normalized is None:
            skipped += 1
            continue

        # Values from API are already floats, but parse_pct handles both
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
        else:
            skipped += 1

    print(f"[main] Saved: {saved}, Skipped: {skipped}")

    # Show a sample of what was saved
    if saved > 0:
        records = db.get_margins(date=date_str)
        print(f"\n[main] Sample records for {date_str} (first 10):")
        print(f"{'Symbol':<15} {'Expiry':<12} {'IM%':>8} {'ELM%':>8} {'Total%':>8}")
        print("-" * 55)
        for rec in records[:10]:
            im = f"{rec['initial_margin_pct']:.2f}" if rec['initial_margin_pct'] is not None else "N/A"
            elm = f"{rec['elm_pct']:.2f}" if rec['elm_pct'] is not None else "N/A"
            total = f"{rec['total_margin_pct']:.2f}" if rec['total_margin_pct'] is not None else "N/A"
            print(f"{rec['symbol']:<15} {rec['expiry']:<12} {im:>8} {elm:>8} {total:>8}")


if __name__ == "__main__":
    main()
