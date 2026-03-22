# Agent Prompt: MCX Natural Gas Margin Intelligence Dashboard — Excel → Web

## Your Mission

Convert the `yieldchaser/mcx-margins` GitHub repo into a **fully live, web-based margin intelligence platform** for MCX NATURALGAS and NATGASMINI futures. The existing Excel workbook (`NG_Futures_Calculator.xlsx`) has been deeply analyzed. You are rebuilding every analysis and chart it contains — plus improvements — as a self-updating GitHub Pages site.

The site must:
- Live at `https://yieldchaser.github.io/mcx-margins/`
- Auto-update every weekday evening when the existing GitHub Actions workflow runs
- Load fast, never hang, work on mobile
- Replicate every analysis that was in the Excel, and extend it

---

## Step 0: Read the repo first

```bash
git clone https://github.com/yieldchaser/mcx-margins.git
cd mcx-margins
```

Read these files before writing a single line of code:
- `db.py` — understand the SQLite schema exactly
- `query.py` — understand what data export already exists
- `main.py` + `backfill.py` — understand the data pipeline
- `.github/workflows/daily_margin.yml` — understand what runs automatically
- `data/margins.db` — query it directly with sqlite3 to verify live column names and row counts

```bash
sqlite3 data/margins.db ".schema margins"
sqlite3 data/margins.db "SELECT COUNT(*), MIN(date), MAX(date) FROM margins;"
sqlite3 data/margins.db "SELECT date, symbol, expiry, initial_margin_pct, total_margin_pct, daily_volatility, annualized_volatility FROM margins WHERE symbol='NATURALGAS' ORDER BY date DESC, expiry ASC LIMIT 20;"
```

---

## Step 1: Add the JSON export script — `export_json.py`

Create `export_json.py` in the repo root. This is the bridge between SQLite and the web dashboard. It reads `data/margins.db` and writes static JSON files to `docs/data/`.

### JSON files to produce

**`docs/data/meta.json`**
```json
{
  "last_updated": "2026-02-27",
  "total_records": 119,
  "date_range": { "from": "2010-01-01", "to": "2026-02-27" }
}
```

**`docs/data/current.json`** — Today's full snapshot (all expiries, both symbols)
```json
{
  "as_of": "2026-02-27",
  "NATURALGAS": [
    { "expiry": "26MAR2026", "dte": 27, "initial_margin_pct": 33.1, "elm_pct": 1.25, "tender_margin_pct": 0.0, "total_margin_pct": 33.1, "additional_long_margin_pct": 0.0, "additional_short_margin_pct": 0.0, "special_long_margin_pct": 0.0, "special_short_margin_pct": 0.0, "delivery_margin_pct": 0.0, "daily_volatility": 0.04996, "annualized_volatility": 0.789937 },
    ...
  ],
  "NATGASMINI": [ ... ]
}
```
Logic: query the most recent date in the DB, return all rows for that date.

**`docs/data/history_ng.json`** — Daily time series for NATURALGAS nearest expiry (front month)
```json
[
  { "date": "2025-06-26", "initial_margin_pct": 42.773, "total_margin_pct": 42.773, "elm_pct": 1.25, "tender_margin_pct": 0.0, "daily_volatility": 0.9969, "annualized_volatility": 15.78, "expiry": "26JUL2025", "dte": 30 },
  ...
]
```
Logic: For each date, pick the row with the smallest positive DTE (i.e., the front month contract for NATURALGAS). Order ascending by date.

**`docs/data/history_ngm.json`** — Same but for NATGASMINI front month.

**`docs/data/seasonal_month.json`** — Average margin by calendar month (across all years)
```json
[
  { "month": "JAN", "month_num": 1, "avg_initial_margin": 20.76, "avg_total_margin": 20.76, "count": 312, "min": 5.5, "max": 45.2 },
  { "month": "FEB", "month_num": 2, "avg_initial_margin": 27.67, ... },
  ...
]
```
Logic: Use `strftime('%m', date)` on SQLite. Both symbols combined, or NATURALGAS only — use NATURALGAS only. Include std_dev if possible (use Python statistics.stdev).

