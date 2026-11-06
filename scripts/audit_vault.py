import duckdb
from pathlib import Path

p_margins = sorted(Path("data/mcx_vault/historical/margins").glob("*.parquet"))
p_prices = sorted(Path("data/mcx_vault/historical/prices").glob("*.parquet"))

print(f"=== MARGIN PARQUETS ({len(p_margins)} files) ===")
tot_margin_size = sum(p.stat().st_size for p in p_margins) / (1024 * 1024)
print(f"Total Margins Size on Disk: {tot_margin_size:.2f} MB")

con = duckdb.connect()
total_margin_rows = 0
for p in p_margins:
    posix_path = p.as_posix()
    cnt = con.execute(f"SELECT count(*) FROM read_parquet('{posix_path}')").fetchone()[0]
    min_d, max_d = con.execute(f"SELECT min(date), max(date) FROM read_parquet('{posix_path}')").fetchone()
    total_margin_rows += cnt
    print(f"  {p.name}: {cnt:,} rows | {min_d} to {max_d} | {p.stat().st_size / 1024:.1f} KB")

print(f"\nTotal Margin Rows in Vault: {total_margin_rows:,}")

print(f"\n=== PRICE PARQUETS ({len(p_prices)} files) ===")
tot_price_size = sum(p.stat().st_size for p in p_prices) / (1024 * 1024)
print(f"Total Prices Size on Disk: {tot_price_size:.2f} MB")

total_price_rows = 0
for p in p_prices:
    posix_path = p.as_posix()
    cnt = con.execute(f"SELECT count(*) FROM read_parquet('{posix_path}')").fetchone()[0]
    min_d, max_d = con.execute(f"SELECT min(date), max(date) FROM read_parquet('{posix_path}')").fetchone()
    total_price_rows += cnt
    print(f"  {p.name}: {cnt:,} rows | {min_d} to {max_d} | {p.stat().st_size / 1024:.1f} KB")

print(f"\nTotal Price Rows in Vault: {total_price_rows:,}")
con.close()
