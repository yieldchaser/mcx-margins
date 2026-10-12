#!/usr/bin/env python3
"""Deep audit: why do contracts only have 21-24 observations?"""
import sqlite3
from collections import Counter

conn = sqlite3.connect('data/margins.db')
cur = conn.cursor()

print("=" * 60)
print("DATABASE DEEP AUDIT")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM margins")
print(f"Total rows in margins table: {cur.fetchone()[0]:,}")

cur.execute("SELECT MIN(date), MAX(date) FROM margins WHERE symbol='NATURALGAS'")
r = cur.fetchone()
print(f"NATURALGAS date range: {r[0]} to {r[1]}")

cur.execute("SELECT COUNT(DISTINCT date) FROM margins WHERE symbol='NATURALGAS'")
print(f"Distinct trading days: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(DISTINCT expiry) FROM margins WHERE symbol='NATURALGAS'")
print(f"Distinct expiries: {cur.fetchone()[0]}")

print()
print("--- Contracts per expiry (sample) ---")
cur.execute("""
    SELECT expiry, COUNT(*) as cnt, MIN(date) as first, MAX(date) as last
    FROM margins
    WHERE symbol='NATURALGAS'
    GROUP BY expiry
    ORDER BY cnt DESC
    LIMIT 15
""")
print(f"{'Expiry':<15} {'Obs':>5}  {'First':<12} {'Last':<12}")
for row in cur.fetchall():
    print(f"{row[0]:<15} {row[1]:>5}  {row[2]:<12} {row[3]:<12}")

print()
print("--- How many contracts appear per trading day (sample) ---")
cur.execute("""
    SELECT date, COUNT(DISTINCT expiry) as num_contracts
    FROM margins
    WHERE symbol='NATURALGAS'
    GROUP BY date
    ORDER BY date DESC
    LIMIT 15
""")
print(f"{'Date':<12} {'Num contracts':>15}")
for row in cur.fetchall():
    print(f"{row[0]:<12} {row[1]:>15}")

print()
print("--- Distribution of obs counts ---")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM margins
    WHERE symbol='NATURALGAS'
    GROUP BY expiry
""")
counts = [r[0] for r in cur.fetchall()]
from collections import Counter
dist = Counter(counts)
MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

def compute_dte(expiry_str, ref_date_str):
    try:
        from datetime import date
        day = int(expiry_str[:2])
        mon = MONTH_MAP[expiry_str[2:5].upper()]
        yr = int(expiry_str[5:])
        expiry_date = date(yr, mon, day)
        ref = date.fromisoformat(ref_date_str)
        return (expiry_date - ref).days
    except Exception:
        return 9999

print(f"Min: {min(counts)}, Max: {max(counts)}, Median: {sorted(counts)[len(counts)//2]}")
print("Obs count -> number of contracts with that count:")
for k in sorted(dist):
    print(f"  {k:>3} obs: {dist[k]:>4} contracts")

print()
print("--- Specific contract deep-dive: 27APR2026 ---")
cur.execute("""
    SELECT date, initial_margin_pct, total_margin_pct
    FROM margins
    WHERE symbol='NATURALGAS' AND expiry='27APR2026'
    ORDER BY date
""")
rows = cur.fetchall()
print(f"Total rows in DB for 27APR2026: {len(rows)}")
if rows:
    first_dte = compute_dte('27APR2026', rows[0][0])
    last_dte = compute_dte('27APR2026', rows[-1][0])
    print(f"  First obs: {rows[0][0]}  DTE={first_dte}")
    print(f"  Last  obs: {rows[-1][0]}  DTE={last_dte}")

print()
print("--- Was this contract EVER listed more than 30 days before expiry? ---")
if rows:
    all_dtes = [compute_dte('27APR2026', r[0]) for r in rows]
    max_dte = max(all_dtes)
    print(f"  Max DTE seen for 27APR2026: {max_dte} days")
    print(f"  -> Contract was first captured when DTE={max_dte} days out")

conn.close()
print()
print("DONE")
