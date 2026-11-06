#!/usr/bin/env python3
"""
scripts/generate_15m_rollups.py
Generates 15-minute rollup Parquet archives for all 1-minute contract-wise parquets in data/mcx_vault/contract_wise/.
Also updates DuckDB quant views and catalog manifests.
"""

import os
import glob
import re
import pandas as pd
import duckdb

CONTRACT_DIR = os.path.abspath("data/mcx_vault/contract_wise")
DUCKDB_PATH = os.path.abspath("data/mcx_vault/mcx_quant.duckdb")

def generate_all_15m_rollups():
    one_min_files = sorted(glob.glob(os.path.join(CONTRACT_DIR, "MCX_*_1m_contract_wise.parquet")))
    print(f"Discovered {len(one_min_files)} 1-minute contract files. Generating 15-minute rollups...")

    total_15m_created = 0
    total_15m_bars = 0

    for path_1m in one_min_files:
        path_15m = path_1m.replace("_1m_contract_wise.parquet", "_15m_contract_wise.parquet")
        try:
            df_1m = pd.read_parquet(path_1m)
            if len(df_1m) == 0:
                continue

            df = df_1m.copy()
            if "ts_ist" in df.columns:
                df["ts_ist_dt"] = pd.to_datetime(df["ts_ist"])
            else:
                df["ts_ist_dt"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")

            df_15m = (
                df.set_index("ts_ist_dt")
                .resample("15min")
                .agg({
                    "epoch": "first",
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                    "oi": "last" if "oi" in df.columns else "first",
                    "symbol": "first",
                    "commodity": "first",
                    "expiry": "first",
                })
                .dropna(subset=["close"])
                .reset_index()
            )
            df_15m["epoch"] = df_15m["epoch"].astype("int64")
            if "oi" in df_15m.columns:
                df_15m["oi"] = df_15m["oi"].fillna(0).astype("int64")
            df_15m.rename(columns={"ts_ist_dt": "ts_ist"}, inplace=True)
            df_15m["ts_ist"] = df_15m["ts_ist"].astype(str)

            df_15m.to_parquet(path_15m, compression="zstd", index=False)
            total_15m_created += 1
            total_15m_bars += len(df_15m)
        except Exception as e:
            print(f"Error processing {os.path.basename(path_1m)}: {e}")

    print(f"Generated {total_15m_created} 15-minute Parquet files ({total_15m_bars:,} total 15m bars).")

    # Update DuckDB Views for 15m
    print(f"Updating DuckDB Quant Vault ({DUCKDB_PATH})...")
    con = duckdb.connect(DUCKDB_PATH)
    all_15m_pattern = os.path.join(CONTRACT_DIR, "MCX_*_15m_contract_wise.parquet").replace("\\", "/")
    con.execute(f"CREATE OR REPLACE VIEW mcx_all_futures_15m AS SELECT * FROM read_parquet('{all_15m_pattern}')")

    cnt = con.execute("SELECT count(*) FROM mcx_all_futures_15m").fetchone()[0]
    print(f"DuckDB mcx_all_futures_15m registered! Total 15m bars: {cnt:,}")
    con.close()

if __name__ == "__main__":
    generate_all_15m_rollups()