**`docs/data/seasonal_year.json`** — Average margin by year (2010–present)
```json
[
  { "year": 2010, "avg_initial_margin": 11.19, "avg_total_margin": 11.19, "count": 288, "min": 5.5, "max": 22.0 },
  { "year": 2011, "avg_initial_margin": 7.39, ... },
  ...
]
```

**`docs/data/seasonal_heatmap.json`** — Month × Year grid for NATURALGAS
```json
{
  "years": [2010, 2011, ..., 2026],
  "months": ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"],
  "data": {
    "2010": { "JAN": 11.2, "FEB": 8.4, ... },
    "2011": { ... }
  }
}
```

**`docs/data/dte_curve.json`** — DTE vs margin (binned)
```json
[
  { "dte_bin": "0-7", "dte_mid": 3, "avg_initial_margin": 45.2, "avg_tender_margin": 12.3, "count": 45 },
  { "dte_bin": "8-14", "dte_mid": 11, "avg_initial_margin": 38.1, ... },
  ...
]
```
Logic: Create DTE bins (0-7, 8-14, 15-30, 31-60, 61-90, 91-120, 121-180, 181+) from the `days_to_expiry` computed field. For NATURALGAS only.

**`docs/data/forward_curve.json`** — Current term structure (all expiries for today)
```json
{
  "as_of": "2026-02-27",
  "NATURALGAS": [
    { "expiry": "26MAR2026", "expiry_date": "2026-03-26", "dte": 27, "total_margin_pct": 33.1, "initial_margin_pct": 33.1, "annualized_volatility": 0.789937 },
    { "expiry": "27APR2026", "dte": 59, "total_margin_pct": 31.53, ... },
    ...
  ],
  "NATGASMINI": [ ... ]
}
```

**`docs/data/volatility_correlation.json`** — Margin vs vol with lag analysis
```json
{
  "lags": [0, 5, 10, 15, 20, 30],
  "NATURALGAS": {
    "0": 0.929,
    "5": 0.861,
    "10": 0.708,
    "15": 0.449,
    "20": 0.286,
    "30": 0.15
  },
  "timeseries": [
    { "date": "2025-06-26", "margin_pct": 42.773, "vol_daily": 0.9969, "vol_annual": 15.78 },
    ...
  ]
}
```
Logic: For lag correlation, use pandas `.corr()` or scipy. For timeseries, join margin % and daily_volatility by date (front month NATURALGAS).

**`docs/data/panic_spread.json`** — Panic spread signal (forward curve spread)
```json
{
  "as_of": "2026-02-27",
  "NATURALGAS": [
    { "expiry_label": "Apr-26", "total_margin_pct": 33.541, "vol_daily": 0.690831, "predicted_tomorrow": 29.77, "action": "CUT", "spread_vs_prev": -3.77 },
    ...
  ]
}
```
Logic: For each expiry in the current forward curve, compute:
- `spread_vs_prev` = total_margin_pct for this expiry minus next expiry's total_margin_pct
- `predicted_tomorrow` = simple: `total_margin_pct * (vol_daily / avg_vol_last_20_days)` or use the linear regression formula from Backend_Calc: `Predicted = 0.0 + (margin * regression_coeff)`. Use a simple linear model: `predicted = total_margin_pct + (vol_daily - mean_vol) * sensitivity`. If you can't derive the exact formula, use: `predicted = total_margin_pct * 0.886 + vol_daily * 43.0` (approximate from the Backend_Calc data showing ~29.77 predicted when margin=33.54, vol=0.69)
- `action` = "HIKE" if predicted > current, "CUT" if predicted < current

### Python logic for export_json.py

