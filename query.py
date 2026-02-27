"""
Query tool for MCX CCL margin data.
Usage:
  python3 query.py SYMBOL          # Query by symbol (e.g., ng, ngm, gold)
  python3 query.py --summary       # Show summary of all data
  python3 query.py --excel         # Export to Excel
  python3 query.py --dates         # List all dates in DB
"""

import sys
from pathlib import Path

import db


def print_records(records: list[dict], title: str = ""):
    """Pretty-print margin records."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")

    if not records:
        print("  No records found.")
        return

    # Header
    print(f"\n{'Date':<12} {'Symbol':<15} {'Expiry':<12} {'IM%':>8} {'ELM%':>8} {'Total%':>8} {'Volatility':>12}")
    print("-" * 80)

    for rec in records:
        im = f"{rec['initial_margin_pct']:.2f}" if rec['initial_margin_pct'] is not None else "N/A"
        elm = f"{rec['elm_pct']:.2f}" if rec['elm_pct'] is not None else "N/A"
        total = f"{rec['total_margin_pct']:.2f}" if rec['total_margin_pct'] is not None else "N/A"
        vol = f"{rec['annualized_volatility']:.4f}" if rec.get('annualized_volatility') is not None else "N/A"
        expiry = rec['expiry'] or ""

        print(f"{rec['date']:<12} {rec['symbol']:<15} {expiry:<12} {im:>8} {elm:>8} {total:>8} {vol:>12}")

    print(f"\nTotal: {len(records)} records")


def print_summary(summary: list[dict]):
    """Print summary statistics."""
    print(f"\n{'='*90}")
    print("  MCX CCL Margin Data Summary")
    print(f"{'='*90}")

    if not summary:
        print("  No data in database.")
        return

    print(f"\n{'Symbol':<20} {'Count':>6} {'Earliest':<12} {'Latest':<12} {'Avg IM%':>8} {'Min IM%':>8} {'Max IM%':>8}")
    print("-" * 80)

    for row in summary:
        avg = f"{row['avg_initial_margin']:.2f}" if row['avg_initial_margin'] is not None else "N/A"
        mn = f"{row['min_initial_margin']:.2f}" if row['min_initial_margin'] is not None else "N/A"
        mx = f"{row['max_initial_margin']:.2f}" if row['max_initial_margin'] is not None else "N/A"

        print(f"{row['symbol']:<20} {row['record_count']:>6} {row['earliest_date']:<12} {row['latest_date']:<12} {avg:>8} {mn:>8} {mx:>8}")

    total = sum(r['record_count'] for r in summary)
    print(f"\nTotal symbols: {len(summary)}, Total records: {total}")


def export_excel():
    """Export all data to Excel."""
    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas not installed. Run: pip install pandas openpyxl")
        sys.exit(1)

    # Get all records
    conn = db.get_connection()
    try:
        cursor = conn.execute("""
            SELECT
                date,
                symbol,
                expiry,
                instrument_id,
                file_id,
                initial_margin_pct,
                elm_pct,
                tender_margin_pct,
                total_margin_pct,
                additional_long_margin_pct,
                additional_short_margin_pct,
                special_long_margin_pct,
                special_short_margin_pct,
                delivery_margin_pct,
                daily_volatility,
                annualized_volatility,
                created_at
            FROM margins
            WHERE symbol IN ('NATURALGAS', 'NATGASMINI')
            ORDER BY date DESC, symbol ASC, expiry ASC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    if not rows:
        print("No data to export.")
        return

    df = pd.DataFrame(rows)

    # Rename columns for readability
    df.columns = [
        "Date", "Symbol", "Expiry", "Instrument ID", "File ID",
        "Initial Margin %", "ELM %",
        "Tender Margin %", "Total Margin %",
        "Additional Long Margin %", "Additional Short Margin %",
        "Special Long Margin %", "Special Short Margin %",
        "Delivery Margin %",
        "Daily Volatility", "Annualized Volatility",
        "Created At"
    ]

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    output_path = exports_dir / "mcx_margins.xlsx"

    with pd.ExcelWriter(str(output_path), engine="openpyxl") as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name="Daily Margins", index=False)

        # Summary sheet
        summary_data = db.get_summary()
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            df_summary.columns = [
                "Symbol", "Record Count", "Earliest Date", "Latest Date",
                "Avg Initial Margin %", "Min Initial Margin %", "Max Initial Margin %"
            ]
            df_summary.to_excel(writer, sheet_name="Summary", index=False)

        # Format the main sheet
        ws = writer.sheets["Daily Margins"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

    print(f"[query] Exported {len(rows)} records to {output_path}")
    return str(output_path)


def main():
    db.init_db()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--summary":
        summary = db.get_summary()
        print_summary(summary)

    elif arg == "--excel":
        export_excel()

    elif arg == "--dates":
        dates = db.get_all_dates()
        if dates:
            print(f"\nDates in database ({len(dates)} total):")
            for d in dates:
                print(f"  {d}")
        else:
            print("No dates in database.")

    else:
        # Query by symbol
        symbol = arg.upper()
        records = db.get_margins(symbol=symbol)
        print_records(records, title=f"Margins for symbol matching '{symbol}'")


if __name__ == "__main__":
    main()
