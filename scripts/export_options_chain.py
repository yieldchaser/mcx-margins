"""
Blue Margin — Black-76 Options Chain & Greeks Exporter
scripts/export_options_chain.py

Calculates institutional options analytics:
- Black-76 Greeks & IV discounted against matching MCX futures contract
- Synchronous timestamp matching between option trades and underlying futures
- Call Wall, Put Wall, Max Pain, 1-SD Expected Move Cone, and 25-Delta Risk Reversal
- Zero-drift d1 implementation with Brent's root finder
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
from datetime import datetime, timezone
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

import glob
import re

VAULT_DIR = "data/mcx_vault"
CONTRACT_DIR = "data/mcx_vault/contract_wise"
OUTPUT_DIR = "docs/data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Dynamically locate options parquet
options_candidates = glob.glob(os.path.join(VAULT_DIR, "*options*_all_strikes.parquet")) + \
                     glob.glob(os.path.join(VAULT_DIR, "options", "*options*_all_strikes.parquet"))

if not options_candidates:
    print("Notice: No options parquet files present in workspace. Skipping options chain export.")
    sys.exit(0)

OPTIONS_PARQUET = sorted(options_candidates, key=lambda p: os.path.getmtime(p))[-1]

# Infer contract code (e.g. 26OCT, 26NOV, 27JAN)
m_exp = re.search(r"(\d{2}[A-Z]{3})", os.path.basename(OPTIONS_PARQUET).upper())
exp_code = m_exp.group(1) if m_exp else ""

# 2. Dynamically locate matching futures parquet
FUTURES_PARQUET = None
if exp_code:
    expected_fut = os.path.join(CONTRACT_DIR, f"MCX_NATURALGAS{exp_code}FUT_1m_contract_wise.parquet")
    if os.path.exists(expected_fut):
        FUTURES_PARQUET = expected_fut

if not FUTURES_PARQUET:
    fut_candidates = sorted(glob.glob(os.path.join(CONTRACT_DIR, "MCX_NATURALGAS*FUT_1m_contract_wise.parquet")))
    if fut_candidates:
        FUTURES_PARQUET = fut_candidates[0]

if not FUTURES_PARQUET or not os.path.exists(FUTURES_PARQUET):
    print(f"Notice: Matching futures parquet for {exp_code} not present. Skipping options chain export.")
    sys.exit(0)

fut_basename = os.path.basename(FUTURES_PARQUET)
m_sym = re.search(r"MCX_NATURALGAS(\d{2}[A-Z]{3})FUT", fut_basename)
underlying_sym = f"MCX:NATURALGAS{m_sym.group(1)}FUT" if m_sym else "MCX:NATURALGASFUT"

# Risk-free rate (Indian 91-day T-Bill yield ~6.6%)
RISK_FREE_RATE = 0.066

MONTH_CODES = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
if exp_code and len(exp_code) == 5:
    exp_yr = 2000 + int(exp_code[:2])
    exp_mo = MONTH_CODES.get(exp_code[2:].upper(), 10)
    exp_day = 23
    expiry_dt = datetime(exp_yr, exp_mo, exp_day, 18, 0, 0, tzinfo=timezone.utc)
    EXPIRY_EPOCH = int(expiry_dt.timestamp())
    EXPIRY_DATE_STR = expiry_dt.strftime("%Y-%m-%d")
else:
    EXPIRY_EPOCH = int(datetime(2026, 10, 23, 18, 0, 0, tzinfo=timezone.utc).timestamp())
    EXPIRY_DATE_STR = "2026-10-23"

print("=" * 80)
print("EXTRACTING BLACK-76 NATURAL GAS OPTIONS CHAIN & GREEKS")
print("=" * 80)

# 1. Load Futures Data (1-minute bars)
con = duckdb.connect()
df_fut = con.execute(f"""
    SELECT epoch, close as fut_close, volume as fut_vol
    FROM read_parquet('{FUTURES_PARQUET}')
    ORDER BY epoch ASC
