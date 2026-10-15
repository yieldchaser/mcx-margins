"""
generate_vault_catalog.py
-------------------------
Generates an audit manifest (JSON & Markdown) of all institutional datasets
stored in the data/mcx_vault/ directory.
"""

from pathlib import Path
import json
import pandas as pd

VAULT_DIR = Path("data/mcx_vault")
OUTPUT_JSON = VAULT_DIR / "VAULT_CATALOG.json"
OUTPUT_MD = VAULT_DIR / "VAULT_CATALOG.md"

def categorize(path_str):
    if "options" in path_str.lower() or "ce" in path_str.lower() or "pe" in path_str.lower():
        return "Options 1-Minute Order Flow"
    elif "contract_wise" in path_str.lower():
        return "Unstitched Contract Futures"
    elif any(c in path_str for c in ["CRUDEOIL", "GOLD", "SILVER", "COPPER"]):
        return "Cross-Asset 1-Minute Continuous"
    elif "continuous" in path_str.lower():
        return "Natural Gas Benchmark Continuous"
    return "Derivative Analytics"

def main():
    if not VAULT_DIR.exists():
        print(f"Vault directory not found: {VAULT_DIR}")
        return

    files = list(VAULT_DIR.rglob("*.parquet"))
    catalog = []
    total_rows = 0
    total_bytes = 0

    print(f"Auditing {len(files)} parquet files...")
    for f in sorted(files):
        size_bytes = f.stat().st_size
        total_bytes += size_bytes
        rel_path = str(f.relative_to(VAULT_DIR)).replace("\\", "/")
        category = categorize(rel_path)

        try:
            df = pd.read_parquet(f)
            rows = len(df)
            total_rows += rows
            cols = list(df.columns)
            dt_col = 'ts_ist' if 'ts_ist' in cols else ('date' if 'date' in cols else ('dt' if 'dt' in cols else ('epoch' if 'epoch' in cols else None)))
            start_date = str(df[dt_col].min()) if dt_col else "N/A"
            end_date = str(df[dt_col].max()) if dt_col else "N/A"
        except Exception as e:
            rows = 0
            cols = []
            start_date = "Error"
            end_date = str(e)

        catalog.append({
            "relative_path": rel_path,
            "category": category,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "rows": rows,
            "columns": cols,
            "start_time": start_date,
            "end_time": end_date
        })

    # Save JSON catalog
    with open(OUTPUT_JSON, "w", encoding="utf-8") as fp:
        json.dump({
            "generated_at": pd.Timestamp.now().isoformat(),
            "total_files": len(catalog),
            "total_rows": total_rows,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "datasets": catalog
        }, fp, indent=2)

    # Save Markdown Report
    md_lines = [
        "# MCX Quant Vault Catalog\n",
        f"**Audit Timestamp:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Total Institutional Records:** {total_rows:,} rows  ",
        f"**Total Storage Footprint:** {total_bytes / (1024*1024):.2f} MB ({len(catalog)} Parquet files)\n",
        "| Category | Dataset Path | Size | Rows | Date Range |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for item in catalog:
        md_lines.append(
            f"| {item['category']} | `{item['relative_path']}` | {item['size_mb']} MB | {item['rows']:,} | {item['start_time'][:16]} to {item['end_time'][:16]} |"
        )

    with open(OUTPUT_MD, "w", encoding="utf-8") as fp:
        fp.write("\n".join(md_lines))

    print(f"Catalog generated: {OUTPUT_JSON} and {OUTPUT_MD}")
    print(f"Total Rows: {total_rows:,} across {len(catalog)} datasets.")

if __name__ == "__main__":
    main()