```python
#!/usr/bin/env python3
"""Export margins.db to JSON files for the web dashboard."""

import sqlite3
import json
import os
from datetime import datetime, date
from pathlib import Path
import statistics
import math

DB_PATH = Path("data/margins.db")
OUT_DIR = Path("docs/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def save(filename, data):
    path = OUT_DIR / filename
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  ✓ {filename}")

def get_conn():
    return sqlite3.connect(DB_PATH)

def compute_dte(expiry_str, ref_date_str):
    """Compute days from ref_date to the actual expiry date (stored in expiry column like '26MAR2026')."""
    # expiry is like '26MAR2026' — parse it
    months = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
    day = int(expiry_str[:2])
    mon = months[expiry_str[2:5]]
    yr = int(expiry_str[5:])
    expiry_date = date(yr, mon, day)
    ref = date.fromisoformat(ref_date_str)
    return (expiry_date - ref).days

if __name__ == "__main__":
    conn = get_conn()
    cur = conn.cursor()
    
    # meta.json
    cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM margins")
    count, min_date, max_date = cur.fetchone()
    save("meta.json", {"last_updated": max_date, "total_records": count, "date_range": {"from": min_date, "to": max_date}})
    
    # current.json (latest date, all expiries, both symbols)
    cur.execute("SELECT MAX(date) FROM margins")
    latest_date = cur.fetchone()[0]
    result = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    cur.execute("""
        SELECT symbol, expiry, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct,
               additional_long_margin_pct, additional_short_margin_pct, special_long_margin_pct,
               special_short_margin_pct, delivery_margin_pct, daily_volatility, annualized_volatility
        FROM margins WHERE date = ? ORDER BY symbol, expiry
    """, (latest_date,))
    for row in cur.fetchall():
        sym = row[0]
        expiry = row[1]
        dte = compute_dte(expiry, latest_date)
        entry = {
            "expiry": expiry, "dte": dte,
            "initial_margin_pct": row[2], "elm_pct": row[3], "tender_margin_pct": row[4],
            "total_margin_pct": row[5], "additional_long_margin_pct": row[6],
            "additional_short_margin_pct": row[7], "special_long_margin_pct": row[8],
            "special_short_margin_pct": row[9], "delivery_margin_pct": row[10],
            "daily_volatility": row[11], "annualized_volatility": row[12]
        }
        if sym in result:
            result[sym].append(entry)
    save("current.json", result)
    
    # history_ng.json and history_ngm.json (front month daily series)
    for sym, fname in [("NATURALGAS", "history_ng.json"), ("NATGASMINI", "history_ngm.json")]:
        cur.execute("SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date", (sym,))
        dates = [r[0] for r in cur.fetchall()]
        series = []
        for d in dates:
            cur.execute("""
                SELECT expiry, initial_margin_pct, total_margin_pct, elm_pct, tender_margin_pct,
                       daily_volatility, annualized_volatility
                FROM margins WHERE date=? AND symbol=?
                ORDER BY expiry ASC
            """, (d, sym))
            rows = cur.fetchall()
            # Front month = smallest positive DTE
            best = None
            best_dte = 99999
            for row in rows:
                dte = compute_dte(row[0], d)
                if dte >= 0 and dte < best_dte:
                    best_dte = dte
                    best = row
            if best:
                series.append({
                    "date": d, "expiry": best[0], "dte": best_dte,
                    "initial_margin_pct": best[1], "total_margin_pct": best[2],
                    "elm_pct": best[3], "tender_margin_pct": best[4],
                    "daily_volatility": best[5], "annualized_volatility": best[6]
                })
        save(fname, series)
    
    # seasonal_month.json
    cur.execute("""
        SELECT strftime('%m', date) as mon,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY mon ORDER BY mon
    """)
    month_names = ['','JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
    rows = cur.fetchall()
    seasonal_month = []
    for row in rows:
        m = int(row[0])
        seasonal_month.append({
            "month": month_names[m], "month_num": m,
            "avg_initial_margin": round(row[1], 3), "avg_total_margin": round(row[2], 3),
            "count": row[3], "min": round(row[4], 3), "max": round(row[5], 3)
        })
    save("seasonal_month.json", seasonal_month)
    
    # seasonal_year.json
    cur.execute("""
        SELECT strftime('%Y', date) as yr,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY yr ORDER BY yr
    """)
    seasonal_year = []
    for row in cur.fetchall():
        seasonal_year.append({
            "year": int(row[0]),
            "avg_initial_margin": round(row[1], 3), "avg_total_margin": round(row[2], 3),
            "count": row[3], "min": round(row[4], 3), "max": round(row[5], 3)
        })
    save("seasonal_year.json", seasonal_year)
    
    # seasonal_heatmap.json
    cur.execute("""
        SELECT strftime('%Y', date) as yr, strftime('%m', date) as mon,
               AVG(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY yr, mon
    """)
    years_set = set()
    heatmap_raw = {}
    for row in cur.fetchall():
        yr, mn = row[0], int(row[1])
        years_set.add(yr)
        if yr not in heatmap_raw:
            heatmap_raw[yr] = {}
        heatmap_raw[yr][month_names[mn]] = round(row[2], 2)
    save("seasonal_heatmap.json", {
        "years": sorted(years_set),
        "months": ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"],
        "data": heatmap_raw
    })
    
    # dte_curve.json
    cur.execute("""
        SELECT date, expiry, initial_margin_pct, tender_margin_pct
        FROM margins WHERE symbol='NATURALGAS'
    """)
    dte_bins = {"0-7": [], "8-14": [], "15-30": [], "31-60": [], "61-90": [], "91-120": [], "121-180": [], "181+": []}
    def get_bin(dte):
        if dte <= 7: return "0-7"
        elif dte <= 14: return "8-14"
        elif dte <= 30: return "15-30"
        elif dte <= 60: return "31-60"
        elif dte <= 90: return "61-90"
        elif dte <= 120: return "91-120"
        elif dte <= 180: return "121-180"
        else: return "181+"
    bin_mid = {"0-7": 3, "8-14": 11, "15-30": 22, "31-60": 45, "61-90": 75, "91-120": 105, "121-180": 150, "181+": 200}
    dte_data = {}
    for row in cur.fetchall():
        d, exp, im, tm = row
        dte = compute_dte(exp, d)
        if dte < 0: continue
        b = get_bin(dte)
        if b not in dte_data: dte_data[b] = {"im": [], "tm": []}
        dte_data[b]["im"].append(im)
        dte_data[b]["tm"].append(tm)
    dte_curve = []
    for b in ["0-7", "8-14", "15-30", "31-60", "61-90", "91-120", "121-180", "181+"]:
        if b in dte_data and dte_data[b]["im"]:
            dte_curve.append({
                "dte_bin": b, "dte_mid": bin_mid[b],
                "avg_initial_margin": round(statistics.mean(dte_data[b]["im"]), 3),
                "avg_tender_margin": round(statistics.mean(dte_data[b]["tm"]), 3),
                "count": len(dte_data[b]["im"])
            })
    save("dte_curve.json", dte_curve)
    
    # forward_curve.json + panic_spread.json (current date)
    cur.execute("""
        SELECT symbol, expiry, initial_margin_pct, total_margin_pct, daily_volatility, annualized_volatility
        FROM margins WHERE date=? ORDER BY symbol, expiry
    """, (latest_date,))
    fwd = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    for row in cur.fetchall():
        sym, exp, im, tm, dv, av = row
        dte = compute_dte(exp, latest_date)
        if sym in fwd:
            fwd[sym].append({
                "expiry": exp, "dte": dte,
                "initial_margin_pct": im, "total_margin_pct": tm,
                "daily_volatility": dv, "annualized_volatility": av
            })
    save("forward_curve.json", fwd)
    
    # volatility_correlation.json
    cur.execute("""
        SELECT date, initial_margin_pct, daily_volatility, annualized_volatility
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY date ORDER BY date
    """)
    ts_rows = cur.fetchall()
    # Use front-month approach: just take one row per date (the avg of front month)
    # For simplicity, take the first expiry per date after deduplication
    ts = [{"date": r[0], "margin_pct": r[1], "vol_daily": r[2], "vol_annual": r[3]} for r in ts_rows]
    # Lag correlation
    margins = [r["margin_pct"] for r in ts if r["margin_pct"] is not None]
    vols = [r["vol_daily"] for r in ts if r["vol_daily"] is not None]
    def safe_corr(x, y):
        n = min(len(x), len(y))
        if n < 2: return None
        x, y = x[:n], y[:n]
        try:
            mx, my = sum(x)/n, sum(y)/n
            num = sum((xi-mx)*(yi-my) for xi,yi in zip(x,y))
            den = math.sqrt(sum((xi-mx)**2 for xi in x) * sum((yi-my)**2 for yi in y))
            return round(num/den, 4) if den > 0 else None
        except: return None
    lag_corr = {}
    for lag in [0, 5, 10, 15, 20, 30]:
        if lag == 0:
            lag_corr[str(lag)] = safe_corr(margins, vols)
        else:
            lag_corr[str(lag)] = safe_corr(margins[lag:], vols[:-lag] if lag > 0 else vols)
    save("volatility_correlation.json", {"lags": [0, 5, 10, 15, 20, 30], "NATURALGAS": lag_corr, "timeseries": ts[:500]})
    
    conn.close()
    print("\nAll JSON files exported successfully.")
```

