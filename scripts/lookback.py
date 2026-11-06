"""
Lookback gap-fill: checks past weekdays and fetches any dates missing
from the database.

Safety net for the daily workflow — if the primary fetch_today.py run ever
fails or is skipped (GitHub Actions outage, network blip, bot detection),
this script catches the gap on the next run and backfills silently.
Stores all MCX commodity futures, de-duplicated and normalized.

Exit codes:
  0 — one or more missing dates were successfully filled
  2 — no gaps found (everything present or confirmed empty from API)
"""

import asyncio
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

# Allow running as `python scripts/lookback.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.db as db
from src.scraper import scrape_margin, scrape_margins_bulk, normalize_row, parse_pct

EXCLUDED_SYMBOLS = {"MCXBULLDEX", "MCXMETLDEX"}


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
    """Check if multi-commodity margin data already exists in SQLite or historical Parquet vault."""
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT count(distinct symbol) FROM margins WHERE date = ?", (date_str,)).fetchone()
        if row and row[0] >= 10:
            return True
    finally:
        conn.close()

    # Check historical parquet vault for dates <= 2025
    yr = date_str[:4]
    p_file = Path("data/mcx_vault/historical/margins") / f"margins_{yr}.parquet"
    if p_file.exists():
        try:
            import duckdb
            c = duckdb.connect()
            r = c.execute(
                f"SELECT count(distinct symbol) FROM read_parquet('{p_file.as_posix()}') WHERE date = ?",
                (date_str,)
            ).fetchone()
            c.close()
            if r and r[0] >= 10:
                return True
        except Exception:
            pass
    return False


def process_and_store_records(raw_rows: list[dict], date_str: str) -> int:
    """Normalize and upsert raw rows into SQLite margins DB."""
    if not raw_rows:
        return 0

    normalized_rows = []
    for raw_row in raw_rows:
        normalized = normalize_row(raw_row, date_str)
        if normalized is None:
            continue

        sym = (normalized.get("symbol") or "").strip().upper()
        inst = (normalized.get("instrument_id") or "").strip().upper()
        if not sym or sym in EXCLUDED_SYMBOLS or inst == "FUTIDX":
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

        normalized_rows.append(normalized)

    if normalized_rows:
        return db.upsert_margins_batch(normalized_rows)
    return 0


def fetch_and_store(date_str: str) -> int:
    """Fetch from mcxccl.com for date_str and store. Returns records saved."""
    raw_rows = asyncio.run(scrape_margin(date_str))
    return process_and_store_records(raw_rows, date_str)


def main():
    parser = argparse.ArgumentParser(description="Gap-fill recent missing margin dates")
    parser.add_argument(
        "--days", type=int, default=5,
        help="How many past weekdays to audit (default: 5 = covers Mon–Fri + 1 buffer week)",
    )
    parser.add_argument(
        "--from-date", type=str, default=None,
        help="Start date YYYY-MM-DD for backfill to yesterday",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-fetching even if date is present in DB",
    )
    args = parser.parse_args()

    db.init_db()

    if args.from_date:
        start_d = date.fromisoformat(args.from_date)
        end_d = date.today() - timedelta(days=1)
        cur = start_d
        dates = []
        while cur <= end_d:
            if cur.weekday() < 5:
                dates.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)
        dates.reverse()
    else:
        dates = past_weekdays(args.days)

    print(f"[lookback] Auditing {len(dates)} weekdays: {dates[:5]}{'...' if len(dates) > 5 else ''}")

    missing_dates = []
    for date_str in dates:
        if not args.force and has_data(date_str):
            continue
        missing_dates.append(date_str)

    if not missing_dates:
        print("[lookback] All dates have complete multi-commodity data. Nothing to fetch.")
        sys.exit(2)

    print(f"[lookback] Missing or requested dates: {len(missing_dates)}. Initiating batch fetch...")

    # Use single-session bulk scraper for efficiency
    bulk_results = asyncio.run(scrape_margins_bulk(missing_dates))

    total_filled = 0
    holidays = []
    filled = []

    for date_str in missing_dates:
        raw_rows = bulk_results.get(date_str, [])
        saved = process_and_store_records(raw_rows, date_str)
        if saved > 0:
            print(f"[lookback] {date_str}: filled {saved} records")
            total_filled += saved
            filled.append(date_str)
        else:
            print(f"[lookback] {date_str}: 0 records saved (holiday / non-trading)")
            holidays.append(date_str)

    # -- Summary --------------------------------------------------------------
    print()
    print("[lookback] -- Summary ------------------------------------------")
    print(f"[lookback]   Audited          : {len(dates)}")
    print(f"[lookback]   Targeted missing : {len(missing_dates)}")
    print(f"[lookback]   Filled           : {len(filled)} dates ({total_filled} records)")
    if holidays:
        print(f"[lookback]   Holidays/empty   : {len(holidays)} dates")
    print("[lookback] -----------------------------------------------------")

    sys.exit(0 if total_filled > 0 else 2)


if __name__ == "__main__":
    main()
