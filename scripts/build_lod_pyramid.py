"""
build_lod_pyramid.py
--------------------
Builds and maintains the Multi-Resolution Level-of-Detail (LOD) dataset pyramid.

Modes:
1. Full Rebuild Mode (Local with Vault):
   When data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet exists,
   resamples and exports:
   - Tier 0: docs/data/deep/ng_daily.json   (Full 8-year daily macro bars: ~1,940 bars)
   - Tier 1: docs/data/deep/ng_1h.json      (Full 8-year 1-hour swing bars: ~28,200 bars)
   - Tier 2: docs/data/deep/ng_15m.json     (Trailing 2-year 15-minute bars: ~26,300 bars)
   - Tier 3: docs/data/deep/1m/<YYYY_MM>.json (Monthly 1-minute microstructure chunks)

2. Cloud CI Incremental Mode (GitHub Actions):
   When run without the 100MB vault parquet, it connects to data/prices.db
   (which is updated daily by fetch_prices.py) and appends new daily settlement
   bars to docs/data/deep/ng_daily.json. This keeps the deep chart updated
   100% automatically on GitHub Actions without manual backfills.
"""

import json
import os
import sys
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

VAULT_DIR = Path("data/mcx_vault")
PRICE_DB = Path("data/prices.db")
OUTPUT_DIR = Path("docs/data/deep")

def find_vault_parquet(name: str) -> Path:
    """Dynamically locates the continuous 1-minute vault parquet, adapting to any year range."""
    candidates = sorted(VAULT_DIR.glob(f"{name}_1m_continuous_*.parquet"))
    if candidates:
        return candidates[-1]
    return VAULT_DIR / f"{name}_1m_continuous_2019_2026.parquet"

def find_contract_wise_parquets(name: str) -> list[Path]:
    """Dynamically discovers all contract-wise 1m parquets for the commodity (active and future)."""
    contract_dir = VAULT_DIR / "contract_wise"
    if not contract_dir.exists():
        return []
    return sorted(contract_dir.glob(f"MCX_{name}*FUT_1m_contract_wise.parquet"))

SYMBOLS_CONFIG = [
    {
        "name": "NATURALGAS",
        "prefix": "ng",
        "vault_parquet": find_vault_parquet("NATURALGAS"),
        "dir_1m": OUTPUT_DIR / "1m",
        "manifest_1m_prefix": "data/deep/1m"
    },
    {
        "name": "NATGASMINI",
        "prefix": "ngm",
        "vault_parquet": find_vault_parquet("NATGASMINI"),
        "dir_1m": OUTPUT_DIR / "1m_ngm",
        "manifest_1m_prefix": "data/deep/1m_ngm"
    }
]