---

## Step 2: Build the dashboard — `docs/`

Create this file structure:

```
docs/
  index.html          ← Main SPA entry point (single file, all JS/CSS inline)
  data/               ← Auto-generated by export_json.py
    meta.json
    current.json
    history_ng.json
    history_ngm.json
    seasonal_month.json
    seasonal_year.json
    seasonal_heatmap.json
    dte_curve.json
    forward_curve.json
    volatility_correlation.json
    panic_spread.json
```

### `docs/index.html` — Complete specification

**Tech stack:**
- Chart.js 4.x from CDN (`https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`)
- Chart.js annotation plugin from CDN (for threshold lines)
- Tailwind CSS from CDN (for layout only)
- Pure vanilla JS — no frameworks
- All CSS/JS inlined in one file
- Fonts: Inter from Google Fonts

**Color palette (dark terminal/trading theme):**
```css
--bg: #0d1117           /* page background */
--surface: #161b22      /* card/panel background */
--surface2: #21262d     /* nested card, table rows */
--border: #30363d       /* borders */
--text: #e6edf3         /* primary text */
--text-muted: #8b949e   /* secondary text */
--accent-blue: #388bfd  /* primary accent, links */
--accent-green: #3fb950 /* positive, safe */
--accent-red: #f85149   /* negative, danger, hike */
--accent-yellow: #d29922 /* warning */
--accent-purple: #a371f7 /* volatility series */
--accent-orange: #fb8f44 /* NATGASMINI accent */
--chart-ng: #388bfd     /* NATURALGAS chart color */
--chart-ngm: #fb8f44    /* NATGASMINI chart color */
--chart-vol: #a371f7    /* volatility chart color */
```

