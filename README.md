# Blue Margin

An institutional-grade, automated intelligence platform that extracts daily margin levels and volatility indexes from the MCX CCL. Designed for quantitative analysis of forward curves, historical regime detection, and 16+ years of backfilled seasonal loading sets.

[![View Dashboard](https://img.shields.io/badge/View-Live--Dashboard-3fb950?style=for-the-badge&logo=github)](https://yieldchaser.github.io/mcx-margins/)
[![Daily Update](https://img.shields.io/badge/Daily--Update-Automated-388bfd?style=for-the-badge&logo=githubactions)](https://github.com/yieldchaser/mcx-margins/actions)

---

## ⚡ Live Dashboard

The standalone layout translates scraped SQLite streams into structural JSON aggregates rendered instantly on the client side via Vanilla JS and Chart.js, without the bloat of frontend web frameworks.

[**📈 Click to Launch the Dashboard**](https://yieldchaser.github.io/mcx-margins/)

### 🚀 Major Feature Sets

*   **High-Fidelity Interaction Engine**: Institutional-grade visual tracking — synchronized vertical crosshairs, pulsing data-point highlights, and an **Interactive Measurement Tool** (drag-to-measure) for instant delta and duration calculations across any line chart.
*   **Contextual Tooltip Engine**: A custom glassmorphism overlay system provides personalized, context-rich tooltips across the dashboard. Table rows recalculate term structure deviations on the fly; charts provide English-language analytical deductions (e.g., classifying a contract as 'historically cheap' or 'expensive' upon hover).
*   **Overview Hub**: Live front-month metrics, composite conditional Regime detection (Structural vs Elevated states), and a 0–100 weighted Stress Score index to signal funding risk.
*   **Analytics Layer**:
    *   **Panic Spread Signal**: A predictive logistic regression framework forecasting next-day margin shifts. Emits explicit probabilities `P(hike) / P(cut) / P(flat)` and ±1σ / ±2σ point-estimate bands.
    *   **Model Health Scorecard**: Tracks real-time backtest health (Hit-rates, MAE, RMSE, Brier Scores) on rolling 30/90/365 day windows.
    *   **Delta Distribution Histogram**: Visualizes margin changes segmented by Days-to-Expiry (DTE) buckets (0–30d, 31–90d, 91+d) using dynamic histograms mapped against current daily predictions.
*   **Term Structure**: Complete dual-axis loading curves mapping `NATURALGAS` against `NATGASMINI` weights. Features dynamic P10/P50/P90 confidence cones calculated against specific DTE profiles to detect curve contango or backwardation anomalies.
*   **Contract Lifecycle Explorer**: Full single-contract deep-dive with interactive range slider, DTE or date axis toggle, metric switching (Initial / Total / Volatility), and a **Tender Zone** overlay marking the critical ≤30 DTE period. Per-contract stats include peak, trough, and directional hike/cut counts.
*   **Historical Scatter & Models**: Over a decade of margin and volatility time-series data featuring dual-regime OLS regression lines (Regime A: structural pre-2019, Regime B: elevated 2019–present) mapping the structural relationship between margin requirements and base market volatility.
*   **Seasonality Checks**: Monthly box plots (P10–P90 whiskers, IQR bars, median and mean markers) exposing true distributional variance — not just means. Accompanied by a dynamic Month×Year heatmap matrix highlighting deviances from all-time averages.

---

## 📈 Dashboard Components: Charts & Tables Guide

The dashboard is structured into **seven analytical tabs**, each hosting specialized visualization components and dynamic tables.

### 1. Overview Tab
*   **Current Margin Snapshot Table**: The command center. Displays all active expiries for a selected symbol (`NATURALGAS` or `NATGASMINI`), detailing DTE, Initial %, ELM %, Tender %, Total %, and Annualized Volatility. Calculates a **Historical Percentile (Hist. Pct)** benchmarking today's margin against all historical precedents at the exact same DTE range.
*   **Forward Curve — Today**: A rapid-assessment line chart plotting the term structure of margin requirements for both the primary and mini contracts.
*   **Panic Spread Signals Table**: A predictive intelligence matrix. Outputs probabilities across three explicit tomorrow-states — Margin Cut / Flat / Hike — with a stacked probability bar per expiry row.

### 2. Term Structure Tab
*   **Forward Margin Curve (with Confidence Cones)**: Plots the full spine of active expiries against historical confidence cones (P10 to P90 bounds), toggleable between "All-time" and "Recent (5Y)" lookback windows. Visually highlights anomalies where spot margins breach standard term structure models.
*   **Volatility Term Structure**: Maps implied annualized structural volatility across the forward curve.
*   **Margin Spread (NATURALGAS vs NATGASMINI)**: Tracks the basis spread directly between the large and mini contracts to surface pricing inefficiencies.

### 3. History Tab
*   **Triple-Layer Independent Zoom**: Three decoupled viewports for Margin, Volatility, and Decomposition analysis — each with its own dedicated double-thumb range slider.
*   **Initial Margin % Over Time**: Longitudinal line chart mapping front-month margin from 2010 to Present. Supports dynamic timeframe toggling (1M through All-time) and an overlay of Henry Hub (Spot) prices.
*   **Daily Volatility Over Time**: Demonstrates how structural volatility regimes trigger exchange margin interventions.
*   **Margin vs Volatility (Scatter)**: Maps the base relationship between daily volatility (X) and margin requirement (Y) with two-regime OLS regression lines — Regime A (blue, structural) and Regime B (orange, elevated). Threshold: vol ≥ 4.5% AND year ≥ 2019 → Regime B.
*   **Margin Decomposition**: Stacked area chart diagnosing what portion of current margin is driven by "Structural Volatility" versus discretionary "Exchange Policy Buffer."

### 4. Seasonality Tab
*   **Monthly Box Plots**: Replaces simple mean bars with full distributional box plots per month — P10/P90 whiskers, IQR (P25–P75) bars, median dash, mean triangle. All-years vs Last-5-Years toggle. Highlights the current month with a "▲ Now" marker.
*   **Average Margin by Year**: Macro-year aggregations highlighting multi-year structural margin inflation or deflation.
*   **Monthly Margin Heatmap**: Institutional Year × Month gradient matrix table. Identifies localized seasonal clusters, historical anomalies, and time-of-year funding peaks.

### 5. Analytics Tab
*   **Model Health Scorecard**: Transparent backtest audit table evaluating predictive model accuracy across 30d / 90d / 365d rolling windows (Directional Accuracy, MAE, RMSE, 1σ and 2σ Hit Rates).
*   **DTE vs Margin Curve**: Demonstrates the nonlinear degradation of margin requirements as physical settlement approaches. Shows two lines — **all-time average** (solid) and **trailing 5Y average** (dashed) — revealing how much the post-2022 era has shifted structural margin levels at each DTE bucket.
*   **Lag Correlation**: Analyzes the time lag (T+0 to T+30) coupling sudden volatility shifts to MCX regulatory margin responses.
*   **Margin Prediction Model (Panic Spread Full View)**: Plots Current vs Predicted bounds with ±1σ and ±2σ shaded bands across the active forward array.
*   **Margin Change Distribution Histogram**: Segments historically realized day-over-day margin shifts into DTE groups (0–30d, 31–90d, 91+d), mapping the probability of extreme jump-risk tail events. Includes today's predicted delta marker.
*   **5-Day Rolling Average vs Spot Margin**: Tracks short-term momentum crossover against spot margins (last 90 days).
*   **Historical Percentile Rank Over Time**: Dual-line chart — **all-time** (gray dashed, since 2010) and **trailing 5Y** (colored, actionable) — showing where today's margin sits vs the current structural era. Color-coded green/amber/red on the 5Y rank so routine market conditions aren't falsely flagged as elevated by historical eras with structurally different vol regimes.

### 6. Contract Lifecycle Explorer Tab
*   **Single-Contract Deep-Dive**: Select any historical NATURALGAS or NATGASMINI contract by delivery year and month. Renders the full price-of-entry lifecycle from first trading day to expiry.
*   **Tender Zone Overlay**: A red-shaded region marking the ≤30 DTE window where tender margin pressure compounds total margin requirements. Automatically repositions on zoom.
*   **Axis Toggle**: Switch between Calendar Date view and Days-to-Expiry (DTE) view for structural pattern comparison across contracts.
*   **Metric Toggle**: Switch between Initial Margin %, Total Margin %, and Daily Volatility % in one click.
*   **HH Price Overlay**: Toggle Henry Hub spot price as a secondary Y-axis for vol-margin correlation studies.
*   **Per-Contract Stats Strip**: Displays Peak Margin, Trough Margin, cumulative Hike count, and cumulative Cut count for the selected lifecycle window.

### 7. Data Explorer Tab
*   **Raw Data Explorer Table**: Fully paginated environment rendering underlying day-by-day telemetry. Supports unpaginated CSV export for offline quant modeling.

---

## 🔬 Advanced Analytics Architecture

All statistical enhancements are built natively in the data engineering layer using **numpy + scikit-learn** — heavy computations run once at build time, not in the browser.

| JSON Output | Purpose |
|---|---|
| `forecast_bands.json` | Rolling residual σ per DTE bucket → ±1σ / ±2σ prediction intervals |
| `model_health.json` | Directional accuracy + hit-rate + MAE/RMSE across 30d/90d/365d windows |
| `regime_model.json` | Dual-regime OLS coefficients (Regime A vol < 4.5% or pre-2019; Regime B otherwise) |
| `decomposition.json` | Decomposes margin into structural (vol-implied) + policy buffer components |
| `event_probabilities.json` | Logistic regression P(hike) / P(cut) / P(flat) per active expiry |
| `curve_cone.json` | P10/P50/P90 confidence bands (all-time + trailing 5Y) per DTE slot; includes `hist_pct` and `hist_pct_recent` for snapshot table color-coding |
| `delta_distribution.json` | Histogram of day-over-day margin changes segmented by DTE bucket |
| `seasonality_boxplot.json` | Monthly distributional stats (min/p10/p25/median/p75/p90/max) for box plots |
| `stress_score.json` | Composite 0–100 stress score from margin + vol percentile vs trailing 5-year baseline |
| `volatility_correlation.json` | Lag-N Pearson correlations between daily vol and margin changes (T+0 to T+30) |
| `dte_curve.json` | Average initial and tender margin by DTE bin — all-time and trailing 5Y — to surface structural era shifts at each DTE bucket |

---

## 📊 Current Database Context

The platform leverages a local SQLite buffer at `data/margins.db`:

| Symbol | Range | Records |
| :--- | :--- | :--- |
| **NATURALGAS** | `2010-01-01` to `Present` | ~87,407 |
| **NATGASMINI** | `2023-03-14` to `Present` | ~38,704 |

> **Total**: ~126,111 records processed securely without blocking browser threads.

---

## 🏗️ System Pipeline

### 1. Scraper (`fetch_today.py` + `main.py`)
*   Uses a **Multi-Layered Playwright stealth browser** to safely bypass external session cookies and bot-blocks.
*   Intercepts internal API payloads during execution, extracting live market volatility metrics mapped to forward curve arrays.

### 2. Structured Storage (`data/margins.db`)
*   Localized fast **SQLite repository** with composite indexes. Deduplicates on insert — each `(date, symbol, expiry)` triplet is uniquely constrained.

### 3. Static Publisher (`export_json.py`)
*   Bundles all aggregates into fully dense statically cached JSON files in `docs/data/*.json`.
*   Statistical backbone: linear regression, residual computation, logistic model training, histogram binning, seasonality aggregation.
*   Filtering algorithms explicitly sequester tender-period outlier skews from corrupting longitudinal metrics.
*   Deduplication layer ensures all JSON outputs contain exactly one entry per `(date, expiry)` pair.

### 4. Alerts Pipeline (`alert.py`)
*   Queries historical margin shifts from SQLite date differentials.
*   Auto-flags sudden absolute shifts above configured thresholds, triggering rich **HTML Email Alerts via SMTP** ahead of funding timelines.

### 5. Client Dashboard (`docs/index.html`)
*   Robust **Vanilla JS SPA** with glassmorphism tooltip aesthetics and Chart.js. Renders all JSON into parallel structural views in the browser — no backend, no build step.

---

## ⚙️ Automated GitHub Actions

Defined in `.github/workflows/daily_margin.yml`:

*   **Scheduled**: Runs automatically at **1:30 & 13:30 UTC** (7:00 AM & 7:00 PM IST).
*   **Manual trigger**: Supports `workflow_dispatch` for on-demand data refresh from the GitHub Actions tab.
*   **Sequential Pipeline**:
    1. **Fetch & Hydrate**: Bootstraps Playwright to fetch the last 3 days of exchange data to bridge weekend/holiday gaps.
    2. **Publish**: Runs `export_json.py` to regenerate all `docs/data/*.json` aggregates.
    3. **Alert Guard**: Assesses differential algorithms and pushes SMTP alerts if a systemic spike is detected.
    4. **Autonomous Commit**: Streams state differentials back to the remote repository.

---

## 💻 Local Setup

### Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

### CLI Helpers
```bash
# Fetch a single day
python main.py YYYY-MM-DD

# Regenerate all JSON aggregates
python export_json.py

# Query DB summary
python query.py --summary

# Export to Excel
python query.py --excel

# Run local dashboard
python export_json.py
cd docs && python -m http.server 8080
# Visit: http://localhost:8080
```