""").df()

fut_dict = dict(zip(df_fut["epoch"], df_fut["fut_close"]))
latest_fut_epoch = df_fut["epoch"].iloc[-1]
latest_fut_price = float(df_fut["fut_close"].iloc[-1])
print(f"Loaded {len(df_fut):,} futures bars. Latest Futures Price: ₹{latest_fut_price:.2f} (Epoch {latest_fut_epoch})")

# 2. Black-76 Pricing Formula & Greeks
def black76_price(F, K, T, r, sigma, is_call):
    if T <= 0 or sigma <= 0:
        return max(0.0, F - K) if is_call else max(0.0, K - F)
    # Strictly zero drift inside d1 for futures options
    d1 = (np.log(F / K) + 0.5 * (sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    disc = np.exp(-r * T)
    if is_call:
        return disc * (F * norm.cdf(d1) - K * norm.cdf(d2))
    else:
        return disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

def solve_black76_iv(F, K, T, r, target_price, is_call):
    disc = np.exp(-r * T)
    floor = disc * max(0.0, F - K if is_call else K - F)
    if target_price <= floor + 0.01:
        return 0.05 # Minimum bound
    if target_price >= disc * (F if is_call else K):
        return 3.00 # Maximum bound
        
    f = lambda s: black76_price(F, K, T, r, s, is_call) - target_price
    try:
        # Strictly bounded Brent root-finder
        return float(brentq(f, 0.01, 5.0, xtol=1e-5))
    except Exception:
        # Fallback approximation if boundary not bracketed
        return 0.45

def calculate_greeks(F, K, T, r, sigma, is_call):
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (np.log(F / K) + 0.5 * (sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    disc = np.exp(-r * T)
    n_d1 = norm.pdf(d1)
    
    delta = float(disc * norm.cdf(d1) if is_call else disc * (norm.cdf(d1) - 1.0))
    gamma = float(disc * n_d1 / (F * sigma * np.sqrt(T)))
    vega = float(disc * F * np.sqrt(T) * n_d1 / 100.0) # per 1% vol change
    
    # Theta per calendar day
    if is_call:
        theta = float((- (disc * F * sigma * n_d1) / (2.0 * np.sqrt(T)) + r * disc * (F * norm.cdf(d1) - K * norm.cdf(d2))) / 365.25)
    else:
        theta = float((- (disc * F * sigma * n_d1) / (2.0 * np.sqrt(T)) - r * disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1))) / 365.25)
        
    return {"delta": round(delta, 4), "gamma": round(gamma, 5), "theta": round(theta, 3), "vega": round(vega, 3)}

# 3. Query All Strikes and Latest Option Candles
df_opts = con.execute(f"""
    SELECT 
        strike, type, symbol,
        epoch, open, high, low, close, volume, oi
    FROM read_parquet('{OPTIONS_PARQUET}')
    ORDER BY strike ASC, epoch ASC