**Layout:**
```
[HEADER: Logo + Title + Last Updated + Key Stats bar]
[TAB NAV: Overview | Term Structure | History | Seasonality | Analytics | Data Explorer]
[TAB CONTENT AREA]
[FOOTER]
```

---

### TAB 1: Overview

**Key Stats Bar (always visible below header):**
- Current Front-Month Margin % (NATURALGAS) — large number
- ELM % — small
- Daily Volatility — with sparkline
- Annualized Volatility %
- Days to Expiry (front month)
- Last Updated date

**Section 1.1 — Current Term Structure (mini)**
A compact line chart showing today's forward curve: X = DTE, Y = Total Margin %. Both NATURALGAS (blue) and NATGASMINI (orange) as two lines. Data source: `forward_curve.json`.

**Section 1.2 — Current Margin Breakdown Table**
For NATURALGAS, show a table of all current expiries:
| Contract | Expiry | DTE | Initial Margin % | ELM % | Tender % | Total % | Ann. Vol % |
Color code DTE: red (≤30 days), yellow (31–60), green (>60).

**Section 1.3 — Panic Spread Signal Table**
For each current expiry:
| Contract | Current Margin | Today's Vol | Predicted Tomorrow | Action |
Action cell: green "▼ CUT" or red "▲ HIKE" badge.

Data source: `forward_curve.json` (compute panic spread in JS: `predicted = contract.total_margin_pct * 0.886 + contract.daily_volatility * 43.0`; if predicted > current → HIKE, else → CUT).

