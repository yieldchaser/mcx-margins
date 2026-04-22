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
print(f"Min: {min(counts)}, Max: {max(counts)}, Median: {sorted(counts)[len(counts)//2]}")
print("Obs count → number of contracts with that count:")
for k in sorted(dist):
    print(f"  {k:>3} obs: {dist[k]:>4} contracts")

print()
print("--- Specific contract deep-dive: 27APR2026 ---")
cur.execute("""
    SELECT date, dte, initial_margin_pct, total_margin_pct
    FROM margins
    WHERE symbol='NATURALGAS' AND expiry='27APR2026'
    ORDER BY date
""")
rows = cur.fetchall()
print(f"Total rows in DB for 27APR2026: {len(rows)}")
if rows:
    print(f"  First obs: {rows[0][0]}  DTE={rows[0][1]}")
    print(f"  Last  obs: {rows[-1][0]}  DTE={rows[-1][1]}")

print()
print("--- Was this contract EVER listed more than 30 days before expiry? ---")
# 27APR2026 expiry → if first obs DTE < 30 it was only captured late
if rows:
    max_dte = max(r[1] for r in rows if r[1])
    print(f"  Max DTE seen for 27APR2026: {max_dte} days")
    print(f"  → Contract was first captured when DTE={max_dte} days out")

conn.close()
print()
print("DONE")
