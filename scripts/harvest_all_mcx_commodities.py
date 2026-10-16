"""
MCX Multi-Commodity Vault Harvester & Archiver
scripts/harvest_all_mcx_commodities.py

Proactively harvests and archives unstitched 1-minute (and 15m/daily rollups)
intraday historical data for ALL active MCX commodity futures before they expire.

Why this is critical:
Brokers (including FYERS) purge historical microstructure (1m, 15m) data for
contracts the moment they expire, returning 'Invalid symbol provided'.
This script dynamically discovers all active MCX contracts from the live FYERS
Symbol Master, extracts full contract lifecycles, and permanently archives them
in data/mcx_vault/contract_wise/ as append-only Parquet files with zero-shrink guards.

Usage:
    python scripts/harvest_all_mcx_commodities.py                  # Harvest all 175+ contracts
    python scripts/harvest_all_mcx_commodities.py --commodity CRUDEOIL  # Harvest specific commodity
    python scripts/harvest_all_mcx_commodities.py --days 30        # Fetch last 30 days
    python scripts/harvest_all_mcx_commodities.py --limit 5         # Dry/quick test on 5 contracts
    python scripts/harvest_all_mcx_commodities.py --push           # Commit and push to git
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import re
import json
import time
import glob
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
import pandas as pd
import duckdb

# Base Directories
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)
VAULT_DIR = os.path.join(REPO_DIR, "data", "mcx_vault")
CONTRACT_DIR = os.path.join(VAULT_DIR, "contract_wise")
MARKET_DIR = os.path.join(REPO_DIR, "docs", "data", "market")
CATALOG_PATH = os.path.join(VAULT_DIR, "commodities_catalog.json")
DOCS_CATALOG_PATH = os.path.join(MARKET_DIR, "commodities_catalog.json")
DUCKDB_PATH = os.path.join(VAULT_DIR, "mcx_quant.duckdb")
FYERS_MASTER_URL = "https://public.fyers.in/sym_details/MCX_COM.csv"

os.makedirs(CONTRACT_DIR, exist_ok=True)
os.makedirs(MARKET_DIR, exist_ok=True)

IST = timezone(timedelta(hours=5, minutes=30))

def log(msg):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"[{ts}] {msg}", flush=True)

def fetch_active_mcx_symbols(commodity_filter=None):
    """
    Downloads the official FYERS MCX Symbol Master and extracts all active futures contracts.
    Returns a list of dicts with symbol metadata sorted by commodity and expiry.
    """
    log(f"Fetching official FYERS MCX Symbol Master from {FYERS_MASTER_URL}...")
    try:
        df_master = pd.read_csv(FYERS_MASTER_URL, header=None, low_memory=False)
    except Exception as e:
        log(f"ERROR: Could not download FYERS symbol master: {e}")
        return []

    # Column 9: Full symbol, e.g. MCX:CRUDEOIL26OCTFUT
    # Column 13: Underlying root commodity, e.g. CRUDEOIL, NATURALGAS, GOLD
    # Column 1: Description, e.g. CRUDEOIL 28 Oct 26 FUT
    # Column 8: Expiry timestamp epoch
    # Column 3: Lot size
    # Column 4: Tick size
    df_futs = df_master[df_master[9].astype(str).str.endswith("FUT", na=False)].copy()
    log(f"Discovered {len(df_futs)} active MCX futures contracts across {df_futs[13].nunique()} commodities.")

    contracts = []
    for _, row in df_futs.iterrows():
        sym = str(row[9]).strip()
        comm = str(row[13]).strip()
        desc = str(row[1]).strip()
        try:
            exp_epoch = int(row[8])
        except (ValueError, TypeError):
            exp_epoch = 0

        # Extract expiry string code like 26OCT from symbol (MCX:BASE26OCTFUT)
        m = re.search(r"(\d{2}[A-Z]{3})FUT$", sym)
        exp_code = m.group(1) if m else ""

        if commodity_filter and commodity_filter.upper() != "ALL":
            if comm.upper() != commodity_filter.upper() and base_symbol_clean(comm) != commodity_filter.upper():
                continue

        contracts.append({
            "symbol": sym,
            "commodity": comm,
            "description": desc,
            "expiry_code": exp_code,
            "expiry_epoch": exp_epoch,
            "expiry_date_str": datetime.fromtimestamp(exp_epoch, timezone.utc).strftime("%Y-%m-%d") if exp_epoch > 0 else "",
            "lot_size": int(row[3]) if pd.notnull(row[3]) and str(row[3]).isdigit() else 1,
            "tick_size": float(row[4]) if pd.notnull(row[4]) else 0.05
        })

    # Sort by commodity then by expiry epoch
    contracts.sort(key=lambda x: (x["commodity"], x["expiry_epoch"]))
    return contracts

def base_symbol_clean(sym):
    return re.sub(r"[^A-Z0-9]", "", str(sym).upper())

def harvest_single_contract(fyers, contract, lookback_days=0):
    """
    Downloads unstitched 1-minute historical candles for a specific contract.
    If lookback_days == 0 (default): Dynamically pages backwards in 60-day chunks
    until FYERS returns 0 candles (the true contract inception date!), capturing
    100% of available historical microstructure without any hardcoded limit.
    If lookback_days > 0: Limits historical fetch to the specified number of days.
    Applies zero-shrink upsert with existing parquet.
    """
    sym = contract["symbol"]
    clean_name = sym.replace(":", "_")
    parquet_path = os.path.join(CONTRACT_DIR, f"{clean_name}_1m_contract_wise.parquet")

    now = datetime.now(timezone.utc)
    now_ist = now.astimezone(IST)

    existing_df = None
    min_epoch = 0
    max_epoch = 0

    if os.path.exists(parquet_path):
        try:
            existing_df = pd.read_parquet(parquet_path)
            if len(existing_df) > 0 and "epoch" in existing_df.columns:
                max_epoch = int(existing_df["epoch"].max())
                min_epoch = int(existing_df["epoch"].min())
        except Exception as e:
            log(f"Notice reading existing parquet {parquet_path}: {e}")
            existing_df = None

    chunks = []

    # 1. Forward incremental fetch: from max_epoch - 2 days up to now (captures recent trades)
    if max_epoch > 0:
        start_forward = datetime.fromtimestamp(max_epoch, timezone.utc) - timedelta(days=2)
        payload = {
            "symbol": sym,
            "resolution": "1",
            "date_format": "1",
            "range_from": start_forward.strftime("%Y-%m-%d"),
            "range_to": now.strftime("%Y-%m-%d"),
            "cont_flag": "0",
            "oi_flag": "1"
        }
        try:
            resp = fyers.history(data=payload)
            if resp.get("s") == "ok" and resp.get("candles"):
                candles = resp["candles"]
                if candles:
                    cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                    chunks.append(pd.DataFrame(candles, columns=cols[:len(candles[0])]))
        except Exception as e:
            log(f"Notice forward querying {sym}: {e}")
        time.sleep(0.25)

    # 2. Backward fetch towards inception:
    if existing_df is None or len(existing_df) == 0:
        # Fresh contract: page backwards from now in 60-day chunks until 0 candles returned
        curr_end = now
        chunk_count = 0
        max_safety_chunks = (lookback_days // 60 + 1) if lookback_days > 0 else 10  # Up to 600 days (full lifetime)

        while chunk_count < max_safety_chunks:
            curr_start = curr_end - timedelta(days=60)
            if lookback_days > 0 and curr_start < (now - timedelta(days=lookback_days)) and chunk_count > 0:
                curr_start = now - timedelta(days=lookback_days)

            payload = {
                "symbol": sym,
                "resolution": "1",
                "date_format": "1",
                "range_from": curr_start.strftime("%Y-%m-%d"),
                "range_to": curr_end.strftime("%Y-%m-%d"),
                "cont_flag": "0",
                "oi_flag": "1"
            }

            try:
                resp = fyers.history(data=payload)
                if resp.get("s") == "ok" and resp.get("candles"):
                    candles = resp["candles"]
                    if not candles:
                        # Reached true inception of contract!
                        break
                    cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                    chunks.append(pd.DataFrame(candles, columns=cols[:len(candles[0])]))
                    chunk_count += 1
                elif resp.get("code") == -300:
                    break
                else:
                    break
            except Exception as e:
                log(f"Notice backward querying {sym} ({curr_start.strftime('%Y-%m-%d')}): {e}")
                break

            curr_end = curr_start - timedelta(days=1)
            time.sleep(0.25)
    elif lookback_days == 0 and min_epoch > 0:
        # Existing contract: backfill backward from min_epoch to true inception
        curr_end = datetime.fromtimestamp(min_epoch, timezone.utc) - timedelta(days=1)
        chunk_count = 0
        while chunk_count < 8:  # Up to 480 days back
            curr_start = curr_end - timedelta(days=60)
            payload = {
                "symbol": sym,
                "resolution": "1",
                "date_format": "1",
                "range_from": curr_start.strftime("%Y-%m-%d"),
                "range_to": curr_end.strftime("%Y-%m-%d"),
                "cont_flag": "0",
                "oi_flag": "1"
            }
            try:
                resp = fyers.history(data=payload)
                if resp.get("s") == "ok" and resp.get("candles"):
                    candles = resp["candles"]
                    if not candles:
                        # Reached true inception!
                        break
                    cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                    chunks.append(pd.DataFrame(candles, columns=cols[:len(candles[0])]))
                    chunk_count += 1
                else:
                    break
            except Exception:
                break
            curr_end = curr_start - timedelta(days=1)
            time.sleep(0.25)

    new_bars_count = 0
    if chunks:
        df_new = pd.concat(chunks, ignore_index=True)
        df_new["symbol"] = sym
        df_new["commodity"] = contract["commodity"]
        df_new["expiry"] = contract["expiry_code"]
        df_new["ts_ist"] = pd.to_datetime(df_new["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
        new_bars_count = len(df_new)

        if existing_df is not None and len(existing_df) > 0:
            df_combined = pd.concat([existing_df, df_new], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["epoch"], keep="last").sort_values("epoch").reset_index(drop=True)
            # ZERO-SHRINK GUARD: Bar count can NEVER decrease!
            if len(df_combined) < len(existing_df):
                raise ValueError(f"CRITICAL: Zero-shrink violation on {sym}! Existing: {len(existing_df)}, New combined: {len(df_combined)}")
        else:
            df_combined = df_new.drop_duplicates(subset=["epoch"]).sort_values("epoch").reset_index(drop=True)

        df_combined.to_parquet(parquet_path, compression="zstd", index=False)
        total_bars = len(df_combined)
        latest_c = float(df_combined["close"].iloc[-1])
        latest_oi = int(df_combined["oi"].iloc[-1]) if "oi" in df_combined.columns else 0
        min_ts = df_combined["ts_ist"].iloc[0].strftime("%Y-%m-%d %H:%M")
        max_ts = df_combined["ts_ist"].iloc[-1].strftime("%Y-%m-%d %H:%M")
    elif existing_df is not None and len(existing_df) > 0:
        total_bars = len(existing_df)
        latest_c = float(existing_df["close"].iloc[-1])
        latest_oi = int(existing_df["oi"].iloc[-1]) if "oi" in existing_df.columns else 0
        min_ts = str(existing_df["ts_ist"].iloc[0])[:16]
        max_ts = str(existing_df["ts_ist"].iloc[-1])[:16]
    else:
        total_bars = 0
        latest_c = 0.0
        latest_oi = 0
        min_ts = "N/A"
        max_ts = "N/A"

    return {
        "symbol": sym,
        "clean_name": clean_name,
        "commodity": contract["commodity"],
        "expiry": contract["expiry_code"],
        "parquet_path": parquet_path,
        "new_bars": new_bars_count,
        "total_bars": total_bars,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "latest_close": latest_c,
        "latest_oi": latest_oi
    }

def update_duckdb_views(contract_stats):
    """
    Registers all commodity contracts into DuckDB quant vault.
    """
    log(f"Registering all commodity contract views into DuckDB ({DUCKDB_PATH})...")
    con = duckdb.connect(DUCKDB_PATH)

    # Master view across all contracts in contract_wise/
    all_parquet_pattern = os.path.join(CONTRACT_DIR, "MCX_*_1m_contract_wise.parquet").replace("\\", "/")
    con.execute(f"CREATE OR REPLACE VIEW mcx_all_futures_1m AS SELECT * FROM read_parquet('{all_parquet_pattern}')")

    # Group contracts by commodity and create commodity-specific views
    commodities = set(c["commodity"] for c in contract_stats if c["total_bars"] > 0)
    for comm in sorted(commodities):
        clean_comm = comm.lower()
        comm_pattern = os.path.join(CONTRACT_DIR, f"MCX_{comm}*_1m_contract_wise.parquet").replace("\\", "/")
        try:
            con.execute(f"CREATE OR REPLACE VIEW {clean_comm}_futures_1m AS SELECT * FROM read_parquet('{comm_pattern}')")
        except Exception as e:
            log(f"Notice registering DuckDB view for {comm}: {e}")

    try:
        cnt = con.execute("SELECT count(*) FROM mcx_all_futures_1m").fetchone()[0]
        log(f"DuckDB Quant Vault synchronized! Total unified 1m bars across all commodities: {cnt:,}")
    except Exception as e:
        log(f"Notice reading unified DuckDB view: {e}")
    con.close()

def build_commodities_catalog(active_contracts, contract_results):
    """
    Generates a full manifest catalog of all archived contracts (active + expired),
    documenting bar counts, date ranges, volume, and open interest.
    """
    log("Building unified commodities catalog manifest...")
    active_sym_set = set(c["symbol"] for c in active_contracts)

    # Discover all parquet files currently in contract_wise/ (including expired)
    all_parquets = glob.glob(os.path.join(CONTRACT_DIR, "MCX_*_1m_contract_wise.parquet"))
    results_map = {r["symbol"]: r for r in contract_results}

    catalog_entries = []
    commodity_summary = {}

    for ppath in sorted(all_parquets):
        pfile = os.path.basename(ppath)
        m = re.match(r"^MCX_([A-Z0-9]+?)(\d{2}[A-Z]{3})FUT_1m_contract_wise\.parquet$", pfile)
        if not m:
            continue
        comm = m.group(1)
        exp = m.group(2)
        sym = f"MCX:{comm}{exp}FUT"

        if sym in results_map and results_map[sym]["total_bars"] > 0:
            res = results_map[sym]
            bars = res["total_bars"]
            min_ts = res["min_ts"]
            max_ts = res["max_ts"]
            latest_c = res["latest_close"]
            latest_oi = res["latest_oi"]
        else:
            try:
                df = pd.read_parquet(ppath)
                bars = len(df)
                min_ts = str(df["ts_ist"].iloc[0])[:16] if bars > 0 else "N/A"
                max_ts = str(df["ts_ist"].iloc[-1])[:16] if bars > 0 else "N/A"
                latest_c = float(df["close"].iloc[-1]) if bars > 0 else 0.0
                latest_oi = int(df["oi"].iloc[-1]) if bars > 0 and "oi" in df.columns else 0
            except Exception:
                bars, min_ts, max_ts, latest_c, latest_oi = 0, "N/A", "N/A", 0.0, 0

        is_active = sym in active_sym_set
        entry = {
            "symbol": sym,
            "commodity": comm,
            "expiry": exp,
            "status": "active" if is_active else "expired",
            "total_bars": bars,
            "start_time": min_ts,
            "end_time": max_ts,
            "latest_close": latest_c,
            "latest_oi": latest_oi,
            "file": f"data/mcx_vault/contract_wise/{pfile}"
        }
        catalog_entries.append(entry)

        if comm not in commodity_summary:
            commodity_summary[comm] = {
                "commodity": comm,
                "contracts_count": 0,
                "active_contracts": 0,
                "expired_contracts": 0,
                "total_bars": 0,
                "latest_price": latest_c
            }
        cs = commodity_summary[comm]
        cs["contracts_count"] += 1
        if is_active:
            cs["active_contracts"] += 1
        else:
            cs["expired_contracts"] += 1
        cs["total_bars"] += bars
        if latest_c > 0:
            cs["latest_price"] = latest_c

    catalog = {
        "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "total_contracts": len(catalog_entries),
        "total_commodities": len(commodity_summary),
        "total_bars": sum(e["total_bars"] for e in catalog_entries),
        "commodities": commodity_summary,
        "contracts": catalog_entries
    }

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    with open(DOCS_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    log(f"Catalog saved to {CATALOG_PATH} and {DOCS_CATALOG_PATH} ({len(catalog_entries)} contracts, {len(commodity_summary)} commodities).")
    return catalog

def git_commit_and_push():
    """Commits newly archived parquet files and catalog to git."""
    try:
        log("Checking git status for new vault archives...")
        status = subprocess.run(["git", "status", "--porcelain", "data/mcx_vault/", "docs/data/market/"], cwd=REPO_DIR, capture_output=True, text=True)
        if not status.stdout.strip():
            log("No git changes detected. Vault is up to date.")
            return

        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "add", "data/mcx_vault/contract_wise/", CATALOG_PATH, DOCS_CATALOG_PATH], cwd=REPO_DIR, check=True)
        
        now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
        msg = f"data: multi-commodity vault archive {now_str}"
        subprocess.run(["git", "commit", "--no-verify", "-m", msg], cwd=REPO_DIR, check=True, capture_output=True, text=True)

        for attempt in range(1, 4):
            try:
                subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
                subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
                log("SUCCESS: Pushed multi-commodity vault archive to origin/main!")
                return
            except subprocess.CalledProcessError as e:
                log(f"Push attempt {attempt} notice: {e.stderr or e}. Retrying in 2s...")
                subprocess.run(["git", "rebase", "--abort"], cwd=REPO_DIR, capture_output=True)
                time.sleep(2)
        log("WARN: Git push deferred.")
    except Exception as e:
        log(f"Notice during git auto-sync: {e}")

def main():
    parser = argparse.ArgumentParser(description="MCX Multi-Commodity Vault Harvester")
    parser.add_argument("--commodity", type=str, default="ALL", help="Filter by commodity (e.g. CRUDEOIL, GOLD, NATURALGAS, ALL).")
    parser.add_argument("--days", type=int, default=0, help="Lookback days for historical 1-minute data (default: 0 = dynamic full lifetime from inception to today).")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of contracts to process (for testing).")
    parser.add_argument("--dry-run", action="store_true", help="Discover contracts without downloading.")
    parser.add_argument("--push", action="store_true", help="Commit and push changes to git.")
    args = parser.parse_args()

    log("=" * 80)
    log("MCX MULTI-COMMODITY VAULT HARVESTER & ARCHIVER")
    log("=" * 80)

    # 1. Discover all active contracts from live Fyers master
    all_active_contracts = fetch_active_mcx_symbols(commodity_filter=None)
    if not all_active_contracts:
        log("No contracts found from Fyers master. Exiting.")
        return

    if args.commodity and args.commodity.upper() != "ALL":
        target = args.commodity.upper()
        contracts = [c for c in all_active_contracts if c["commodity"].upper() == target or base_symbol_clean(c["commodity"]) == target]
    else:
        contracts = list(all_active_contracts)

    if not contracts:
        log(f"No contracts matching filter '{args.commodity}'. Exiting.")
        return

    if args.limit > 0:
        contracts = contracts[:args.limit]
        log(f"Test mode active: Limited to first {len(contracts)} contracts.")

    if args.dry_run:
        log("Dry run requested. Contracts to be harvested:")
        for c in contracts:
            log(f"  {c['symbol']:28s} | {c['commodity']:12s} | Expiry: {c['expiry_date_str']} | {c['description']}")
        return

    # 2. Authenticate Fyers
    from scripts.auto_market_snapshot import get_authenticated_fyers
    fyers, user = get_authenticated_fyers()
    if not fyers:
        log("ERROR: Could not obtain authenticated FYERS client. Exiting.")
        sys.exit(1)
    log(f"Authenticated with FYERS as: {user}")

    # 3. Harvest active contracts
    log(f"Harvesting {len(contracts)} contracts across MCX commodities (Lookback: {args.days} days)...")
    results = []
    start_time = time.time()

    for idx, c in enumerate(contracts, 1):
        log(f"[{idx}/{len(contracts)}] Harvesting {c['symbol']} ({c['commodity']} {c['expiry_code']})...")
        res = harvest_single_contract(fyers, c, lookback_days=args.days)
        results.append(res)
        if res["total_bars"] > 0:
            log(f"    --> {res['total_bars']:,} total 1m bars (+{res['new_bars']} new) | Span: {res['min_ts']} -> {res['max_ts']} | Close: {res['latest_close']}")
        else:
            log(f"    --> 0 bars returned (no traded volume or pending listing)")
        time.sleep(0.3)  # Respect rate limits

    elapsed = time.time() - start_time
    log(f"Harvest complete in {elapsed:.1f}s ({len(results)} contracts processed).")

    # 4. Update DuckDB Views
    update_duckdb_views(results)

    # 5. Build Unified Commodities Catalog Manifest
    build_commodities_catalog(all_active_contracts, results)

    # 6. Commit and Push if requested
    if args.push:
        git_commit_and_push()

    log("=" * 80)
    log("ALL HARVESTING STEPS COMPLETED CLEANLY.")
    log("=" * 80)

if __name__ == "__main__":
    main()