---

### TAB 2: Term Structure

**Chart 2.1 — Forward Curve (full)**
Large line chart, dual Y axes if needed.
- X axis: DTE (0 to 185 days), or expiry labels
- Y axis: Total Margin %
- Line 1 (blue): NATURALGAS current
- Line 2 (orange): NATGASMINI current
- Tooltip: show expiry, DTE, margin %
- Annotation: horizontal dashed line at current front-month margin level

**Chart 2.2 — Volatility Curve**
Same X axis (by expiry), Y = Annualized Volatility %. Single purple line. Shows whether vol is in contango or backwardation.

**Chart 2.3 — Margin Spread Heatmap (optional)**
If you have enough data: show margin spread between NATURALGAS front month vs 6-month deferred over time. A simple line chart will do.

---

### TAB 3: History

**Controls at top:**
- Symbol selector: `NATURALGAS | NATGASMINI`
- Date range picker (or quick buttons: 1M | 3M | 6M | 1Y | 3Y | All)
- Metric toggles: Initial Margin | Total Margin | ELM | Volatility

**Chart 3.1 — Margin % Over Time (primary)**
Time series line chart. X = date, Y = initial_margin_pct (or total_margin_pct).
- Show selected date range
- Brush/zoom capability (use Chart.js zoom plugin from CDN, or implement with slider)
- Tooltip with date, margin %, vol

**Chart 3.2 — Volatility Overlay**
Second chart (or second Y axis on Chart 3.1) showing daily_volatility and annualized_volatility over same time range.

**Chart 3.3 — Margin vs Volatility Scatter**
X = daily_volatility, Y = initial_margin_pct. Each point = one day's front-month reading.
Color by year (gradient from 2010 to 2026).
Tooltip: date, margin %, vol.
This visually shows the margin-vol relationship.

Data source: `history_ng.json` or `history_ngm.json` depending on symbol selector.

---

### TAB 4: Seasonality

**Chart 4.1 — Average Margin by Month (Bar Chart)**
X = month name (JAN–DEC), Y = avg initial margin %. Blue bars with error bars showing min/max range. Annotate with value labels on top of bars. Data: `seasonal_month.json`.

**Chart 4.2 — Year-over-Year Comparison (Bar Chart)**
X = year (2010–2026), Y = avg initial margin %. Color bars: green for below-median years, red for above-median. Annotate with year labels. Data: `seasonal_year.json`.

