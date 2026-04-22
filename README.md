# Blue Margin

Blue Margin is a static, GitHub Pages-hosted intelligence dashboard for MCX natural gas margins and futures market data.

It scrapes:

- MCX CCL daily margin files into `data/margins.db`
- MCX futures bhavcopy price, volume, and open-interest data into `data/prices.db`

It then exports precomputed JSON to `docs/data/` so the dashboard in `docs/index.html` can render everything client-side with no backend.

[![Live Dashboard](https://img.shields.io/badge/live-dashboard-3fb950?style=for-the-badge)](https://yieldchaser.github.io/mcx-margins/)
[![GitHub Actions](https://img.shields.io/badge/github-actions-automated-388bfd?style=for-the-badge)](https://github.com/yieldchaser/mcx-margins/actions)

## What the dashboard covers

### Margin intelligence

- Live and historical margin term structure for `NATURALGAS` and `NATGASMINI`
- Contract lifecycle analysis with date/DTE toggles
- Regime, seasonality, decomposition, stress, percentile, and prediction views
- Tender-zone behavior and front-month margin monitoring

### Market and PVOI intelligence

- Front-month price, return, realized-volatility, volume, and open-interest tracking
- Price/OI positioning states such as `long_build`, `short_build`, `long_unwind`, and `short_cover`
- Curve and liquidity views across active expiries
- Event windows, liquidity heatmaps, and active-contract leaderboards

### Margin x market linkage

- Front-month joined views only when margin expiry and market expiry truly match
- Contract-specific lifecycle overlays using exact `symbol + expiry` payloads
- Precomputed linkage metrics such as:
  - `margin_change_1d`
  - `margin_change_5d`
  - `margin_price_divergence`
  - `margin_vs_realized_vol_gap`
  - `margin_per_liquidity`
  - `funding_friction_score`

## Architecture

### 1. Data ingestion

- [`src/scraper.py`](src/scraper.py): Playwright scraper for MCX CCL daily margin data
- [`scripts/main.py`](scripts/main.py): fetch a specific trading date
- [`scripts/fetch_today.py`](scripts/fetch_today.py): retry-oriented daily fetch
- [`scripts/lookback.py`](scripts/lookback.py): recent-gap backfill
- [`scripts/backfill.py`](scripts/backfill.py): historical backfill
- [`scripts/fetch_prices.py`](scripts/fetch_prices.py): MCX futures bhavcopy scraper into `data/prices.db`

### 2. Storage

- `data/margins.db`: source of truth for margin observations
- `data/prices.db`: source of truth for futures PVOI observations

### 3. Static publishing

- [`scripts/export_json.py`](scripts/export_json.py): builds the JSON data API used by the dashboard
- [`docs/index.html`](docs/index.html): static client-side dashboard

The exporter now hardens contract integrity by:

- deduplicating same-day margin rows at export time
- emitting symbol-scoped contract payloads
- preserving explicit series scope on integrated datasets:
  - `front_month`
  - `active_curve`
  - `specific_expiry`

## JSON outputs

### Core margin outputs

- `docs/data/current.json`
- `docs/data/history_ng.json`
- `docs/data/history_ngm.json`
- `docs/data/forward_curve.json`
- `docs/data/contract_index.json`
- `docs/data/contract/ng/<EXPIRY>.json`
- `docs/data/contract/ngm/<EXPIRY>.json`

### Market and linkage outputs

- `docs/data/market/meta.json`
- `docs/data/market/current.json`
- `docs/data/market/history_ng.json`
- `docs/data/market/history_ngm.json`
- `docs/data/market/forward_curve.json`
- `docs/data/market/contract_index.json`
- `docs/data/market/contract_crosswalk.json`
- `docs/data/market/curve_history.json`
- `docs/data/market/margin_joined_front.json`
- `docs/data/market/cross_regimes.json`
- `docs/data/market/signals.json`
- `docs/data/market/contract/ng/<EXPIRY>.json`
- `docs/data/market/contract/ngm/<EXPIRY>.json`

Important contract-path change:

- old margin payload path: `docs/data/contract/<EXPIRY>.json`
- current margin payload path: `docs/data/contract/<sym>/<EXPIRY>.json`

The market payload structure has the same symbol-scoped pattern:

- `docs/data/market/contract/<sym>/<EXPIRY>.json`

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

- fetches new margin data
- bridges recent gaps
- regenerates dashboard JSON
- can send alerts
- commits refreshed `data/` and `docs/data/`

### Price workflow

Defined in [`daily_prices.yml`](.github/workflows/daily_prices.yml):

- refreshes futures price/volume/OI data
- runs export again so linked market outputs stay fresh
- commits updated price DB and static JSON

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

# recent lookback repair
python scripts/lookback.py

# historical backfill
python scripts/backfill.py

# price / volume / OI refresh
python scripts/fetch_prices.py
```

Regenerate the static dashboard data:

```bash
python scripts/export_json.py
```

Run the site locally:

```bash
python scripts/export_json.py
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

- front-month contract selection
- rolling PVOI metric enrichment
- explainable signal generation
- freshness logic
- margin-row dedupe priority
- contract alignment states
- joined-summary filtering
- curve-history generation

## Notes

- The dashboard is fully static at runtime; expensive analytics are computed in Python during export.
- `numpy` and `scikit-learn` enable the heavier statistical outputs, but the site still renders core data without a backend service.
- Margin-only usage still works even if `data/prices.db` is absent; market outputs degrade gracefully.
