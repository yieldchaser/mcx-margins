#!/usr/bin/env python3
"""
Export margins.db to JSON files for the MCX Margin Intelligence Web Dashboard.
Run: python export_json.py
Output: docs/data/*.json
"""

import sqlite3
import json
import math
import statistics
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path("data/margins.db")
OUT_DIR = Path("docs/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def save(filename, data):
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [OK] {filename}")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
MONTH_NAMES = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def compute_dte(expiry_str, ref_date_str):
    """Parse expiry like '26MAR2026' and return days from ref_date."""
    try:
        day = int(expiry_str[:2])
        mon = MONTH_MAP[expiry_str[2:5]]
        yr = int(expiry_str[5:])
        expiry_date = date(yr, mon, day)
        ref = date.fromisoformat(ref_date_str)
        return (expiry_date - ref).days
    except Exception:
        return 9999


def safe_corr(x, y):
    n = min(len(x), len(y))
    if n < 2:
        return None
    x, y = x[:n], y[:n]
    try:
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den = math.sqrt(
            sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)
        )
        return round(num / den, 4) if den > 0 else None
    except Exception:
        return None


def main():
    print("MCX Margin Dashboard — JSON Export")
    print("=" * 40)
    conn = get_conn()
    cur = conn.cursor()

    # ── meta.json ──────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM margins")
    count, min_date, max_date = cur.fetchone()
    save(
        "meta.json",
        {
            "last_updated": max_date,
            "total_records": count,
            "date_range": {"from": min_date, "to": max_date},
        },
    )

    # ── current.json ──────────────────────────────────────────────────────────
    latest_date = max_date  # already fetched above
    result = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    cur.execute(
        """
        SELECT symbol, expiry, initial_margin_pct, elm_pct, tender_margin_pct,
               total_margin_pct, additional_long_margin_pct, additional_short_margin_pct,
               special_long_margin_pct, special_short_margin_pct, delivery_margin_pct,
               daily_volatility, annualized_volatility
        FROM margins WHERE date = ?
        ORDER BY symbol, expiry
        """,
        (latest_date,),
    )
    for row in cur.fetchall():
        sym = row[0]
        expiry = row[1]
        dte = compute_dte(expiry, latest_date)
        entry = {
            "expiry": expiry,
            "dte": dte,
            "initial_margin_pct": row[2],
            "elm_pct": row[3],
            "tender_margin_pct": row[4],
            "total_margin_pct": row[5],
            "additional_long_margin_pct": row[6],
            "additional_short_margin_pct": row[7],
            "special_long_margin_pct": row[8],
            "special_short_margin_pct": row[9],
            "delivery_margin_pct": row[10],
            "daily_volatility": row[11],
            "annualized_volatility": row[12],
        }
        if sym in result:
            result[sym].append(entry)
    # Sort by DTE ascending
    for sym in ["NATURALGAS", "NATGASMINI"]:
        result[sym].sort(key=lambda x: x["dte"])
    save("current.json", result)

    # ── history_ng.json + history_ngm.json (front-month daily series) ─────────
    for sym, fname in [("NATURALGAS", "history_ng.json"), ("NATGASMINI", "history_ngm.json")]:
        cur.execute(
            "SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date", (sym,)
        )
        dates = [r[0] for r in cur.fetchall()]
        series = []
        for d in dates:
            cur.execute(
                """
                SELECT expiry, initial_margin_pct, total_margin_pct, elm_pct,
                       tender_margin_pct, daily_volatility, annualized_volatility
                FROM margins WHERE date=? AND symbol=?
                ORDER BY expiry ASC
                """,
                (d, sym),
            )
            rows = cur.fetchall()
            best = None
            best_dte = 99999
            for row in rows:
                dte = compute_dte(row[0], d)
                if 0 <= dte < best_dte:
                    best_dte = dte
                    best = row
            if best:
                series.append(
                    {
                        "date": d,
                        "expiry": best[0],
                        "dte": best_dte,
                        "initial_margin_pct": best[1],
                        "total_margin_pct": best[2],
                        "elm_pct": best[3],
                        "tender_margin_pct": best[4],
                        "daily_volatility": best[5],
                        "annualized_volatility": best[6],
                    }
                )
        save(fname, series)

    # ── seasonal_month.json ───────────────────────────────────────────────────
    cur.execute(
        """
        SELECT strftime('%m', date) as mon,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY mon ORDER BY mon
        """,
    )
    seasonal_month = []
    for row in cur.fetchall():
        m = int(row[0])
        seasonal_month.append(
            {
                "month": MONTH_NAMES[m],
                "month_num": m,
                "avg_initial_margin": round(row[1], 3),
                "avg_total_margin": round(row[2], 3),
                "count": row[3],
                "min": round(row[4], 3),
                "max": round(row[5], 3),
            }
        )
    save("seasonal_month.json", seasonal_month)

    # Standard deviation per month (requires fetching raw vals)
    cur.execute(
        """
        SELECT strftime('%m', date) as mon, initial_margin_pct
        FROM margins WHERE symbol='NATURALGAS' AND initial_margin_pct IS NOT NULL
        ORDER BY mon
        """,
    )
    month_vals: dict = {}
    for row in cur.fetchall():
        m = int(row[0])
        month_vals.setdefault(m, []).append(row[1])
    # Patch std_dev into seasonal_month
    for entry in seasonal_month:
        vals = month_vals.get(entry["month_num"], [])
        entry["std_dev"] = round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0
    save("seasonal_month.json", seasonal_month)  # resave with std_dev

    # ── seasonal_year.json ────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT strftime('%Y', date) as yr,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY yr ORDER BY yr
        """,
    )
    seasonal_year = []
    for row in cur.fetchall():
        seasonal_year.append(
            {
                "year": int(row[0]),
                "avg_initial_margin": round(row[1], 3),
                "avg_total_margin": round(row[2], 3),
                "count": row[3],
                "min": round(row[4], 3),
                "max": round(row[5], 3),
            }
        )
    save("seasonal_year.json", seasonal_year)

    # ── seasonal_heatmap.json ─────────────────────────────────────────────────
    cur.execute(
        """
        SELECT strftime('%Y', date) as yr, strftime('%m', date) as mon,
               AVG(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY yr, mon
        """,
    )
    years_set = set()
    heatmap_raw: dict = {}
    for row in cur.fetchall():
        yr, mn = row[0], int(row[1])
        years_set.add(yr)
        heatmap_raw.setdefault(yr, {})[MONTH_NAMES[mn]] = round(row[2], 2)
    save(
        "seasonal_heatmap.json",
        {
            "years": sorted(years_set),
            "months": ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
            "data": heatmap_raw,
        },
    )

    # ── dte_curve.json ────────────────────────────────────────────────────────
    cur.execute(
        "SELECT date, expiry, initial_margin_pct, tender_margin_pct FROM margins WHERE symbol='NATURALGAS'",
    )
    bin_order = ["0-7", "8-14", "15-30", "31-60", "61-90", "91-120", "121-180", "181+"]
    bin_mid = {
        "0-7": 3, "8-14": 11, "15-30": 22, "31-60": 45,
        "61-90": 75, "91-120": 105, "121-180": 150, "181+": 200,
    }

    def get_bin(dte):
        if dte <= 7:
            return "0-7"
        elif dte <= 14:
            return "8-14"
        elif dte <= 30:
            return "15-30"
        elif dte <= 60:
            return "31-60"
        elif dte <= 90:
            return "61-90"
        elif dte <= 120:
            return "91-120"
        elif dte <= 180:
            return "121-180"
        return "181+"

    dte_data: dict = {}
    for row in cur.fetchall():
        d, exp, im, tm = row[0], row[1], row[2], row[3]
        dte = compute_dte(exp, d)
        if dte < 0 or im is None:
            continue
        b = get_bin(dte)
        dte_data.setdefault(b, {"im": [], "tm": []})
        dte_data[b]["im"].append(im)
        if tm is not None:
            dte_data[b]["tm"].append(tm)

    dte_curve = []
    for b in bin_order:
        if b in dte_data and dte_data[b]["im"]:
            dte_curve.append(
                {
                    "dte_bin": b,
                    "dte_mid": bin_mid[b],
                    "avg_initial_margin": round(statistics.mean(dte_data[b]["im"]), 3),
                    "avg_tender_margin": round(
                        statistics.mean(dte_data[b]["tm"]), 3
                    ) if dte_data[b]["tm"] else 0.0,
                    "count": len(dte_data[b]["im"]),
                }
            )
    save("dte_curve.json", dte_curve)

    # ── forward_curve.json ────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT symbol, expiry, initial_margin_pct, total_margin_pct,
               daily_volatility, annualized_volatility
        FROM margins WHERE date=? ORDER BY symbol, expiry
        """,
        (latest_date,),
    )
    fwd: dict = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    for row in cur.fetchall():
        sym, exp, im, tm, dv, av = row
        dte = compute_dte(exp, latest_date)
        if sym in fwd:
            fwd[sym].append(
                {
                    "expiry": exp,
                    "dte": dte,
                    "initial_margin_pct": im,
                    "total_margin_pct": tm,
                    "daily_volatility": dv,
                    "annualized_volatility": av,
                }
            )
    for sym in ["NATURALGAS", "NATGASMINI"]:
        fwd[sym].sort(key=lambda x: x["dte"])
    save("forward_curve.json", fwd)

    # ── volatility_correlation.json ───────────────────────────────────────────
    # One row per date (front month) for NATURALGAS
    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol='NATURALGAS' ORDER BY date",
    )
    all_dates = [r[0] for r in cur.fetchall()]

    ts = []
    for d in all_dates:
        cur.execute(
            """
            SELECT expiry, initial_margin_pct, daily_volatility, annualized_volatility
            FROM margins WHERE date=? AND symbol='NATURALGAS'
            """,
            (d,),
        )
        rows = cur.fetchall()
        best = None
        best_dte = 99999
        for row in rows:
            dte = compute_dte(row[0], d)
            if 0 <= dte < best_dte:
                best_dte = dte
                best = row
        if best and best[1] is not None and best[2] is not None:
            ts.append(
                {
                    "date": d,
                    "margin_pct": best[1],
                    "vol_daily": best[2],
                    "vol_annual": best[3],
                }
            )

    margins_list = [r["margin_pct"] for r in ts]
    vols_list = [r["vol_daily"] for r in ts]

    lag_corr = {}
    for lag in [0, 5, 10, 15, 20, 30]:
        if lag == 0:
            lag_corr[str(lag)] = safe_corr(margins_list, vols_list)
        else:
            lag_corr[str(lag)] = safe_corr(margins_list[lag:], vols_list[:-lag])

    save(
        "volatility_correlation.json",
        {
            "lags": [0, 5, 10, 15, 20, 30],
            "NATURALGAS": lag_corr,
            "timeseries": ts,  # full history
        },
    )

    # ── panic_spread.json ─────────────────────────────────────────────────────
    # Compute from forward_curve data (already loaded)
    ng_fwd = fwd["NATURALGAS"]
    # Compute mean vol for last 20 days
    recent_vols = [r["vol_daily"] for r in ts[-20:] if r["vol_daily"] is not None]
    mean_vol_20 = sum(recent_vols) / len(recent_vols) if recent_vols else 0.04

    panic_entries = []
    for i, contract in enumerate(ng_fwd):
        tm = contract["total_margin_pct"] or 0
        dv = contract["daily_volatility"] or mean_vol_20
        predicted = tm * 0.886 + dv * 43.0
        spread_vs_next = (
            tm - ng_fwd[i + 1]["total_margin_pct"]
            if i + 1 < len(ng_fwd)
            else 0.0
        )
        action = "HIKE" if predicted > tm else "CUT"
        panic_entries.append(
            {
                "expiry": contract["expiry"],
                "dte": contract["dte"],
                "total_margin_pct": round(tm, 3),
                "vol_daily": round(dv, 6),
                "predicted_tomorrow": round(predicted, 3),
                "spread_vs_prev": round(spread_vs_next, 3),
                "action": action,
            }
        )
    save(
        "panic_spread.json",
        {"as_of": latest_date, "NATURALGAS": panic_entries},
    )

    conn.close()
    print()
    print(f"All JSON files exported to {OUT_DIR}/")
    print(f"Latest data: {latest_date} | Total records: {count:,}")


if __name__ == "__main__":
    main()