def update_daily_incremental_for_sym(sym_cfg):
    """Updates docs/data/deep/{prefix}_daily.json using data/prices.db in CI."""
    if not PRICE_DB.exists():
        print(f"Warning: Neither vault parquet nor {PRICE_DB} exists for {sym_cfg['name']}. Skipping.")
        return

    daily_json = OUTPUT_DIR / f"{sym_cfg['prefix']}_daily.json"
    if not daily_json.exists():
        print(f"Warning: {daily_json} does not exist to update incrementally.")
        return

    print(f"Running in CI Incremental Mode: Updating {daily_json.name} from prices.db...")
    with open(daily_json, "r") as f:
        daily_bars = json.load(f)

    latest_epoch = daily_bars[-1]["time"] if daily_bars else 0
    latest_dt = pd.to_datetime(latest_epoch, unit="s", utc=True).tz_convert("Asia/Kolkata")
    latest_date_str = latest_dt.strftime("%Y-%m-%d")
    print(f"Latest bar in {daily_json.name}: {latest_date_str} (epoch {latest_epoch})")

    conn = sqlite3.connect(PRICE_DB)
    query = """
        SELECT date, open, high, low, close, volume_lots as volume
        FROM prices
        WHERE symbol = ? AND instrument = 'FUTCOM' AND date >= ?
        ORDER BY date ASC, volume_lots DESC
    """
    df = pd.read_sql_query(query, conn, params=(sym_cfg["name"], latest_date_str))
    conn.close()

    if df.empty:
        print(f"No newer price data found for {sym_cfg['name']} in prices.db.")
        return

    df = df.drop_duplicates(subset=["date"], keep="first")
    added = 0
    existing_epochs = {b["time"] for b in daily_bars}
    existing_dates = {
        pd.to_datetime(b["time"], unit="s", utc=True).tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
        for b in daily_bars
    }
    for _, row in df.iterrows():
        row_date = str(row["date"])
        ts = pd.Timestamp(f"{row_date} 09:00:00", tz="Asia/Kolkata")
        epoch_sec = int(ts.timestamp())
        if epoch_sec not in existing_epochs and row_date not in existing_dates and row["close"] > 0:
            daily_bars.append({
                "time": epoch_sec,
                "open": round(float(row["open"] if row["open"] > 0 else row["close"]), 2),
                "high": round(float(row["high"] if row["high"] > 0 else row["close"]), 2),
                "low": round(float(row["low"] if row["low"] > 0 else row["close"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"])
            })
            existing_epochs.add(epoch_sec)
            existing_dates.add(row_date)
            added += 1

    if added > 0:
        daily_bars.sort(key=lambda x: x["time"])
        with open(daily_json, "w") as f:
            json.dump(daily_bars, f, separators=(',', ':'))
        print(f"Successfully added {added} new trading day(s) to {daily_json}. Total bars: {len(daily_bars)}")
    else:
        print(f"{daily_json.name} is already completely up to date.")

def build_symbol_pyramid(sym_cfg):
    """Builds full 3-tier LOD pyramid for a specific symbol configuration."""
    vault_parquet = sym_cfg["vault_parquet"]
    if not vault_parquet.exists():
        print(f"Vault parquet not found for {sym_cfg['name']} ({vault_parquet}). Skipping.")
        return None

    print(f"\n[{sym_cfg['name']}] Loading vault: {vault_parquet}...")
    df = pd.read_parquet(vault_parquet)
    print(f"[{sym_cfg['name']}] Loaded {len(df):,} raw bars from vault.")

    # Dynamically merge all available contract-wise 1m bars
    contract_files = find_contract_wise_parquets(sym_cfg["name"])
    if contract_files:
        print(f"[{sym_cfg['name']}] Merging {len(contract_files)} contract-wise parquets into LOD pyramid...")
        merged_count = 0
        for cp in contract_files:
            try:
                df_cp = pd.read_parquet(cp)
                df = pd.concat([df, df_cp], ignore_index=True)
                merged_count += len(df_cp)
            except Exception as e:
                print(f"[{sym_cfg['name']}] Notice merging {cp.name}: {e}")
        df = df.drop_duplicates(subset=["epoch"], keep="last").sort_values("epoch").reset_index(drop=True)
        print(f"[{sym_cfg['name']}] Successfully merged {merged_count:,} contract bars across all active/future contracts (Total: {len(df):,}).")

    df["dt"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dir_1m = sym_cfg["dir_1m"]
    dir_1m.mkdir(parents=True, exist_ok=True)
    prefix = sym_cfg["prefix"]

    # ── Tier 0: Daily ──
    print(f"[{sym_cfg['name']}] Resampling Daily tier...")
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    daily_bars = []
    for dt, row in daily.iterrows():
        daily_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    daily_file = OUTPUT_DIR / f"{prefix}_daily.json"
    with open(daily_file, "w") as f:
        json.dump(daily_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 0 Daily: {len(daily_bars):,} bars -> {daily_file.name} ({daily_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 1: 1-Hour ──
    print(f"[{sym_cfg['name']}] Resampling 1-Hour tier...")
    h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    h1_bars = []
    for dt, row in h1.iterrows():
        h1_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    h1_file = OUTPUT_DIR / f"{prefix}_1h.json"
    with open(h1_file, "w") as f:
        json.dump(h1_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 1 1-Hour: {len(h1_bars):,} bars -> {h1_file.name} ({h1_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 2: 15-Minute (Trailing 24 Months) ──
    latest_dt = df.index.max()
    cutoff_24m = (latest_dt - pd.DateOffset(months=24)).strftime("%Y-%m-01")
    print(f"[{sym_cfg['name']}] Resampling 15-Minute tier (from {cutoff_24m} to {latest_dt.strftime('%Y-%m-%d')})...")
    df_recent = df[df.index >= cutoff_24m]
    m15 = df_recent.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    m15_bars = []
    for dt, row in m15.iterrows():
        m15_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    m15_file = OUTPUT_DIR / f"{prefix}_15m.json"
    with open(m15_file, "w") as f:
        json.dump(m15_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 2 15-Minute: {len(m15_bars):,} bars -> {m15_file.name} ({m15_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 3: 1-Minute Monthly Chunks (Trailing 12 Months) ──
    cutoff_12m = (latest_dt - pd.DateOffset(months=12)).strftime("%Y-%m-01")
    print(f"[{sym_cfg['name']}] Generating Tier 3 Monthly 1-Minute chunks for trailing 12 months (from {cutoff_12m})...")
    df_1m = df[df.index >= cutoff_12m].copy()
    df_1m["ym"] = df_1m.index.strftime("%Y_%m")

    manifest_1m = []
    for ym, group in df_1m.groupby("ym"):
        month_bars = []
        for dt, row in group.iterrows():
            month_bars.append([
                int(row["epoch"]),
                round(float(row["open"]), 2),
                round(float(row["high"]), 2),
                round(float(row["low"]), 2),
                round(float(row["close"]), 2),
                int(row["volume"])
            ])
        target_file = dir_1m / f"{ym}.json"
        with open(target_file, "w") as f:
            json.dump(month_bars, f, separators=(',', ':'))
        print(f"  [{sym_cfg['name']}] Month {ym}: {len(month_bars):,} 1m bars -> {target_file.name} ({target_file.stat().st_size / 1024:.1f} KB)")
        manifest_1m.append({
            "month": ym,
            "bars": len(month_bars),
            "start": int(group["epoch"].iloc[0]),
            "end": int(group["epoch"].iloc[-1]),
            "file": f"{sym_cfg['manifest_1m_prefix']}/{ym}.json"
        })

    return {
        "daily": {"file": f"data/deep/{prefix}_daily.json", "bars": len(daily_bars)},
        "h1": {"file": f"data/deep/{prefix}_1h.json", "bars": len(h1_bars)},
        "m15": {"file": f"data/deep/{prefix}_15m.json", "bars": len(m15_bars)},
        "m1_months": manifest_1m
    }

def full_vault_rebuild():
    """Builds full LOD pyramids for both NATURALGAS and NATGASMINI."""
    manifest_data = {}
    for sym_cfg in SYMBOLS_CONFIG:
        meta = build_symbol_pyramid(sym_cfg)
        if meta:
            manifest_data[sym_cfg["prefix"]] = meta

    manifest_file = OUTPUT_DIR / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"\nManifest successfully updated -> {manifest_file}")

def main():
    has_any_vault = any(cfg["vault_parquet"].exists() for cfg in SYMBOLS_CONFIG)
    if has_any_vault and "--incremental" not in sys.argv:
        full_vault_rebuild()
    else:
        for sym_cfg in SYMBOLS_CONFIG:
            update_daily_incremental_for_sym(sym_cfg)

if __name__ == "__main__":
    main()
