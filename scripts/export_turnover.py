"""
Turnover Analytics Exporter for MCX Natural Gas & NatGasMini Futures
Exports multi-year turnover, ADT, tenor breakdown, and monthly seasonality
from data/prices.db to docs/data/market/turnover_analytics.json.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, date

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_DIR, "data", "prices.db")
OUTPUT_PATH = os.path.join(REPO_DIR, "docs", "data", "market", "turnover_analytics.json")


def parse_expiry(exp_str):
    """Parses MCX expiry string format like '27OCT2026' into date object."""
    try:
        return datetime.strptime(exp_str.strip().upper(), "%d%b%Y").date()
    except Exception:
        return None


def get_contract_multiplier(symbol, trade_date_str):
    """
    Returns the physical trading unit multiplier in mmBtu:
    - NATGASMINI: 250 mmBtu
    - NATURALGAS: 500 mmBtu prior to 2008-04-21, 1,250 mmBtu thereafter.
    """
    if symbol == "NATGASMINI":
        return 250.0
    if trade_date_str < "2008-04-21":
        return 500.0
    return 1250.0


def export_turnover_analytics(db_path=DB_PATH, output_path=OUTPUT_PATH):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Query all futures records sorted by date and expiry
    query = """
    SELECT date, symbol, expiry, volume_lots, value_lacs, close, prev_close
    FROM prices
    WHERE UPPER(COALESCE(instrument, 'FUTCOM')) = 'FUTCOM'
      AND symbol IN ('NATURALGAS', 'NATGASMINI')
    ORDER BY date ASC
    """
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        raise ValueError("No FUTCOM records found in database.")

    # Group records by date
    days_map = {}
    for r in rows:
        d_str, sym, exp_str, vol_lots, val_lacs, close_p, prev_close_p = r
        if d_str not in days_map:
            days_map[d_str] = []
        days_map[d_str].append({
            "symbol": sym,
            "expiry": exp_str,
            "volume_lots": int(vol_lots or 0),
            "value_lacs": float(val_lacs or 0.0) if val_lacs is not None else 0.0,
            "close": float(close_p or 0.0) if close_p is not None else (float(prev_close_p or 0.0) if prev_close_p is not None else 0.0),
        })

    sorted_dates = sorted(days_map.keys())

    daily_records = []
    grand_total_cr = 0.0
    grand_total_volume = 0
    all_time_peak_day = {"date": None, "turnover_cr": -1.0, "volume_lots": 0, "contracts": []}

    # Process each trading day
    for d_str in sorted_dates:
        t_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        contracts = days_map[d_str]

        # Categorize contracts
        # Mini contracts are tracked distinctly
        # For standard NATURALGAS, sort unexpired contracts by expiry date
        ng_contracts = []
        ngm_contracts = []

        day_total_cr = 0.0
        day_volume_lots = 0
        day_front_cr = 0.0
        day_next_cr = 0.0
        day_far_cr = 0.0
        day_mini_cr = 0.0

        for c in contracts:
            sym = c["symbol"]
            vol = c["volume_lots"]
            val_lacs = c["value_lacs"]
            close_p = c["close"]

            # Turnover in Crores
            if val_lacs > 0:
                t_cr = val_lacs / 100.0
            else:
                mult = get_contract_multiplier(sym, d_str)
                t_cr = (vol * mult * close_p) / 10000000.0

            c["turnover_cr"] = t_cr
            exp_date = parse_expiry(c["expiry"])
            c["exp_date"] = exp_date

            day_total_cr += t_cr
            day_volume_lots += vol

            if sym == "NATGASMINI":
                ngm_contracts.append(c)
                day_mini_cr += t_cr
            else:
                ng_contracts.append(c)

        # Sort standard contracts by expiry to determine Front (M1), Next (M2), Far (M3+)
        # Valid active contracts: exp_date >= t_date
        active_ng = [c for c in ng_contracts if c["exp_date"] is not None and c["exp_date"] >= t_date]
        active_ng.sort(key=lambda x: x["exp_date"])

        if active_ng:
            day_front_cr += active_ng[0]["turnover_cr"]
            if len(active_ng) > 1:
                day_next_cr += active_ng[1]["turnover_cr"]
            if len(active_ng) > 2:
                for c in active_ng[2:]:
                    day_far_cr += c["turnover_cr"]
        else:
            # Fallback if expiries already passed or missing
            for c in ng_contracts:
                day_front_cr += c["turnover_cr"]

        # Track grand totals and ATH
        grand_total_cr += day_total_cr
        grand_total_volume += day_volume_lots

        if day_total_cr > all_time_peak_day["turnover_cr"]:
            all_time_peak_day = {
                "date": d_str,
                "turnover_cr": round(day_total_cr, 2),
                "volume_lots": day_volume_lots,
                "contracts": [
                    {
                        "symbol": c["symbol"],
                        "expiry": c["expiry"],
                        "volume_lots": c["volume_lots"],
                        "turnover_cr": round(c["turnover_cr"], 2),
                        "close": round(c["close"], 2)
                    }
                    for c in sorted(contracts, key=lambda x: x["turnover_cr"], reverse=True)[:5]
                ]
            }

        daily_records.append({
            "date": d_str,
            "total_cr": day_total_cr,
            "front_cr": day_front_cr,
            "next_cr": day_next_cr,
            "far_cr": day_far_cr,
            "mini_cr": day_mini_cr,
            "vol_lots": day_volume_lots
        })

    # Compute rolling 30-day moving average
    window_30 = []
    daily_export = []
    for d in daily_records:
        window_30.append(d["total_cr"])
        if len(window_30) > 30:
            window_30.pop(0)
        ma30 = sum(window_30) / float(len(window_30))
        daily_export.append([
            d["date"],
            round(d["total_cr"], 2),
            round(ma30, 2),
            round(d["front_cr"], 2),
            round(d["next_cr"], 2),
            round(d["far_cr"], 2),
            round(d["mini_cr"], 2),
            d["vol_lots"]
        ])

    # Group by Year
    yearly_map = {}
    for d in daily_records:
        y = d["date"][:4]
        if y not in yearly_map:
            yearly_map[y] = {
                "year": y,
                "trading_days": 0,
                "total_cr": 0.0,
                "total_lots": 0,
                "front_cr": 0.0,
                "next_cr": 0.0,
                "far_cr": 0.0,
                "mini_cr": 0.0,
                "peak_day": {"date": None, "turnover_cr": -1.0}
            }
        ym = yearly_map[y]
        ym["trading_days"] += 1
        ym["total_cr"] += d["total_cr"]
        ym["total_lots"] += d["vol_lots"]
        ym["front_cr"] += d["front_cr"]
        ym["next_cr"] += d["next_cr"]
        ym["far_cr"] += d["far_cr"]
        ym["mini_cr"] += d["mini_cr"]
        if d["total_cr"] > ym["peak_day"]["turnover_cr"]:
            ym["peak_day"] = {"date": d["date"], "turnover_cr": round(d["total_cr"], 2)}

    sorted_years = sorted(yearly_map.keys())
    max_year = sorted_years[-1]
    yearly_history = []

    prev_y_to = None
    prev_y_vol = None

    for y in sorted_years:
        ym = yearly_map[y]
        t_cr = ym["total_cr"]
        days = ym["trading_days"]
        adt_cr = t_cr / days if days > 0 else 0.0
        t_lakh_cr = t_cr / 100000.0

        front_share = round((ym["front_cr"] / t_cr * 100.0), 1) if t_cr > 0 else 0.0
        next_share = round((ym["next_cr"] / t_cr * 100.0), 1) if t_cr > 0 else 0.0
        far_share = round((ym["far_cr"] / t_cr * 100.0), 1) if t_cr > 0 else 0.0
        mini_share = round((ym["mini_cr"] / t_cr * 100.0), 1) if t_cr > 0 else 0.0

        yoy_to = round(((t_cr - prev_y_to) / prev_y_to * 100.0), 1) if prev_y_to and prev_y_to > 0 else None
        yoy_vol = round(((ym["total_lots"] - prev_y_vol) / prev_y_vol * 100.0), 1) if prev_y_vol and prev_y_vol > 0 else None

        prev_y_to = t_cr
        prev_y_vol = ym["total_lots"]

        yearly_history.append({
            "year": y,
            "trading_days": days,
            "turnover_cr": round(t_cr, 2),
            "turnover_lakh_cr": round(t_lakh_cr, 4),
            "adt_cr": round(adt_cr, 2),
            "total_lots": ym["total_lots"],
            "front_cr": round(ym["front_cr"], 2),
            "next_cr": round(ym["next_cr"], 2),
            "far_cr": round(ym["far_cr"], 2),
            "mini_cr": round(ym["mini_cr"], 2),
            "front_share_pct": front_share,
            "next_share_pct": next_share,
            "far_share_pct": far_share,
            "mini_share_pct": mini_share,
            "yoy_turnover_pct": yoy_to,
            "yoy_volume_pct": yoy_vol,
            "peak_day": ym["peak_day"],
            "is_ytd": (y == max_year)
        })

    # Monthly Seasonality across entire 20-year history
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_map = {m: {"days": 0, "total_cr": 0.0, "total_lots": 0} for m in range(1, 13)}

    for d in daily_records:
        m = int(d["date"][5:7])
        monthly_map[m]["days"] += 1
        monthly_map[m]["total_cr"] += d["total_cr"]
        monthly_map[m]["total_lots"] += d["vol_lots"]

    monthly_seasonality = []
    for m in range(1, 13):
        m_data = monthly_map[m]
        days = m_data["days"]
        t_cr = m_data["total_cr"]
        vol = m_data["total_lots"]
        share = round((t_cr / grand_total_cr * 100.0), 2) if grand_total_cr > 0 else 0.0
        adt = round(t_cr / days, 2) if days > 0 else 0.0
        avg_vol = int(vol / days) if days > 0 else 0

        monthly_seasonality.append({
            "month_num": m,
            "month_name": month_names[m - 1],
            "trading_days": days,
            "total_turnover_cr": round(t_cr, 2),
            "share_pct": share,
            "adt_cr": adt,
            "avg_daily_volume_lots": avg_vol
        })

    # Latest KPIs
    latest_day = daily_records[-1]
    latest_year_obj = yearly_history[-1]

    latest_tot_cr = latest_day["total_cr"]
    front_share_latest = round(latest_day["front_cr"] / latest_tot_cr * 100.0, 1) if latest_tot_cr > 0 else 0.0
    mini_share_latest = round(latest_day["mini_cr"] / latest_tot_cr * 100.0, 1) if latest_tot_cr > 0 else 0.0

    kpis = {
        "current_session": {
            "date": latest_day["date"],
            "turnover_cr": round(latest_day["total_cr"], 2),
            "volume_lots": latest_day["vol_lots"],
            "front_cr": round(latest_day["front_cr"], 2),
            "next_cr": round(latest_day["next_cr"], 2),
            "far_cr": round(latest_day["far_cr"], 2),
            "mini_cr": round(latest_day["mini_cr"], 2),
            "front_share_pct": front_share_latest,
            "mini_share_pct": mini_share_latest
        },
        "ytd_current": {
            "year": latest_year_obj["year"],
            "days": latest_year_obj["trading_days"],
            "turnover_cr": latest_year_obj["turnover_cr"],
            "turnover_lakh_cr": latest_year_obj["turnover_lakh_cr"],
            "adt_cr": latest_year_obj["adt_cr"],
            "annualized_lakh_cr": round((latest_year_obj["adt_cr"] * 252.0) / 100000.0, 3),
            "mini_share_pct": latest_year_obj["mini_share_pct"],
            "front_share_pct": latest_year_obj["front_share_pct"]
        },
        "ath_day": all_time_peak_day,
        "front_month_share_pct": front_share_latest
    }

    meta = {
        "last_updated": sorted_dates[-1],
        "date_range": {"from": sorted_dates[0], "to": sorted_dates[-1]},
        "trading_days": len(sorted_dates),
        "total_turnover_cr": round(grand_total_cr, 2),
        "total_turnover_lakh_cr": round(grand_total_cr / 100000.0, 4),
        "total_volume_lots": grand_total_volume,
        "daily_columns": ["date", "total_cr", "ma30_cr", "front_cr", "next_cr", "far_cr", "mini_cr", "vol_lots"]
    }

    payload = {
        "meta": meta,
        "kpis": kpis,
        "yearly": yearly_history,
        "monthly_seasonality": monthly_seasonality,
        "daily": daily_export
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024.0
    print(f"Exported turnover analytics successfully to {output_path} ({size_kb:.1f} KB, {len(sorted_dates)} sessions, {len(yearly_history)} years).")
    return payload


if __name__ == "__main__":
    export_turnover_analytics()
