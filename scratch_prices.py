import sqlite3
import pandas as pd

conn = sqlite3.connect('data/prices.db')
query = """
    SELECT 
        date,
        expiry,
        value_lacs / 100.0 as traded_cr,
        volume_lots
    FROM prices 
    WHERE symbol = 'NATURALGAS' 
      AND instrument = 'FUTCOM'
"""
df = pd.read_sql_query(query, conn)

# Clean dates
df['date'] = pd.to_datetime(df['date'])
# Expiry might be like '25-Feb-2026' or '2026-02-25'
df['expiry'] = pd.to_datetime(df['expiry'])

# Calculate DTE
df['dte'] = (df['expiry'] - df['date']).dt.days

# Filter invalid DTEs
df = df[df['dte'] >= 0]

# 1. Total Cumulative Traded Value per Contract
total_per_contract = df.groupby('expiry')['traded_cr'].sum()
avg_lifetime_value = total_per_contract.mean()

print(f'--- LIFETIME TRADED VALUE PER CONTRACT ---')
print(f'Average: Rs. {avg_lifetime_value:,.0f} Crores\n')

# 2. Daily Traded Value by DTE Buckets
bins = [-1, 5, 10, 20, 30, 45, 60, 90, 180, 365]
labels = ['0-5 (Tender/Expiry)', '6-10', '11-20 (Prime Front Month)', '21-30', '31-45 (Next Month)', '46-60', '61-90', '90-180', '180+']
df['dte_bucket'] = pd.cut(df['dte'], bins=bins, labels=labels, right=True)

lifecycle = df.groupby('dte_bucket').agg(
    avg_daily_cr=('traded_cr', 'mean'),
    median_daily_cr=('traded_cr', 'median'),
    avg_volume_lots=('volume_lots', 'mean')
).reset_index()

# Format output
lifecycle['avg_daily_cr'] = lifecycle['avg_daily_cr'].round(0)
lifecycle['median_daily_cr'] = lifecycle['median_daily_cr'].round(0)
lifecycle['avg_volume_lots'] = lifecycle['avg_volume_lots'].round(0)

print(f'--- DAILY TRADED VALUE BY DAYS TO EXPIRY (CRORES) ---')
print(lifecycle.to_string(index=False))
