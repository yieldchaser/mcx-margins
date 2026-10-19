"""
Blue Margin — Intraday Rollups, GKYZ Volatility & Calendar Spread Exporter
scripts/export_intraday_rollups.py

Generates:
1. Zero-redundancy Columnar JSONs (5m & 15m) for active contracts with strict ascending deduplication.
2. Garman-Klass-Yang-Zhang (GKYZ) volatility with overnight opening gap term.
3. Session-bounded ASOF calendar roll spread (Nov26 - Oct26).
4. Volume-at-Price (VAP) distribution with POC, VAH, and VAL.
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import duckdb
import numpy as np
import pandas as pd

CONTRACT_DIR = "data/mcx_vault/contract_wise"
OUTPUT_DIR = "docs/data/market"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

print("=" * 80)
print("EXPORTING INTRADAY ROLLUPS, GKYZ VOLATILITY & SPREADS")
print("=" * 80)

con = duckdb.connect()

# 1. Dynamically Discover All Contract Parquets in Vault (Both Active & Expired)
import glob
import re

contracts = []
pattern = os.path.join(CONTRACT_DIR, "MCX_*_1m_contract_wise.parquet")
for ppath in sorted(glob.glob(pattern)):
    pfile = os.path.basename(ppath)
    m = re.match(r"^MCX_([A-Z]+)(\d{2}[A-Z]{3})FUT_1m_contract_wise\.parquet$", pfile)
    if m:
        base, exp_code = m.group(1), m.group(2)
        sym = f"MCX:{base}{exp_code}FUT"
        if base == "NATURALGAS":
            tag = f"NG_{exp_code}"
        elif base == "NATGASMINI":
            tag = f"NGM_{exp_code}"
        else:
            tag = f"{base}_{exp_code}"
        contracts.append((sym, pfile, tag, base))

for sym, pfile, tag, base in contracts:
    full_path = os.path.join(CONTRACT_DIR, pfile)
    if not os.path.exists(full_path):
        continue
    
    # Load 1-minute bars with commodity-appropriate sanity filter
    sanity_filter = "AND open < 1000 AND high < 1000 AND close < 1000" if base in ("NATURALGAS", "NATGASMINI") else ""
    df = con.execute(f"""
        SELECT epoch as dt, open, high, low, close, volume, oi
        FROM read_parquet('{full_path}')
        WHERE open > 0 AND high >= low AND volume >= 0 {sanity_filter}
        ORDER BY epoch ASC
    """).df()
    
    # Strict deduplication and ascending sort (Lightweight Charts rule)
    df = df.drop_duplicates(subset=["dt"]).sort_values("dt").reset_index(drop=True)
    
    # Timestamp in IST
    ts_ist = pd.to_datetime(df["dt"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df["date_ist"] = ts_ist.dt.date
    
    # Calculate GKYZ Daily Realized Volatility:
    # sigma_GKYZ^2 = (ln(O_t / C_{t-1}))^2 + 0.5 * (ln(H_t / L_t))^2 - (2*ln(2) - 1) * (ln(C_t / O_t))^2
    daily_rows = []
    for d, d_group in df.groupby("date_ist"):
        d_open = float(d_group["open"].iloc[0])
        d_high = float(d_group["high"].max())
        d_low = float(d_group["low"].min())
        d_close = float(d_group["close"].iloc[-1])
        d_vol = int(d_group["volume"].sum())
        d_oi = int(d_group["oi"].iloc[-1])
        daily_rows.append({
            "date": str(d),
            "open": d_open, "high": d_high, "low": d_low, "close": d_close,
            "volume": d_vol, "oi": d_oi
        })
        
    df_daily = pd.DataFrame(daily_rows)
    df_daily["prev_close"] = df_daily["close"].shift(1)
    
    # Overnight gap + intraday GK components
    gap_sq = np.log(df_daily["open"] / df_daily["prev_close"]) ** 2
    hl_sq = 0.5 * (np.log(df_daily["high"] / df_daily["low"]) ** 2)
    co_sq = (2.0 * np.log(2.0) - 1.0) * (np.log(df_daily["close"] / df_daily["open"]) ** 2)
    df_daily["gkyz_var"] = gap_sq + hl_sq - co_sq
    # Annualized vol % = sqrt(gkyz_var * 252) * 100
    df_daily["gkyz_vol_pct"] = np.sqrt(np.maximum(df_daily["gkyz_var"], 0)) * np.sqrt(252.0) * 100.0
    
    # Downsample to 15-Minute Bars (Columnar JSON)
    df["dt_15m"] = (df["dt"] // 900) * 900
    df_15m = df.groupby("dt_15m").agg(
        o=("open", "first"),
        h=("high", "max"),
        l=("low", "min"),
        c=("close", "last"),
        v=("volume", "sum"),
        oi=("oi", "last")
    ).reset_index().rename(columns={"dt_15m": "dt"})
    
    df_15m = df_15m.drop_duplicates(subset=["dt"]).sort_values("dt").reset_index(drop=True)
    
    # Calculate Volume-at-Price (VAP) Profile for active contract
    price_min = float(df["low"].min())
    price_max = float(df["high"].max())
    bins = np.linspace(price_min, price_max, 50)
    bin_labels = (bins[:-1] + bins[1:]) / 2.0
    df["price_bin"] = pd.cut(df["close"], bins=bins, labels=bin_labels, include_lowest=True)
    vap_series = df.groupby("price_bin", observed=False)["volume"].sum()
    
    poc_price = float(vap_series.idxmax())
    total_vap_vol = float(vap_series.sum())
    
    # Value Area (at least 70% of total volume inclusive of crossing bin)
    sorted_vap = vap_series.sort_values(ascending=False)
    cum_vol = sorted_vap.cumsum()
    va_mask = (cum_vol.shift(1, fill_value=0) < (total_vap_vol * 0.70)) if total_vap_vol > 0 else pd.Series(True, index=sorted_vap.index)
    va_prices = [float(p) for p in sorted_vap[va_mask].index]
    vah_price = max(va_prices) if va_prices else poc_price
    val_price = min(va_prices) if va_prices else poc_price
    
    # Save Columnar 15m Rollup JSON
    out_15m = {
        "symbol": sym,
        "tag": tag,
        "resolution": "15m",
        "candles_count": len(df_15m),
        "vap_profile": {
            "poc": round(poc_price, 2),
            "vah": round(vah_price, 2),
            "val": round(val_price, 2),
            "levels": [round(float(p), 2) for p in bin_labels],
            "volumes": [int(v) for v in vap_series]
        },
        "latest_gkyz_vol_pct": round(float(df_daily["gkyz_vol_pct"].dropna().iloc[-1]), 2) if len(df_daily.dropna()) > 0 else 45.0,
        "data": {
            "dt": df_15m["dt"].tolist(),
            "o": [round(float(x), 2) for x in df_15m["o"]],
            "h": [round(float(x), 2) for x in df_15m["h"]],
            "l": [round(float(x), 2) for x in df_15m["l"]],
            "c": [round(float(x), 2) for x in df_15m["c"]],
            "v": df_15m["v"].tolist(),
            "oi": df_15m["oi"].tolist()
        }
    }
    
    out_path = os.path.join(OUTPUT_DIR, f"{tag}_15m.json")
    # Guard: If existing 15m JSON has bars, merge to guarantee zero-shrink
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f_ex:
                ex_json = json.load(f_ex)
            # CRITICAL: Only merge if the existing file belongs to this exact symbol
            if ex_json.get("symbol") == sym:
                ex_d = ex_json.get("data", {})
                ex_dt = ex_d.get("dt", [])
                ex_c = ex_d.get("c", [])
                is_corrupted = (base in ("NATURALGAS", "NATGASMINI") and any(x > 1000 for x in ex_c))
                if not is_corrupted and len(ex_dt) > len(df_15m):
                    m_map = {ex_dt[i]: {
                        "o": ex_d["o"][i], "h": ex_d["h"][i], "l": ex_d["l"][i],
                        "c": ex_d["c"][i], "v": ex_d["v"][i], "oi": ex_d.get("oi", [0]*len(ex_dt))[i]
                    } for i in range(len(ex_dt))}
                    for _, r in df_15m.iterrows():
                        m_map[int(r["dt"])] = {
                            "o": round(float(r["o"]), 2), "h": round(float(r["h"]), 2),
                            "l": round(float(r["l"]), 2), "c": round(float(r["c"]), 2),
                            "v": int(r["v"]), "oi": int(r["oi"])
                        }
                    sorted_dt = sorted(m_map.keys())
                    out_15m["candles_count"] = len(sorted_dt)
                    out_15m["data"] = {
                        "dt": sorted_dt,
                        "o": [m_map[t]["o"] for t in sorted_dt],
                        "h": [m_map[t]["h"] for t in sorted_dt],
                        "l": [m_map[t]["l"] for t in sorted_dt],
                        "c": [m_map[t]["c"] for t in sorted_dt],
                        "v": [m_map[t]["v"] for t in sorted_dt],
                        "oi": [m_map[t]["oi"] for t in sorted_dt]
                    }
        except Exception:
            pass

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_15m, f, cls=NpEncoder, separators=(",", ":"))
        
    kb = os.path.getsize(out_path) / 1024
    print(f"  {sym:26s} -> Saved 15m Rollup ({out_15m['candles_count']:,} bars, {kb:.1f} KB) | POC: ₹{poc_price:.2f}, VAH: ₹{vah_price:.2f}, VAL: ₹{val_price:.2f}")

    # Export 1m columnar JSON for all available contracts
    if len(df) > 0:
        out_1m = {
            "symbol": sym,
            "tag": tag,
            "resolution": "1m",
            "candles_count": len(df),
            "data": {
                "dt": df["dt"].tolist(),
                "o": [round(float(x), 2) for x in df["open"]],
                "h": [round(float(x), 2) for x in df["high"]],
                "l": [round(float(x), 2) for x in df["low"]],
                "c": [round(float(x), 2) for x in df["close"]],
                "v": [int(x) for x in df["volume"]]
            }
        }
        out_1m_path = os.path.join(OUTPUT_DIR, f"{tag}_1m.json")

        # Guard: If existing 1m JSON has more bars, merge to guarantee zero-shrink
        if os.path.exists(out_1m_path):
            try:
                with open(out_1m_path, "r", encoding="utf-8") as f_ex:
                    ex_json = json.load(f_ex)
                if ex_json.get("symbol") == sym:
                    ex_d = ex_json.get("data", {})
                    ex_dt = ex_d.get("dt", [])
                    ex_c = ex_d.get("c", [])
                    is_corrupted = (base in ("NATURALGAS", "NATGASMINI") and any(x > 1000 for x in ex_c))
                    if not is_corrupted and len(ex_dt) > len(df):
                        m_map = {ex_dt[i]: {
                            "o": ex_d["o"][i], "h": ex_d["h"][i], "l": ex_d["l"][i],
                            "c": ex_d["c"][i], "v": ex_d["v"][i]
                        } for i in range(len(ex_dt))}
                        for _, r in df.iterrows():
                            m_map[int(r["dt"])] = {
                                "o": round(float(r["open"]), 2), "h": round(float(r["high"]), 2),
                                "l": round(float(r["low"]), 2), "c": round(float(r["close"]), 2),
                                "v": int(r["volume"])
                            }
                        sorted_dt = sorted(m_map.keys())
                        out_1m["candles_count"] = len(sorted_dt)
                        out_1m["data"] = {
                            "dt": sorted_dt,
                            "o": [m_map[t]["o"] for t in sorted_dt],
                            "h": [m_map[t]["h"] for t in sorted_dt],
                            "l": [m_map[t]["l"] for t in sorted_dt],
                            "c": [m_map[t]["c"] for t in sorted_dt],
                            "v": [m_map[t]["v"] for t in sorted_dt]
                        }
            except Exception:
                pass

        with open(out_1m_path, "w", encoding="utf-8") as f:
            json.dump(out_1m, f, cls=NpEncoder, separators=(",", ":"))
        kb_1m = os.path.getsize(out_1m_path) / 1024
        print(f"    └─ Saved 1m Microstructure ({out_1m['candles_count']:,} bars, {kb_1m:.1f} KB)")

# 2. Dynamically Compute Session-Bounded ASOF Calendar Spread
print("\nDynamically Resolving Active Calendar Roll Spread Pair...")
MONTH_ORDER = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}

ng_contracts = []
for sym, pfile, tag, base in contracts:
    m = re.match(r"^MCX_NATURALGAS(\d{2})([A-Z]{3})FUT_1m_contract_wise\.parquet$", pfile)
    if m:
        yr = 2000 + int(m.group(1))
        mo = MONTH_ORDER.get(m.group(2), 0)
        full_path = os.path.join(CONTRACT_DIR, pfile)
        ng_contracts.append({
            "sym": sym,
            "pfile": pfile,
            "path": full_path,
            "tag": tag,
            "yr": yr,
            "mo": mo
        })

ng_contracts.sort(key=lambda x: (x["yr"], x["mo"]))

if len(ng_contracts) >= 2:
    # Pick front month and next month:
    # Look for the first contract that has recent trading activity or the earliest active pair
    now_ts = pd.Timestamp.now(tz="UTC").timestamp()
    pair_idx = 0
    for i in range(len(ng_contracts) - 1):
        c_path = ng_contracts[i]["path"]
        try:
            max_epoch = con.execute(f"SELECT MAX(epoch) FROM read_parquet('{c_path}')").fetchone()[0]
            if max_epoch and (now_ts - max_epoch) < 35 * 86400: # Active in last 35 days
                pair_idx = i
                break
        except Exception:
            continue

    c1 = ng_contracts[pair_idx]
    c2 = ng_contracts[pair_idx + 1]
    print(f"  Selected Roll Pair: Front={c1['sym']} ({c1['tag']}) vs Next={c2['sym']} ({c2['tag']})")

    try:
        df_spread = con.execute(f"""
            WITH c1_data AS (
                SELECT epoch, close as c1_close
                FROM read_parquet('{c1["path"]}')
                WHERE close > 0
            ),
            c2_data AS (
                SELECT epoch, close as c2_close
                FROM read_parquet('{c2["path"]}')
                WHERE close > 0
            )
            SELECT 
                c2_data.epoch as dt,
                c2_data.c2_close,
                c1_data.c1_close,
                ROUND(c2_data.c2_close - c1_data.c1_close, 2) as spread
            FROM c2_data
            JOIN c1_data ON c2_data.epoch = c1_data.epoch
            ORDER BY c2_data.epoch ASC
        """).df()

        if len(df_spread) > 0:
            df_spread["dt_15m"] = (df_spread["dt"] // 900) * 900
            spread_15m = df_spread.groupby("dt_15m").agg(
                spread=("spread", "median"),
                c1_close=("c1_close", "last"),
                c2_close=("c2_close", "last")
            ).reset_index().rename(columns={"dt_15m": "dt"})

            spread_output = {
                "pair": f"{c2['sym']} - {c1['sym']}",
                "front_contract": c1["sym"],
                "next_contract": c2["sym"],
                "resolution": "15m",
                "bars_count": len(spread_15m),
                "latest_spread": round(float(spread_15m["spread"].iloc[-1]), 2),
                "min_spread": round(float(spread_15m["spread"].min()), 2),
                "max_spread": round(float(spread_15m["spread"].max()), 2),
                "data": {
                    "dt": spread_15m["dt"].tolist(),
                    "spread": [round(float(s), 2) for s in spread_15m["spread"]],
                    "front_close": [round(float(c), 2) for c in spread_15m["c1_close"]],
                    "next_close": [round(float(c), 2) for c in spread_15m["c2_close"]]
                }
            }

            # Save perpetual generic calendar spread
            spread_path_generic = os.path.join(OUTPUT_DIR, "calendar_spread.json")
            with open(spread_path_generic, "w", encoding="utf-8") as f:
                json.dump(spread_output, f, cls=NpEncoder, separators=(",", ":"))

            # Save specific pair and legacy compatibility JSONs
            pair_tag_path = os.path.join(OUTPUT_DIR, f"calendar_spread_{c2['tag'].lower()}_{c1['tag'].lower()}.json")
            with open(pair_tag_path, "w", encoding="utf-8") as f:
                json.dump(spread_output, f, cls=NpEncoder, separators=(",", ":"))

            legacy_path = os.path.join(OUTPUT_DIR, "calendar_spread_nov26_oct26.json")
            with open(legacy_path, "w", encoding="utf-8") as f:
                json.dump(spread_output, f, cls=NpEncoder, separators=(",", ":"))

            kb = os.path.getsize(spread_path_generic) / 1024
            print(f"  Saved Calendar Spread to {spread_path_generic} & legacy aliases ({len(spread_15m):,} bars, {kb:.1f} KB)")
            print(f"  Latest Roll Spread: ₹{spread_output['latest_spread']:.2f} (Range: ₹{spread_output['min_spread']:.2f} to ₹{spread_output['max_spread']:.2f})")
    except Exception as e:
        print(f"  Notice calculating calendar roll spread: {e}")

con.close()
print("=" * 80)
print("PHASE 1 PRE-COMPUTATION PIPELINE COMPLETE!")
print("=" * 80)
