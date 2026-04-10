# MCX Margin Intelligence — Natural Gas Futures Dashboard

An automated intelligence platform extracting daily margin levels and volatility indexes from MCX CCL. Designed to visualize forward curves, historical volume offsets, and 16+ years of backfilled seasonal loading sets.

[![View Dashboard](https://img.shields.io/badge/View-Live--Dashboard-3fb950?style=for-the-badge&logo=github)](https://yieldchaser.github.io/mcx-margins/)
[![Daily Update](https://img.shields.io/badge/Daily--Update-Automated-388bfd?style=for-the-badge&logo=githubactions)](https://github.com/yieldchaser/mcx-margins/actions)

---

## 📊 Live Dashboard
The standalone layout translates scraped SQLite streams into structural JSON aggregates rendered efficiently inside panel workloads.

[**👉 Click to Launch the Dashboard**](https://yieldchaser.github.io/mcx-margins/)

### 📈 Major Feature Sets

*   **Overview Hub**: Front Month snapshot with historical percentile rank, dual-percentile regime detection, probability-weighted Hike/Cut/Flat signals, and predictive Panic Spread signals.
*   **Term Structure**: Complete dual-axis loading curves comparing `NATURALGAS` vs `NATGASMINI` margin weights + P10/P50/P90 confidence cones at equivalent DTE.
*   **Historical Trends**: Rich margin + volatility time series (2010–present) with regime-colored scatter plot, dual OLS regression lines per regime, and margin decomposition (structural vs policy buffer).
*   **Seasonality Check**: Monthly box plots (P10–P90 whiskers, P25–P75 IQR, median/mean markers) with all-years and last-5-years toggles.
*   **Analytics Layer**: 
    - **Model Health** scorecard: directional accuracy, MAE, RMSE, interval hit rates (30d/90d/365d).
    - **Prediction intervals**: ±1σ/±2σ bands on the forecast model from rolling residual std.
    - **DTE vs Margin** and **Lag Correlation** trend analysis.
    - **Delta Distribution**: daily margin change histograms by DTE bucket + conditional P10/P50/P90 by current margin quartile.
*   **Regime Detection**: Two-regime OLS model (Regime A: low-vol/pre-2019; Regime B: elevated/2019+) with per-regime coefficients, percentile ranks, and visual classification.
*   **Stress Score**: Composite 0–100 indicator combining margin + volatility percentiles (5-year trailing) with gradient visualization.
*   **Raw Data Explorer**: Multi-column list filtering with direct CSV export.

---

## 📊 Advanced Analytics (Items 1–9)

All statistical enhancements use **numpy + scikit-learn** for robust modeling:

| Feature | JSON Output | Tab | Use Case |
|---------|-------------|-----|----------|
| **Forecast Bands** | `forecast_bands.json` | Analytics | View ±1σ/±2σ confidence intervals on tomorrow’s predicted margin |
| **Model Health** | `model_health.json` | Analytics | Check backtest metrics (directional accuracy, hit rates) over 30d/90d/365d windows |
| **Regime Detection** | `regime_model.json` | All | Color-coded regime classification + per-regime OLS regression |
| **Delta Distribution** | `delta_distribution.json` | Analytics | Histogram of daily margin changes by DTE bucket + conditional stats |
| **Confidence Cone** | `curve_cone.json` | Term Structure | P10/P50/P90 historical ranges at equivalent DTE per expiry |
| **Decomposition** | `decomposition.json` | History | Structural (vol-implied) margin vs MCX’s policy buffer over time |
| **Box Plots** | `seasonality_boxplot.json` | Seasonality | Monthly dispersion stats (full range + IQR + median) |
| **Stress Score** | `stress_score.json` | Header | Composite 0–100 regime indicator (CALM → STRESS) |
| **Event Probabilities** | `event_probabilities.json` | Overview | Logistic regression P(hike)/P(cut)/P(flat) per expiry + Brier scores |



## 🚀 Current Database Context

The platform leverages a local highly dense SQLite buffer cached at `data/margins.db`:

| Symbol | Range | Records | Min Margin % | Max Margin % |
| :--- | :--- | :--- | :--- | :--- |
| **NATURALGAS** | `2010-01-01` to `Present` | **86,663** | 0.00% | 100.00% |
| **NATGASMINI** | `2023-03-14` to `Present` | **38,704** | 0.00% | 100.00% |

> **Total records**: ~125,367 continuous data points processed correctly scaling pipelines safely.

---

## 🛠️ System Architecture (Excel → SPA Pipeline)

The platform converts static calculations into automated daily streams:

### 1. Scraper Module (`src/scraper.py` + `main.py`)
*   Uses a **Multi-Layered Playwright stealth browser** triggering homepage navigations first to bypass target session cookies and bot detections safely.
*   Intercepts `POST /backpage.aspx/GetDailyMargin` API payloads directly inside browser execution, omitting heavy DOM nodes for fast scraping.
*   Normalizes standardized volatility data points mapping seamlessly into daily offset streams.

### 2. Structured Storage (`src/db.py`)
*   Local fast **SQLite cached repository** utilizing rich composed composite framing indexes preserving strict consistency and skipping overlapping duplications securely.

### 3. Static Indexer publishes (`export_json.py`)
Continually bundles aggregates drafting fully dense statically loaded caches stored natively inside `docs/data/*.json`:
*   Baseline exports: meta, current, history (NG/NGM), forward curve, DTE/seasonality curves, panic spread, volatility correlation, Henry Hub price.
*   **Advanced analytics** (9 new): forecast bands (±1σ/±2σ), model health scorecard, regime detection & OLS models, delta distribution histograms, forward curve confidence cone, margin decomposition, seasonality box plots, composite stress score, event probabilities (logistic).
*   Resolves Cross-Origin (CORS) limits offline supporting **Henry Hub benchmark price** layering loads fallback scripts securely.

### 4. Continuous Alerts Pipeline (`alert.py`)
*   Queries historical margin shifts from SQLite date differentials.
*   Auto-flags sudden absolute shifts (> thresholds) triggering rich **HTML Email Alerts via SMTP** keeping traders aligned ahead of funding timelines.

### 5. SPA Client Dashboard (`docs/index.html`)
Fast **Vanilla Javascript SPA layout with Glassmorphism overlay aesthetics**. Renders lightweight requests into parallel structural outputs using standard Chart.js concurrent plotting without React bundle wait times safely.

---

## ⚙️ Continuous Automated Wiring

Defined securely inside the `.github/workflows/daily_margin.yml` Github Actions configuration:

*   **Trigger Schedule**: Runs automatically @ **1:30 & 13:30 UTC** (`7:00 AM & 7:00 PM IST`) loads seamlessly.
*   **Sequential Pipeline Operations**:
    1. **Fetch Setup Check**: Triggers Chromium fetch streams loading last 3 days to catch delayed update offsets safely.
    2. **Static Bundling**: Runs static stream aggregates publishing directly into local SPA documentation trees.
    3. **Threshold Guard**: Executes threshold differential algorithms sending email alerts when spikes load safely.
    4. **Commit publishing**: Auto-streams push state differentials securely committing back incremental database commits autonomously.

---

## 💻 Local Setup Operations

To run pipelines or diagnostics locally on local machines:

### Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

### Quick CLI Helpers
*   **Fetch Single Date updates**: `python main.py YYYY-MM-DD`
*   **Re-run full aggregate publish**: `python export_json.py`
*   **Console Summary metrics**: `python query.py --summary`
*   **Direct Excel Sheet export files**: `python query.py --excel`

**View local live dashboards safely**:
```bash
python export_json.py
cd docs && python -m http.server 8080
```
Then visit: `http://localhost:8080` safely.
