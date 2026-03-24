"""
Lookback gap-fill: checks the last N weekdays and fetches any dates missing
from the database.

Safety net for the daily workflow — if the primary fetch_today.py run ever
fails or is skipped (GitHub Actions outage, network blip, bot detection),
this script catches the gap on the next run and backfills silently.

Only looks at PAST dates (yesterday and earlier); today is handled by
fetch_today.py.  Dates that return 0 records from the API are assumed to be
MCX holidays / non-trading days and are logged but not retried.

Exit codes:
  0 — one or more missing dates were successfully filled
  2 — no gaps found (everything present or confirmed empty from API)
"""

import asyncio
import sys
import argparse
from datetime import date, timedelta

import src.db as db
from src.scraper import scrape_margin, normalize_row, parse_pct

SYMBOLS_TO_STORE = {"NATURALGAS", "NATGASMINI"}


def past_weekdays(n: int) -> list[str]:
    """Return the last n weekday dates before today, newest first."""
    result = []
    d = date.today() - timedelta(days=1)
    while len(result) < n:
        if d.weekday() < 5:  # Mon=0 … Fri=4
            result.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    return result


def has_data(date_str: str) -> bool:
    return len(db.get_margins(date=date_str)) > 0


def fetch_and_store(date_str: str) -> int:
    """Fetch from mcxccl.com for date_str and store. Returns records saved."""
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
    parser = argparse.ArgumentParser(description="Gap-fill recent missing margin dates")
    parser.add_argument(
        "--days", type=int, default=5,
        help="How many past weekdays to audit (default: 5 = covers Mon–Fri + 1 buffer week)",
    )
    args = parser.parse_args()

    db.init_db()
    dates = past_weekdays(args.days)

    print(f"[lookback] Auditing {args.days} past weekdays: {dates}")

    total_filled = 0
    gaps = []
    holidays = []

    for date_str in dates:
        if has_data(date_str):
            print(f"[lookback] {date_str}: OK")
            continue

        gaps.append(date_str)
        print(f"[lookback] {date_str}: MISSING — fetching from mcxccl.com ...")
        saved = fetch_and_store(date_str)

        if saved > 0:
            print(f"[lookback] {date_str}: filled {saved} records")
            total_filled += saved
        else:
            # API returned nothing — MCX holiday or genuinely no trading that day
            print(f"[lookback] {date_str}: API returned 0 records — treating as holiday/non-trading day")
            holidays.append(date_str)

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("[lookback] ── Summary ──────────────────────────────────────────")
    print(f"[lookback]   Weekdays audited : {len(dates)}")
    print(f"[lookback]   Already present  : {len(dates) - len(gaps)}")
    print(f"[lookback]   Gaps found       : {len(gaps)}")
    if gaps:
        filled = [d for d in gaps if d not in holidays]
        print(f"[lookback]   Filled           : {filled} ({total_filled} records)")
        if holidays:
            print(f"[lookback]   Holidays/empty   : {holidays}")
    print("[lookback] ─────────────────────────────────────────────────────")

    sys.exit(0 if total_filled > 0 else 2)


if __name__ == "__main__":
    main()
