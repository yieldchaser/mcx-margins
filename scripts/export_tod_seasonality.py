"""
Blue Margin — US DST-Aware Time-of-Day (TOD) Volatility & Volume Profile Exporter
scripts/export_tod_seasonality.py

Aggregates 1.65M 1-minute bars (2019–2026) into 15-minute intervals across MCX session.
Accounts for US Daylight Saving Time (DST) to isolate the EIA Gas Storage inventory
release and NYMEX pit open without 1-hour temporal smearing.
"""

import os
import json
from datetime import datetime, timedelta
import duckdb
import pandas as pd
import numpy as np

import glob

vault_candidates = sorted(glob.glob("data/mcx_vault/NATURALGAS_1m_continuous_*.parquet"))
PARQUET_FILE = vault_candidates[-1] if vault_candidates else "data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet"
OUTPUT_FILE = "docs/data/tod_seasonality.json"
os.makedirs("docs/data", exist_ok=True)

print("=" * 80)
print(f"EXTRACTING US DST-AWARE TIME-OF-DAY SEASONALITY ({os.path.basename(PARQUET_FILE)})")
print("=" * 80)

con = duckdb.connect()
df = con.execute(f"""
    SELECT 
        epoch,
        open, high, low, close, volume
    FROM read_parquet('{PARQUET_FILE}')
    WHERE volume > 0 AND open > 0 AND high >= low
    ORDER BY epoch ASC
""").df()
con.close()

print(f"Loaded {len(df):,} valid 1-minute candles.")

# Vectorized Timestamps in IST and US Eastern Time
ts_utc = pd.to_datetime(df["epoch"], unit="s", utc=True)
ts_ist = ts_utc.dt.tz_convert("Asia/Kolkata")
ts_ny = ts_utc.dt.tz_convert("America/New_York")

df["date_ist"] = ts_ist.dt.date
df["time_ist"] = ts_ist.dt.strftime("%H:%M")
df["minute_of_day"] = ts_ist.dt.hour * 60 + ts_ist.dt.minute
df["weekday"] = ts_ist.dt.weekday # 3 = Thursday
# Exact DST detection via America/New_York zoneinfo
df["is_us_dst"] = ts_ny.apply(lambda x: bool(x.dst() and x.dst().total_seconds() > 0))

# Filter strictly to MCX Natural Gas trading hours (09:00 to 23:30 IST)
df = df[(df["minute_of_day"] >= 9 * 60) & (df["minute_of_day"] <= 23 * 60 + 30)].copy()

# 15-Minute Interval Binning
df["interval_min"] = (df["minute_of_day"] // 15) * 15
df["time_label"] = df["interval_min"].apply(lambda m: f"{m // 60:02d}:{m % 60:02d}")

# High-Low Range in %: (H - L) / O * 100
df["range_pct"] = (df["high"] - df["low"]) / df["open"] * 100.0

# Log components for Garman-Klass Intraday Volatility:
# 0.5 * (ln(H/L))^2 - (2*ln(2) - 1) * (ln(C/O))^2
log_hl = np.log(df["high"] / df["low"])
log_co = np.log(df["close"] / df["open"])
df["gk_var"] = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)

def aggregate_profile(sub_df):
    grouped = sub_df.groupby("time_label")
    res = grouped.agg(
        avg_volume=("volume", "mean"),
        median_volume=("volume", "median"),
        total_volume=("volume", "sum"),
        avg_range_pct=("range_pct", "mean"),
        gk_vol_annualized=("gk_var", lambda x: float(np.sqrt(np.mean(np.maximum(x, 0)) * 252 * 58) * 100)), # Annualized ~58 15m intervals/day
        obs_count=("volume", "count")
    ).reset_index()
    
    # Sort strictly by time_label
    res = res.sort_values("time_label")
    return {
        "intervals": res["time_label"].tolist(),
        "avg_volume": [round(float(v), 1) for v in res["avg_volume"]],
        "median_volume": [round(float(v), 1) for v in res["median_volume"]],
        "avg_range_pct": [round(float(r), 3) for r in res["avg_range_pct"]],
        "gk_vol_pct": [round(float(g), 2) for g in res["gk_vol_annualized"]],
        "bars_count": [int(c) for c in res["obs_count"]]
    }

print("Aggregating profiles...")
profile_combined = aggregate_profile(df)
profile_summer = aggregate_profile(df[df["is_us_dst"] == True])
profile_winter = aggregate_profile(df[df["is_us_dst"] == False])
profile_thursday = aggregate_profile(df[df["weekday"] == 3])
profile_non_thursday = aggregate_profile(df[df["weekday"] != 3])

output_data = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "source": "NATURALGAS_1m_continuous_2019_2026.parquet",
        "total_candles_analyzed": len(df),
        "summer_candles": int(df["is_us_dst"].sum()),
        "winter_candles": int((~df["is_us_dst"]).sum()),
        "thursday_eia_candles": int((df["weekday"] == 3).sum()),
        "resolution": "15m",
        "session": "09:00 - 23:30 IST"
    },
    "profiles": {
        "combined": profile_combined,
        "summer_edt": profile_summer,
        "winter_est": profile_winter,
        "thursday_eia": profile_thursday,
        "regular_weekdays": profile_non_thursday
    }
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, separators=(",", ":"))

kb_size = os.path.getsize(OUTPUT_FILE) / 1024
print(f"SUCCESS! Saved DST-aware seasonality profile to {OUTPUT_FILE} ({kb_size:.1f} KB)")
print(f"  Summer (US EDT) peak volume interval: {profile_summer['intervals'][np.argmax(profile_summer['avg_volume'])]} ({max(profile_summer['avg_volume']):,.0f} lots/15m)")
print(f"  Winter (US EST) peak volume interval: {profile_winter['intervals'][np.argmax(profile_winter['avg_volume'])]} ({max(profile_winter['avg_volume']):,.0f} lots/15m)")
