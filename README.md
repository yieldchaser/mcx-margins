# MCX Margin Intelligence — Natural Gas Futures Dashboard

An institutional-grade, automated intelligence platform that extracts daily margin levels and volatility indexes from the MCX CCL. Designed for quantitative analysis of forward curves, historical volume offsets, and 16+ years of backfilled seasonal loading sets.

[![View Dashboard](https://img.shields.io/badge/View-Live--Dashboard-3fb950?style=for-the-badge&logo=github)](https://yieldchaser.github.io/mcx-margins/)
[![Daily Update](https://img.shields.io/badge/Daily--Update-Automated-388bfd?style=for-the-badge&logo=githubactions)](https://github.com/yieldchaser/mcx-margins/actions)

---

## ⚡ Live Dashboard
The standalone layout translates scraped SQLite streams into structural JSON aggregates rendered instantly on the client side via Vanilla JS and Chart.js, without the bloat of frontend web frameworks.

[**📈 Click to Launch the Dashboard**](https://yieldchaser.github.io/mcx-margins/)

### 🚀 Major Feature Sets

*   **Contextual Tooltip Engine**: A custom "glassmorphism" overlay system provides personalized, context-rich tooltips across the dashboard. Table rows recalculate term structure deviations on the fly, and charts provide English-language analytical deductions (e.g., classifying a contract as 'historically cheap' or 'expensive' upon hover).
*   **Overview Hub**: Live front-month metrics, composite conditional Regime detection (Structural vs Elevated states), and a 0–100 weighted Stress Score index to signal funding risk.
*   **Analytics Layer**:
    *   **Panic Spread Signal**: A predictive logistic regression framework forecasting next-day margin shifts. Emits explicit probabilities `P(hike) / P(cut) / P(flat)` and point-estimate target bands.
    *   **Model Health Scorecard**: Tracks real-time backtest health (Hit-rates, Mean Absolute Error, Brier Scores) on rolling 30/90/365 day windows.
    *   **Delta Distribution Histogram**: Visualizes margin changes based on explicit Days-to-Expiry (DTE) buckets (0-30d, 31-90d, 91+d) using dynamic histograms mapped against current daily predictions.
*   **Term Structure**: Complete dual-axis loading curves mapping `NATURALGAS` against `NATGASMINI` weights. Features dynamic P10/P50/P90 confidence cones calculated against specific DTE profiles to detect curve contango or backwardation anomalies.
*   **Historical Scatter & Models**: Over a decade of margin and volatility time-series data featuring two-regime OLS regression lines to map the structural relationship between margin requirements and base market volatility.
*   **Seasonality Checks**: Monthly box plots mapping median variance and tender-period outliers, accompanied by a dynamic Month-by-Year heatmap matrix that highlights deviances from all-time averages.

---

## 🔬 Advanced Analytics Architecture

All statistical enhancements are built natively in the data engineering layer utilizing **numpy + scikit-learn** to ensure heavy mathematical operations are computed once synchronously at build time, rather than taxing the client browser.

| Feature Area | Output Source | Use Case / Value Engine |
|---------|-------------|----------|
| **Forecast Bounds** | `forecast_bands.json` | Computes rolling residual standard deviation per DTE bucket (0-30d, 31-90d, 91+d) for tight ±1σ and ±2σ predictive prediction intervals. |
| **Model Verification** | `model_health.json` | Benchmarks predictive model integrity by scoring historic directional accuracy and symmetric/asymmetric hit-rate drift. |
| **Regime Detection** | `regime_model.json` | Prevents regression line warping by sequestering low-volatility pre-2019 data (Regime A) from modern high-stress states (Regime B). |
| **Structural Variance** | `decomposition.json` | Decomposes official total margins into pure vol-determined margin versus arbitrary MCX 'Policy Buffer'. |
| **Probability Spread** | `event_probabilities.json` | Multi-class logistic regression mapping specific statistical probabilities of an MCX margin hike before market open. |

---

## 📊 Current Database Context

The platform leverages a local highly dense SQLite buffer cached at `data/margins.db`:

| Symbol | Range | Records | Min Margin % | Max Margin % |
| :--- | :--- | :--- | :--- | :--- |
| **NATURALGAS** | `2010-01-01` to `Present` | **86,663+** | 0.00% | 100.00% |
| **NATGASMINI** | `2023-03-14` to `Present` | **38,704+** | 0.00% | 100.00% |

> **Total records**: ~125,367 continuous data points processed securely without blocking browser threads.

---

## 🏗️ System Pipeline Operations

The platform converts daily static calculations into automated analytical streams without external backend servers:

### 1. Scraper Module (`src/scraper.py` + `main.py`)
*   Uses a **Multi-Layered Playwright stealth browser** triggering navigations to safely bypass external session cookies or bot-blocks.
*   Intercepts internal API payloads directly during execution, extracting live market standardized volatility metrics mapped to forward curve arrays.

### 2. Structured Storage (`src/db.py`)
*   A localized fast **SQLite repository** utilizing rich composed composite framing indexes. Bypasses duplications and ensures clean relational continuity across instrument contracts.

### 3. Static Publisher Engine (`export_json.py`)
Continually bundles aggregates drafting fully dense statically loaded caches stored natively inside `docs/data/*.json`. Acts as the statistical backbone containing all linear regression and descriptive stats logic. Filtering algorithms explicitly sequester tender-period outlier skews from corrupting longitudinal metrics.

### 4. Continuous Alerts Pipeline (`alert.py`)
*   Queries historical margin shifts from SQLite date differentials.
*   Auto-flags sudden absolute shifts (> thresholds) triggering rich **HTML Email Alerts via SMTP**, keeping traders aligned ahead of funding timelines or forced liquation events.

### 5. Client Dashboard Interface (`docs/index.html`)
A robust **Vanilla Javascript SPA layout with localized Glassmorphism Tooltip aesthetics**. Renders lightweight requests into parallel structural views using standard concurrent plotting directly in the browser's DOM paint engine.

---

## ⚙️ Automated GitHub Actions Wiring

Operations are defined safely and securely inside `.github/workflows/daily_margin.yml`:

*   **Trigger Schedule**: Runs automatically @ **1:30 & 13:30 UTC** (`7:00 AM & 7:00 PM IST`).
*   **Sequential Pipeline Flow**:
    1. **Fetch & Hydrate**: Bootstraps Playwright to fetch the last 3 days of exchange data to bridge potential weekend or delayed offsets.
    2. **Algorithmic Subroutines**: Triggers the static bundler to build the advanced multi-layer `JSON` database for the webapp.
    3. **Threshold Guard**: Assesses differential algorithms to push SMTP email alerts out if an unforeseen systemic spike is detected.
    4. **Autonomous Commits**: Streams state differentials back directly to the remote repository, closing the continuous integration loop.

---

## 💻 Local Setup Operations

To run pipelines or diagnostics on local machines:

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

**View local live dashboards easily via built-in servers**:
```bash
python export_json.py
cd docs && python -m http.server 8080
```
Then visit: `http://localhost:8080`.
