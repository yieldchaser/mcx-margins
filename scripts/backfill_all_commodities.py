#!/usr/bin/env python3
"""
scripts/backfill_all_commodities.py
High-speed, resilient multi-commodity backfiller for:
1. MCX Bhavcopy EOD prices (back to 2007) -> data/prices.db
2. MCX CCL Daily Margins (back to 2010) -> data/margins.db
"""

import sys
import os
import time
import json
import asyncio
import sqlite3
import argparse
from datetime import datetime, date, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import src.db as db
from src.scraper import scrape_margins_bulk, normalize_row, parse_pct
EXCLUDED_SYMBOLS = {'MCXBULLDEX', 'MCXMETLDEX', 'BULLDEX', 'METLDEX'}
from scripts.fetch_prices import BhavSession, normalize as normalize_price, save_records, db_connect, async_playwright

PRICES_DB_PATH = os.path.join(REPO_ROOT, "data", "prices.db")
MARGINS_DB_PATH = os.path.join(REPO_ROOT, "data", "margins.db")

IST = timezone(timedelta(hours=5, minutes=30))

def log(msg):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"[{ts}] {msg}", flush=True)

def get_pending_price_dates(conn, start_date="2007-01-01", end_date=None, min_symbols=10):
    """Find all weekday dates between start_date and end_date missing multi-commodity data."""
    if end_date is None:
        end_date = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Existing complete dates
    complete_dates = {
        r[0] for r in conn.execute(
            "SELECT date FROM prices GROUP BY date HAVING count(distinct symbol) >= ?",
            (min_symbols,)
        ).fetchall()
    }
    
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    pending = []
    while cur <= end_dt:
        if cur.weekday() < 5:
            d_str = cur.strftime("%Y-%m-%d")
            if d_str not in complete_dates:
                pending.append(d_str)
        cur += timedelta(days=1)
    return pending

def get_pending_margin_dates(conn, start_date="2010-01-01", end_date=None, min_symbols=10):
    """Find all weekday dates between start_date and end_date missing multi-commodity margin data."""
    if end_date is None:
        end_date = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
        
    complete_dates = {
        r[0] for r in conn.execute(
            "SELECT date FROM margins GROUP BY date HAVING count(distinct symbol) >= ?",
            (min_symbols,)
        ).fetchall()
    }
    
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    pending = []
    while cur <= end_dt:
        if cur.weekday() < 5:
            d_str = cur.strftime("%Y-%m-%d")
            if d_str not in complete_dates:
                pending.append(d_str)
        cur += timedelta(days=1)
    return pending

async def backfill_prices(dates, chunk_size=50):
    """Backfill Bhavcopy prices in browser session chunks."""
    if not dates:
        log("No pending Bhavcopy dates to backfill.")
        return 0

    log(f"Starting Bhavcopy backfill for {len(dates)} dates in chunks of {chunk_size}...")
    conn = db_connect(PRICES_DB_PATH)
    total_saved = 0

    for chunk_idx in range(0, len(dates), chunk_size):
        chunk = dates[chunk_idx:chunk_idx + chunk_size]
        log(f"Bhavcopy Chunk {chunk_idx // chunk_size + 1}: {len(chunk)} dates ({chunk[0]} to {chunk[-1]})")
        
        async with async_playwright() as p:
            session = BhavSession(p)
            try:
                await session.start()
            except Exception as e:
                log(f"Error starting BhavSession: {e}")
                continue

            for i, d_str in enumerate(chunk, 1):
                t0 = time.time()
                try:
                    raw_rows = await session.fetch_date(d_str)
                    normalized = [r for raw in raw_rows if (r := normalize_price(raw, d_str))]
                except Exception as e:
                    log(f"  [{i}/{len(chunk)}] {d_str}: error {e}")
                    continue

                if normalized:
                    saved = save_records(conn, normalized)
                    total_saved += saved
                    syms = len({r['symbol'] for r in normalized})
                    elapsed = time.time() - t0
                    log(f"  [{i}/{len(chunk)}] {d_str}: {saved} rows, {syms} symbols ({elapsed:.2f}s)")
                else:
                    log(f"  [{i}/{len(chunk)}] {d_str}: 0 rows (holiday/closed)")
                
                await asyncio.sleep(0.1) # Gentle pacing
            
            await session.close()
            
    conn.close()
    log(f"Bhavcopy backfill finished: total {total_saved} rows saved.")
    return total_saved

async def backfill_margins(dates, chunk_size=50):
    """Backfill MCX CCL margins in stealth browser chunks."""
    if not dates:
        log("No pending margin dates to backfill.")
        return 0

    log(f"Starting MCX CCL Margins backfill for {len(dates)} dates in chunks of {chunk_size}...")
    total_saved = 0

    for chunk_idx in range(0, len(dates), chunk_size):
        chunk = dates[chunk_idx:chunk_idx + chunk_size]
        log(f"Margins Chunk {chunk_idx // chunk_size + 1}: {len(chunk)} dates ({chunk[0]} to {chunk[-1]})")
        
        results = await scrape_margins_bulk(chunk)
        
        for d_str, raw_rows in results.items():
            if not raw_rows:
                log(f"  {d_str}: 0 margin records (holiday/closed)")
                continue

            normalized_rows = []
            for raw_row in raw_rows:
                normalized = normalize_row(raw_row, d_str)
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
                saved = db.upsert_margins_batch(normalized_rows)
                total_saved += saved
                syms = len({r['symbol'] for r in normalized_rows})
                log(f"  {d_str}: {saved} rows, {syms} symbols saved")
            else:
                log(f"  {d_str}: 0 valid commodity rows")

    log(f"Margins backfill finished: total {total_saved} rows saved.")
    return total_saved

def main():
    parser = argparse.ArgumentParser(description="Multi-Commodity Historical Backfill Pipeline")
    parser.add_argument("--mode", choices=["prices", "margins", "all"], default="all")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--reverse", action="store_true", help="Backfill from most recent to oldest (recommended)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of dates to process")
    parser.add_argument("--chunk", type=int, default=40, help="Dates per session chunk")
    args = parser.parse_args()

    db.init_db()

    # Default start dates
    p_start = args.start or "2007-01-01"
    m_start = args.start or "2010-01-01"

    if args.mode in ["prices", "all"]:
        conn_p = db_connect(PRICES_DB_PATH)
        p_dates = get_pending_price_dates(conn_p, start_date=p_start, end_date=args.end)
        conn_p.close()
        if args.reverse:
            p_dates.reverse()
        if args.limit > 0:
            p_dates = p_dates[:args.limit]
        log(f"Discovered {len(p_dates)} pending Bhavcopy price dates (Range: {p_start} to {args.end or 'today'})")
        asyncio.run(backfill_prices(p_dates, chunk_size=args.chunk))

    if args.mode in ["margins", "all"]:
        conn_m = sqlite3.connect(MARGINS_DB_PATH)
        m_dates = get_pending_margin_dates(conn_m, start_date=m_start, end_date=args.end)
        conn_m.close()
        if args.reverse:
            m_dates.reverse()
        if args.limit > 0:
            m_dates = m_dates[:args.limit]
        log(f"Discovered {len(m_dates)} pending MCX CCL margin dates (Range: {m_start} to {args.end or 'today'})")
        asyncio.run(backfill_margins(m_dates, chunk_size=args.chunk))

if __name__ == "__main__":
    main()
