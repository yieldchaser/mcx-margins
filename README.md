# Blue Margin — NG Margin Intelligence

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

## 📈 Dashboard Components: Charts & Tables Guide

The dashboard is structured into six analytical tabs, each hosting specialized visualization components and dynamic tables. 

### 1. Overview Tab
*   **Current Margin Snapshot Table**: The command center. Displays all active expiries for a selected symbol (`NATURALGAS` or `NATGASMINI`), detailing Days-To-Expiry (DTE), Initial %, ELM %, Tender %, Total %, and Annualized Volatility. Crucially, it calculates a **Historical Percentile (Hist. Pct)**, benchmarking today's margin against all historical precedents at the exact same DTE range to pinpoint if current funding costs are historically cheap or expensive.
*   **Forward Curve — Today**: A rapid-assessment line chart plotting the term structure of margin requirements for both the primary and mini contracts.
*   **Panic Spread Signals Table**: A predictive intelligence matrix. Utilizing a logistic regression model, it outputs probabilities across three explicit tomorrow-states: Margin Cut, Flat, or Margin Hike.

### 2. Term Structure Tab
*   **Forward Margin Curve (with Confidence Cones)**: Plots the full spine of active expiries against historical confidence cones (P10 to P90 bounds), toggleable between "All-time" and "Recent (5Y)" lookback windows. This visually highlights anomalies where spot margins violently breach standard term structure contango/backwardation models.
*   **Volatility Term Structure**: Maps implied annualized structural volatility across the forward curve.
*   **Margin Spread (NATURALGAS vs NATGASMINI)**: Tracks the basis spread directly between the large and mini contracts to highlight liquidity divergences or exchange pricing inefficiencies.

### 3. History Tab
*   **Initial Margin % Over Time**: A longitudinal line chart mapping front-month margin requirements from 2010 to Present. Supports dynamic timeframe toggling (1M through All-time) and an overlay of underlying Henry Hub (Spot) Prices.
*   **Daily Volatility Over Time**: The sister chart to margin history, demonstrating how structural volatility regimes trigger exchange margin interventions.
*   **Margin vs Volatility (Scatter)**: Maps the base relationship between daily volatility (X) and margin requirement (Y). Visualizes the structural relationship and the exchange's linear reactivity models.
*   **Margin Decomposition**: A stacked area chart diagnosing what portion of the current margin is fundamentally driven by "Structural Volatility" versus discretionary "Exchange Policy Buffers".

### 4. Seasonality Tab
*   **Average Margin by Month**: Bar chart exposing structural calendar biases (e.g., winter vs summer funding profiles) dating back to 2010.
*   **Average Margin by Year**: Macro-year aggregations highlighting multi-year structural margin inflation or deflation vectors.
*   **Monthly Margin Heatmap**: An institutional Year × Month gradient matrix table. Identifies localized seasonal clusters, historical anomalies, and exact time-of-year funding peaks.

### 5. Analytics Tab
*   **Model Health Scorecard**: A transparent backtest audit table evaluating the accuracy of the proprietary predictive models across 30-day, 90-day, and 365-day rolling windows.
*   **DTE vs Margin Scatter**: Demonstrates the nonlinear degradation (or acceleration) of margin requirements as physical settlement approaches.
*   **Lag Correlation**: Analyzes the specific time lag (between T+0 to T+10) coupling sudden volatility shifts to MCX regulatory margin responses.
*   **Margin Prediction Model (Panic Spread Full View)**: Plots Current vs Predicted bounds across the active forward array to identify broad over/under-pricing.
*   **Margin Change Distribution Histogram**: Segments historically realized Day-over-Day margin shifts into precise Days-To-Expiry groups (e.g., 0-30d vs 91+d), mapping the probability of extreme jump-risk tail events.
*   **5-Day Rolling Average vs Spot Margin**: Tracks short-term momentum crossover against spot margins.
*   **Historical Percentile Rank Over Time**: An All-Time Historical Percentile time-series mapping relative stress across the historical sample period.

### 6. Data Explorer Tab
*   **Raw Data Explorer Table**: A fully paginated, sortable environment rendering the underlying SQL outputs with specific day-by-day telemetry. Supports seamless unpaginated CSV dumps for offline quant modeling.

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
