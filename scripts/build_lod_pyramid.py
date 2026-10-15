"""
build_lod_pyramid.py
--------------------
Builds a Multi-Resolution Level-of-Detail (LOD) dataset pyramid from the
8-year continuous Natural Gas 1-minute vault (2019-2026, 1.65M candles).

Tiers generated:
- Tier 0: docs/data/deep/ng_daily.json   (Full 8-year daily macro bars: ~1,940 bars, ~50 KB)
- Tier 1: docs/data/deep/ng_1h.json      (Full 8-year 1-hour swing bars: ~28,200 bars, ~700 KB)
- Tier 2: docs/data/deep/ng_15m.json     (Trailing 2-year 15-minute bars: ~28,000 bars, ~700 KB)
- Tier 3: docs/data/deep/1m/<YYYY_MM>.json (Monthly 1-minute microstructure chunks)

Strict Guardrails Enforced:
1. Deduplication & Chronological Sort: Guaranteed strictly ascending timestamps to prevent
   Lightweight Charts runtime assertions.
2. Floating-point rounding to 2 decimal places to minimize JSON size.
"""

import json
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

VAULT_PARQUET = Path("data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet")
OUTPUT_DIR = Path("docs/data/deep")
OUTPUT_1M_DIR = OUTPUT_DIR / "1m"

def main():
    if not VAULT_PARQUET.exists():
        print(f"Error: Vault parquet not found at {VAULT_PARQUET}")
        sys.exit(1)

    print(f"Loading 1m vault: {VAULT_PARQUET}...")
    df = pd.read_parquet(VAULT_PARQUET)
    print(f"Loaded {len(df):,} raw bars.")

    # Ensure datetime index in IST
    df["dt"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("dt").sort_index()

    # Drop duplicate timestamps if any
    df = df[~df.index.duplicated(keep="first")]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_1M_DIR.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────
    # Tier 0: Daily (Full 8 Years: 2019-2026)
    # ─────────────────────────────────────────────────────────────
    print("Resampling Daily tier (2019-2026)...")
    daily = df.resample("1D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "epoch": "first"
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
    daily_file = OUTPUT_DIR / "ng_daily.json"
    with open(daily_file, "w") as f:
        json.dump(daily_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 0 Daily: {len(daily_bars):,} bars -> {daily_file} ({daily_file.stat().st_size / 1024:.1f} KB)")

    # ─────────────────────────────────────────────────────────────
    # Tier 1: 1-Hour (Full 8 Years: 2019-2026)
    # ─────────────────────────────────────────────────────────────
    print("Resampling 1-Hour tier (2019-2026)...")
    h1 = df.resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "epoch": "first"
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
    h1_file = OUTPUT_DIR / "ng_1h.json"
    with open(h1_file, "w") as f:
        json.dump(h1_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 1 1-Hour: {len(h1_bars):,} bars -> {h1_file} ({h1_file.stat().st_size / 1024:.1f} KB)")

    # ─────────────────────────────────────────────────────────────
    # Tier 2: 15-Minute (Trailing 2 Years: 2025-2026)
    # ─────────────────────────────────────────────────────────────
    print("Resampling 15-Minute tier (2025-2026)...")
    df_recent = df[df.index >= "2025-01-01"]
    m15 = df_recent.resample("15min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "epoch": "first"
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
    m15_file = OUTPUT_DIR / "ng_15m.json"
    with open(m15_file, "w") as f:
        json.dump(m15_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 2 15-Minute: {len(m15_bars):,} bars -> {m15_file} ({m15_file.stat().st_size / 1024:.1f} KB)")

    # ─────────────────────────────────────────────────────────────
    # Tier 3: 1-Minute Monthly Microstructure (Trailing 12 Months)
    # ─────────────────────────────────────────────────────────────
    print("Generating Tier 3 Monthly 1-Minute chunks for trailing 12 months...")
    df_1m = df[df.index >= "2025-10-01"].copy()
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
        target_file = OUTPUT_1M_DIR / f"{ym}.json"
        with open(target_file, "w") as f:
            json.dump(month_bars, f, separators=(',', ':'))
        print(f"  Month {ym}: {len(month_bars):,} 1m bars -> {target_file.name} ({target_file.stat().st_size / 1024:.1f} KB)")
        manifest_1m.append({
            "month": ym,
            "bars": len(month_bars),
            "start": int(group["epoch"].iloc[0]),
            "end": int(group["epoch"].iloc[-1]),
            "file": f"data/deep/1m/{ym}.json"
        })

    manifest_file = OUTPUT_DIR / "manifest.json"
    manifest_data = {
        "daily": {"file": "data/deep/ng_daily.json", "bars": len(daily_bars)},
        "h1": {"file": "data/deep/ng_1h.json", "bars": len(h1_bars)},
        "m15": {"file": "data/deep/ng_15m.json", "bars": len(m15_bars)},
        "m1_months": manifest_1m
    }
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Wrote manifest: {manifest_file}")
    print("LOD data pyramid successfully built.")

if __name__ == "__main__":
    main()