""").df()
con.close()

# Group by (strike, type) to extract latest state and synchronous futures match
chain_records = {}
strikes = sorted(df_opts["strike"].unique())

for (strike, opt_type), group in df_opts.groupby(["strike", "type"]):
    last_row = group.iloc[-1]
    last_trade_epoch = int(last_row["epoch"])
    last_opt_price = float(last_row["close"])
    total_vol = int(group["volume"].sum())
    last_oi = int(last_row["oi"])
    
    # Synchronous futures matching: find futures price at exact same minute of option trade
    matched_fut_price = fut_dict.get(last_trade_epoch, latest_fut_price)
    
    # Fractional time to expiry in years
    mins_remaining_at_trade = max((EXPIRY_EPOCH - last_trade_epoch) / 60.0, 1.0)
    T_trade = max(mins_remaining_at_trade / 525600.0, 1.0 / 525600.0)
    
    is_call = (opt_type == "CE")
    solved_iv = solve_black76_iv(matched_fut_price, strike, T_trade, RISK_FREE_RATE, last_opt_price, is_call)
    
    # Now compute Greeks at the LATEST futures price and current fractional time
    curr_mins_remaining = max((EXPIRY_EPOCH - latest_fut_epoch) / 60.0, 1.0)
    T_curr = max(curr_mins_remaining / 525600.0, 1.0 / 525600.0)
    greeks = calculate_greeks(latest_fut_price, strike, T_curr, RISK_FREE_RATE, solved_iv, is_call)
    theo_price = black76_price(latest_fut_price, strike, T_curr, RISK_FREE_RATE, solved_iv, is_call)
    
    if strike not in chain_records:
        chain_records[strike] = {"strike": int(strike)}
    
    key_prefix = "call" if is_call else "put"
    chain_records[strike][key_prefix] = {
        "symbol": str(last_row["symbol"]),
        "ltp": round(last_opt_price, 2),
        "theo_price": round(theo_price, 2),
        "volume": total_vol,
        "oi": last_oi,
        "iv": round(solved_iv * 100.0, 2),
        "delta": greeks["delta"],
        "gamma": greeks["gamma"],
        "theta": greeks["theta"],
        "vega": greeks["vega"],
        "last_trade_epoch": last_trade_epoch
    }

# 4. Compute Master Derivatives Indicators
all_chain_list = [chain_records[s] for s in strikes]

total_call_oi = sum(c.get("call", {}).get("oi", 0) for c in all_chain_list)
total_put_oi = sum(c.get("put", {}).get("oi", 0) for c in all_chain_list)
total_call_vol = sum(c.get("call", {}).get("volume", 0) for c in all_chain_list)
total_put_vol = sum(c.get("put", {}).get("volume", 0) for c in all_chain_list)

# Call Wall & Put Wall
call_wall_strike = max(all_chain_list, key=lambda x: x.get("call", {}).get("oi", 0))["strike"]
put_wall_strike = max(all_chain_list, key=lambda x: x.get("put", {}).get("oi", 0))["strike"]

# Max Pain Calculation across all strike levels
min_loss = float("inf")
max_pain_strike = strikes[len(strikes) // 2]

for candidate_price in strikes:
    total_loss = 0.0
    for row in all_chain_list:
        k = row["strike"]
        c_oi = row.get("call", {}).get("oi", 0)
        p_oi = row.get("put", {}).get("oi", 0)
        total_loss += c_oi * max(0.0, candidate_price - k)
        total_loss += p_oi * max(0.0, k - candidate_price)
    if total_loss < min_loss:
        min_loss = total_loss
        max_pain_strike = candidate_price

# ATM Strike & 1-SD Expected Move Cone
atm_strike = min(strikes, key=lambda x: abs(x - latest_fut_price))
atm_row = chain_records.get(atm_strike, {})
atm_call_iv = atm_row.get("call", {}).get("iv", 45.0) / 100.0
atm_put_iv = atm_row.get("put", {}).get("iv", 45.0) / 100.0
atm_avg_iv = (atm_call_iv + atm_put_iv) / 2.0

curr_T = max((EXPIRY_EPOCH - latest_fut_epoch) / 60.0 / 525600.0, 1.0 / 525600.0)
one_sd_move = latest_fut_price * atm_avg_iv * np.sqrt(curr_T)

# 25-Delta Risk Reversal
call_25d = min(all_chain_list, key=lambda x: abs(x.get("call", {}).get("delta", 0.5) - 0.25))
put_25d = min(all_chain_list, key=lambda x: abs(x.get("put", {}).get("delta", -0.5) - (-0.25)))
risk_reversal_25d = call_25d.get("call", {}).get("iv", 0.0) - put_25d.get("put", {}).get("iv", 0.0)

# Filtered Active Ladder (Liquid strikes: OI > 10 or within +- 15 strikes of ATM)
filtered_strikes = [
    s for s in strikes 
    if abs(s - atm_strike) <= 30 or (chain_records[s].get("call", {}).get("oi", 0) > 10 or chain_records[s].get("put", {}).get("oi", 0) > 10)
]

output_data = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "underlying_futures": underlying_sym,
        "latest_futures_price": latest_fut_price,
        "expiry_date": EXPIRY_DATE_STR,
        "days_to_expiry": round(curr_T * 365.25, 2),
        "total_strikes": len(strikes),
        "filtered_liquid_strikes_count": len(filtered_strikes)
    },
    "indicators": {
        "call_wall_strike": call_wall_strike,
        "call_wall_oi": chain_records[call_wall_strike].get("call", {}).get("oi", 0),
        "put_wall_strike": put_wall_strike,
        "put_wall_oi": chain_records[put_wall_strike].get("put", {}).get("oi", 0),
        "max_pain_strike": max_pain_strike,
        "atm_strike": atm_strike,
        "atm_iv_pct": round(atm_avg_iv * 100.0, 2),
        "expected_move_1sd": round(one_sd_move, 2),
        "expected_range_lower": round(latest_fut_price - one_sd_move, 2),
        "expected_range_upper": round(latest_fut_price + one_sd_move, 2),
        "pcr_oi": round(total_put_oi / max(total_call_oi, 1), 3),
        "pcr_volume": round(total_put_vol / max(total_call_vol, 1), 3),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "risk_reversal_25d": round(risk_reversal_25d, 2)
    },
    "chain": [chain_records[s] for s in filtered_strikes],
    "all_chain": all_chain_list
}

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

output_file_generic = os.path.join(OUTPUT_DIR, "options_chain.json")
with open(output_file_generic, "w", encoding="utf-8") as f:
    json.dump(output_data, f, cls=NpEncoder, separators=(",", ":"))

if exp_code:
    specific_file = os.path.join(OUTPUT_DIR, f"options_chain_{exp_code.lower()}.json")
    with open(specific_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, cls=NpEncoder, separators=(",", ":"))

legacy_file = os.path.join(OUTPUT_DIR, "options_chain_oct26.json")
with open(legacy_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, cls=NpEncoder, separators=(",", ":"))

kb = os.path.getsize(output_file_generic) / 1024
print(f"SUCCESS! Saved Black-76 options chain to {output_file_generic} & aliases ({kb:.1f} KB)")
print(f"  Futures Reference Price : ₹{latest_fut_price:.2f}")
print(f"  Call Wall (Resistance)  : Strike {call_wall_strike} (OI: {chain_records[call_wall_strike].get('call', {}).get('oi', 0):,})")
print(f"  Put Wall (Floor)        : Strike {put_wall_strike} (OI: {chain_records[put_wall_strike].get('put', {}).get('oi', 0):,})")
print(f"  Max Pain Level          : Strike {max_pain_strike}")
print(f"  1-SD Expected Move Cone : ±₹{one_sd_move:.2f} (Range: ₹{latest_fut_price - one_sd_move:.2f} to ₹{latest_fut_price + one_sd_move:.2f})")
print(f"  25-Delta Risk Reversal  : {risk_reversal_25d:+.2f}%")
