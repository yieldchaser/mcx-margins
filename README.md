# Blue Margin

Blue Margin is a static, high-fidelity intelligence dashboard for MCX Natural Gas margins and futures market data. It provides an institutional-grade visual interface for quantitative market analysis without requiring any active backend server.

It scrapes:
- MCX CCL daily margin files into `data/margins.db`
- MCX futures bhavcopy price, volume, and open-interest data into `data/prices.db`

It then computes complex analytics in Python (using `numpy`, `scikit-learn`, `scipy`) and exports precomputed JSON to `docs/data/`. The dashboard (`docs/index.html`) renders these datasets completely client-side using Vanilla JS, modern CSS, and Chart.js.

[![Live Dashboard](https://img.shields.io/badge/live-dashboard-3fb950?style=for-the-badge)](https://yieldchaser.github.io/mcx-margins/)
[![GitHub Actions](https://img.shields.io/badge/github-actions-automated-388bfd?style=for-the-badge)](https://github.com/yieldchaser/mcx-margins/actions)

## Dashboard Features (The 7 Tabs)

The frontend features a premium, glassmorphic UI spanning 7 specialized tabs:

### 1. Overview
- **Market Context:** At-a-glance KPIs (Front Close, Return, Volume Shock, OI Change, Liquidity Score) with semantic color-coding.
- **Price vs Margin Confluence:** A trailing 60-day interactive chart overlaying front-month price action against margin requirements to spot immediate divergences.
- **Stress & Regime Scoring:** Real-time composite indicators determining if the market is in a structural calm or high-stress, pre-hike regime.

### 2. Term Structure
- **Historical Forward Curves:** Visualizes the evolution of the margin and price curves. Overlays today's curve against the 1-week, 1-month, and 1-year historical curves to measure structural shifts in maturity expectations.

### 3. History
- **Deep Time-Series Analysis:** A dedicated historical engine with an interactive range slider (1M, 3M, 6M, 1Y, 3Y, ALL).
- Plots absolute Margins, Realized Volatility over time, Margin Component Decomposition, and Market Flow dynamics.

### 4. Seasonality
- **Year-Over-Year Overlays:** Compares historical margin behavior normalized across the Jan–Dec calendar year. Allows easy spotting of structural seasonal hikes (e.g., winter volatility pricing).

### 5. Analytics
- **Machine Learning & Stats:** Random Forest feature importance, margin-to-volatility linear regression, and cross-regime correlation matrices. Generated entirely from backend data and surfaced gracefully.

### 6. Market
- **Market Intelligence KPIs:** In-depth metrics including Realized Volatility percentiles, exact OI Flow States (e.g., "Long Unwind", "Short Cover"), and Funding Friction scores.
- **Futures Details Panel:** Heatmapped tabular data highlighting liquidity bandwidth and exact PVOI metrics across all active contract months.

### 7. Data Explorer
- **Raw Exportable Data:** A high-density, searchable, and sortable tabular interface of the combined margin + market payloads for quantitative researchers who need raw numbers.

## Architecture

The project is split into a robust Python data pipeline and a stateless frontend:

### 1. Data ingestion
- [`src/scraper.py`](src/scraper.py): Playwright scraper for MCX CCL daily margin data
- [`scripts/main.py`](scripts/main.py): Fetch a specific trading date
- [`scripts/fetch_today.py`](scripts/fetch_today.py): Retry-oriented daily fetch
- [`scripts/lookback.py`](scripts/lookback.py): Recent-gap backfill
- [`scripts/backfill.py`](scripts/backfill.py): Historical backfill
- [`scripts/fetch_prices.py`](scripts/fetch_prices.py): MCX futures bhavcopy scraper into `data/prices.db`

### 2. Storage
- `data/margins.db`: Source of truth for margin observations
- `data/prices.db`: Source of truth for futures PVOI (Price/Volume/OI) observations

### 3. Static publishing
- [`scripts/export_json.py`](scripts/export_json.py): Builds the entire JSON API used by the dashboard. Applies deduplication, active-curve scoping, rolling volatility calculations, and cross-regime statistics.
- [`docs/index.html`](docs/index.html): The static client-side dashboard file containing all layout, CSS tokens, and rendering logic.

## JSON outputs

The Python pipeline exports heavily structured payloads:

### Core margin outputs
- `docs/data/current.json`
- `docs/data/history_ng.json` / `history_ngm.json`
- `docs/data/forward_curve.json`
- `docs/data/contract_index.json`
- `docs/data/contract/<sym>/<EXPIRY>.json`

### Market and linkage outputs
- `docs/data/market/meta.json`
- `docs/data/market/current.json`
- `docs/data/market/history_ng.json` / `history_ngm.json`
- `docs/data/market/forward_curve.json`
- `docs/data/market/curve_history.json`
- `docs/data/market/margin_joined_front.json`
- `docs/data/market/cross_regimes.json`
- `docs/data/market/signals.json`
- `docs/data/market/contract/<sym>/<EXPIRY>.json`

*Note: The system explicitly aligns margin expiries with market expiries to calculate exact `margin_vs_realized_vol_gap`, `margin_per_liquidity`, and `funding_friction_score` metrics.*

## Repo layout

```text
.
|-- data/
|   |-- margins.db
|   `-- prices.db
|-- docs/
|   |-- index.html
|   `-- data/
|-- scripts/
|   |-- export_json.py
|   |-- fetch_prices.py
|   |-- fetch_today.py
|   |-- backfill.py
|   |-- lookback.py
|   |-- main.py
|   `-- query.py
|-- src/
|   |-- db.py
|   `-- scraper.py
`-- tests/
    `-- test_market_export.py
```

## Automation

### Margin workflow
Defined in [`daily_margin.yml`](.github/workflows/daily_margin.yml):
- Fetches new margin data
- Bridges recent gaps if any
- Regenerates dashboard JSON
- Commits refreshed `data/` and `docs/data/` straight to GitHub Pages

### Price workflow
Defined in [`daily_prices.yml`](.github/workflows/daily_prices.yml):
- Refreshes futures price/volume/OI data from MCX bhavcopy
- Re-runs JSON export so linked market outputs stay perfectly synchronized
- Commits updated DB and static files

## Local setup

Install dependencies:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Fetch data:
```bash
# one trading date
python scripts/main.py YYYY-MM-DD

# daily retry fetch
python scripts/fetch_today.py

# price / volume / OI refresh
python scripts/fetch_prices.py
```

Regenerate the static dashboard data:
```bash
python scripts/export_json.py
```

Run the site locally:
```bash
cd docs
python -m http.server 8080
```
Then open `http://localhost:8080`.

## Testing

Run the test suite:
```bash
python -m unittest
```
Current test coverage includes market-export helpers for:
- Front-month contract selection
- Rolling PVOI metric enrichment
- Explainable signal generation
- Freshness logic & margin-row dedupe priority
- Joined-summary filtering and curve-history generation

## Notes
- The dashboard is fully static at runtime; expensive analytics are computed entirely in Python during export.
- `numpy` and `scikit-learn` enable the heavier statistical outputs, but the site still renders core data natively in the browser.
- Margin-only usage still works gracefully even if `data/prices.db` is completely absent or empty.