**Chart 4.3 — Monthly Heatmap (the Excel's "Seasonal Dashboard" main chart)**
A CSS grid heatmap — not a chart library, but a rendered HTML table/grid.
- Rows = years (2010–2026), Columns = months (JAN–DEC)
- Each cell: background color from green (low margin = easy to trade) to red (high margin = expensive)
- Cell text: the margin % value (1 decimal)
- Color scale: compute min/max across all cells, interpolate green→yellow→red
- Data source: `seasonal_heatmap.json`

This is the **crown jewel of the Seasonality tab** — make it look like a professional Bloomberg terminal heatmap.

**Chart 4.4 — Monthly Box Plot (optional enhancement)**
If time allows: show distribution of daily margins per month as box plots (min/Q1/median/Q3/max). Use Chart.js custom rendering or a simpler visualization with range bars.

---

### TAB 5: Analytics

**Section 5.1 — DTE Curve (Days to Expiry vs Margin)**
Line chart: X = DTE bin midpoint (0 to 200 days), Y = avg initial margin % and avg tender margin %.
Two lines: Initial Margin (blue), Tender Margin (red).
This replicates the `Backend_Calc` DTE pivot table analysis.
Data source: `dte_curve.json`.

Key insight to annotate: tender margin kicks in only in final 7-14 days, initial margin rises as DTE → 0.

**Section 5.2 — Lag Correlation Analysis**
Bar chart: X = lag (0, 5, 10, 15, 20, 30 days), Y = correlation coefficient between margin % and daily volatility.
Show bars colored by strength: >0.8 = green, 0.5–0.8 = yellow, <0.5 = orange.
Data source: `volatility_correlation.json`.

Add text insight: "Margin and volatility are most correlated when measured simultaneously (lag=0). The relationship weakens significantly beyond 10 days, suggesting MCX responds to current vol conditions rather than anticipating future ones."

**Section 5.3 — Margin Prediction Model (Panic Spread)**
Line chart: X = forward expiry dates, dual Y:
- Y1 (left): Current total_margin_pct (solid blue line)
- Y2 (right) or same scale: Predicted tomorrow's margin (dashed orange line)
Color the gap between lines: red fill when predicted > current (HIKE), green fill when predicted < current (CUT).

Below chart: a signal table like the Overview tab but with more detail.

Data source: Compute from `forward_curve.json` in JS.

**Section 5.4 — Capital Efficiency (Cap_Efficiency Score)**
If you have Cap_Efficiency data (from the Raw DB Exploration sheet: `Cap_Efficiency = initial_margin_pct / daily_volatility` or similar ratio), show it over time. If not directly available, compute it in JS from `history_ng.json`: `cap_efficiency = 100 / (initial_margin_pct * daily_volatility)` or just show `initial_margin_pct / (annualized_volatility * 100)`.

Line chart: X = date, Y = efficiency score. Higher = better (more margin per unit of risk).

---

### TAB 6: Data Explorer

**Full data table** with:
- Filters: Symbol (NATURALGAS / NATGASMINI), Date range, Expiry month selector
- Columns: Date | Symbol | Expiry | DTE | Initial Margin % | ELM % | Tender % | Total % | Additional Long % | Additional Short % | Daily Vol | Ann. Vol
- Sortable columns (click header to sort)
- Pagination (50 rows per page)
- Export button: "Download CSV" (JS-generated from the loaded data)

Data source: Load `current.json` for initial view. For full history, load `history_ng.json` + `history_ngm.json`.

Note: The full raw DB data (all expiries, all dates) is not exported as a single JSON (would be too large). The Data Explorer tab shows front-month history + current snapshot. Add a note: "For full data export, run `python3 query.py --excel` locally."

---

## Step 3: Update GitHub Actions workflow

In `.github/workflows/daily_margin.yml`, add the JSON export step **after** the existing `python main.py` step:

```yaml
- name: Export JSON data for dashboard
  run: python export_json.py

- name: Commit and push DB + dashboard data
  run: |
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git config user.name "github-actions[bot]"
    git add data/ docs/data/
    git diff --staged --quiet || git commit -m "data: daily margin update $(date +%Y-%m-%d)"
    git push
```

**Important:** Remove the old commit step (don't commit twice). Replace it with this single combined commit that pushes both the DB and the JSON data files together.

Also add to `requirements.txt` if not present: `statistics` is stdlib, no addition needed. If scipy is used for correlation, add `scipy` — but try to avoid it and use stdlib `statistics` + manual correlation.

---

## Step 4: Enable GitHub Pages

In the repo settings (or add a workflow step):
```yaml
- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./docs
```

Or simply push to the `docs/` folder and set GitHub Pages source to "Deploy from branch: main, /docs folder" in repo Settings > Pages.

**Preferred:** Use the `docs/` folder approach (simpler, no gh-pages branch needed). Just push docs/ to main and configure Pages in settings. Add a note in the README for this one-time manual step.

---

## Step 5: Update the repo's `README.md`

Add a section:

```markdown
## 📊 Live Dashboard

[**View the MCX Margin Intelligence Dashboard →**](https://yieldchaser.github.io/mcx-margins/)

The dashboard auto-updates every weekday evening after MCX market close (8 PM IST).

### Dashboard Features
- **Overview**: Current margin snapshot, panic spread signals
- **Term Structure**: Forward curve by expiry (NATURALGAS + NATGASMINI)  
- **History**: Daily margin & volatility time series (2010–present)
- **Seasonality**: Monthly/yearly heatmaps and bar charts
- **Analytics**: DTE curve, lag correlation, margin prediction model
- **Data Explorer**: Filterable/exportable table
```

---

## Step 6: Wire it all together — quality checklist before you finish

Run these checks locally before pushing:

```bash
# 1. Run export to generate JSON
python export_json.py
# Verify all files exist in docs/data/

# 2. Serve locally and check all tabs
cd docs && python -m http.server 8080
# Open http://localhost:8080 and check every tab

# 3. Verify charts render with real data (not empty)
# Check: forward_curve.json has at least 3 expiry entries
# Check: history_ng.json has at least 10 data points
# Check: seasonal_heatmap.json has data for multiple years

# 4. Test on mobile viewport (Chrome DevTools > Toggle device toolbar)

# 5. Check console for JS errors (should be zero)
```

---

## Critical constraints and quality requirements

1. **Single HTML file**: `docs/index.html` must be self-contained. No separate `.js` or `.css` files. All scripts and styles inline.

2. **No hanging / no blocking**: All data loads are `async/await fetch()` with proper error handling. Each tab loads its data lazily when first clicked (not all at once on page load).

3. **Graceful empty states**: If a JSON file returns 0 records, show "No data available" in the chart area rather than crashing.

4. **Mobile responsive**: All charts resize. Table has horizontal scroll on small screens. Font sizes adapt.

5. **Fast first paint**: Load only `meta.json` and `current.json` on initial page load. Other JSON files load on tab click.

6. **Trading-grade precision**: All margin percentages show 2 decimal places. Volatility shows 4 decimal places. DTE shows integer.

7. **Live data badge**: Show a green "LIVE" dot next to the last updated date if the data is from today's date. Show amber "DELAYED" if data is 1-5 days old. Show red "STALE" if data is >5 days old (weekends/holidays expected, so threshold is 5 days).

8. **Chart tooltips**: Every chart must have a detailed tooltip showing the exact values on hover.

9. **Zero hardcoded data**: Every number shown on the dashboard comes from the JSON files. No placeholder/fake data.

10. **Handle NaN / null gracefully**: Some cells in the DB may be null (especially tender_margin_pct = 0 is common). Filter these out in JS before charting.

---

## Known data facts to encode

From the Excel analysis:
- The DB currently has data from **2010 to 2026** (backfill was completed)
- **NATURALGAS**: ~59 expiries per trading day, initial margin ranges 22–44%
- **NATGASMINI**: ~60 expiries per trading day, initial margin ranges 16–33%
- **Tender margin** only kicks in for expiries ≤ 7 days — show this prominently on the DTE chart
- **ELM** (Extreme Loss Margin) = 1.25% consistently — show as a constant annotation on relevant charts
- **Lag correlation** (from Backend_Calc): lag=0: 0.93, lag=5: 0.86, lag=10: 0.71, lag=15: 0.45, lag=20: 0.29 — use these as reference values if the computed correlation differs significantly
- **Year-over-year averages** (from Backend_Calc): 2010–2014 were low margin years (6–11%), 2019–2025 are high (18–35%), 2022–2023 peaks (~30–34%)
- **Seasonal pattern**: JAN is the lowest month (~20.8%), FEB highest (~27.7%), with significant summer volatility

---

## Deliverables

When complete, the following should exist and work:

1. `export_json.py` — tested, runs without errors
2. `docs/index.html` — complete dashboard with all 6 tabs
3. `docs/data/*.json` — all 10 JSON files generated
4. Updated `.github/workflows/daily_margin.yml` — includes export step
5. Updated `README.md` — with link to live dashboard
6. `git push` — everything committed and pushed

The GitHub Actions badge on the README should be green. The GitHub Pages site should be live at `https://yieldchaser.github.io/mcx-margins/`.

---

## DO NOT

- Do not create a React/Vue/Next.js app — vanilla HTML only
- Do not add npm or any build step — this must deploy as static files with zero build
- Do not use localStorage or sessionStorage
- Do not hardcode any margin % values or dates in the charts — always read from JSON
- Do not split into multiple HTML pages — one SPA with tab navigation
- Do not forget to handle the case where `docs/data/` JSON files don't exist yet (show "Loading..." state)
- Do not remove or change the existing scraper scripts (`main.py`, `backfill.py`, `scraper.py`, `db.py`, `query.py`)
