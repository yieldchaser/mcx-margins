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
- **Trade Intelligence & Capital Calculator:** Interactive backtester supporting NG and NGM futures with multiple chart views (Equity, Daily, Drawdown, Util, Margin, Shield) featuring descriptive hover tooltips, fee modeling (STT, exchange, GST, brokerage), margin call detection, and shareable state via URL hash. Features preset horizons (Full/30D/10D/5D/≤30 DTE), custom lot sizing, and detailed performance metrics (ROI on margin, max drawdown, best/worst days).
- **Risk & Liquidation Shield:** Dynamic card displaying real-time safety metrics—Entry Shield (adverse percentage to liquidation), Worst-case Shield (minimum cushion hit during trade window), and Exit Shield—with dedicated tooltip explanations for RMS square-off thresholds.

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

## The Volatility-Adjusted Margin Buffer (VAMB) & Regime-Shifting Alpha Engine (RSAE v2.0)

The dashboard implements the institutional-grade **Volatility-Adjusted Margin Buffer (VAMB)** and its evolutionary upgrade, the **Regime-Shifting Alpha Engine (RSAE v2.0)**, to protect trading capital against margin-hike liquidations in hyper-volatile commodity contracts like MCX Natural Gas.

### 1. Classical VAMB Sizing Formula

$$\text{Safety Shield} = \min(0.35, \max(0.10, 0.25 \times \sigma_{\text{ann}}))$$

$$\text{Total Required Margin} = \text{SPAN Margin} + \text{Safety Shield}$$

$$\text{Position Lots (Raw)} = \left\lfloor \frac{\text{Capital}}{\text{Price} \times \text{Lot Size} \times \text{Total Required Margin}} \right\rfloor$$

$$\text{Position Lots (Clamped)} = \min\left( \text{Position Lots (Raw)}, \left\lfloor \frac{\text{Capital} \times 2.5}{\text{Price} \times \text{Lot Size}} \right\rfloor \right)$$

*Note: The **2.5× leverage ceiling** acts as a hard stop to prevent over-leverage in artificially low-margin regimes.*

### 2. RSAE v2.0 Asymmetric Sizing Engine
RSAE v2.0 upgrades classical VAMB by introducing direction-decoupled volatility parameters, near-expiry tender week surcharges, path-dependent portfolio drawdown brakes, and dynamic margin-skew contraction.

#### A. Direction-Decoupled Asymmetric Safety Shield
Short positions face unbounded upside risk during short squeezes, requiring a wider buffer:

$$\text{Shield} = \min\left(0.40, \max\left(s_{\text{Min}}, c_{\text{Co}} \times \sigma_{\text{ann}}\right)\right)$$

$$\text{where } s_{\text{Min}} = \begin{cases} 0.10 & \text{for LONG} \\ 0.18 & \text{for SHORT} \end{cases}, \quad c_{\text{Co}} = \begin{cases} 0.25 & \text{for LONG} \\ 0.40 & \text{for SHORT} \end{cases}$$

#### B. Near-Expiry Tender Surcharge & Taper
To prevent near-expiry physical delivery/cash-settlement margin spikes, a linear surcharge $\tau$ and a leverage multiplier $\psi_{\text{DTE}}$ are applied during the final 7 DTE:

$$\tau = \begin{cases} 0.08 \times \frac{8 - \max(\text{DTE}, 0)}{7} & \text{for } \text{DTE} \le 7 \\ 0 & \text{otherwise} \end{cases}$$

$$\psi_{\text{DTE}} = \begin{cases} 0.50 & \text{for } \text{DTE} \le 3 \\ 0.75 & \text{for } \text{DTE} \le 7 \\ 1.00 & \text{otherwise} \end{cases}$$

#### C. Corporate Portfolio Drawdown Brake
To protect capital from path-dependent ruin, a risk-taper brake is applied based on portfolio drawdowns:

$$\text{portfolioBrake} = \begin{cases} 0.40 & \text{for } \text{Drawdown} \ge 0.10 \\ 0.65 & \text{for } \text{Drawdown} \ge 0.05 \\ 1.00 & \text{otherwise} \end{cases}$$

#### D. Compound Margin Sufficiency

$$\text{Margin Requirement } (m_{\text{Req}}) = \text{SPAN Margin} + \text{Shield} + \tau$$

$$\text{Raw Sized Lots } (\text{Lots}_{\text{Raw}}) = \left\lfloor \frac{\text{Capital}}{\text{Price} \times \text{Lot Size} \times m_{\text{Req}}} \right\rfloor$$

#### E. Asymmetric Leverage Ceilings & Skew Contraction
The effective leverage ceiling $l_{\text{eff}}$ adjusts dynamically according to market regime parameters:

$$l_{\text{eff}} = l_{\text{Base}} \times \kappa_{\text{OI}} \times \phi_{\text{Skew}} \times \psi_{\text{DTE}} \times \text{portfolioBrake}$$

* **Base Leverage ($l_{\text{Base}}$):** $3.25$ for LONG, $1.75$ for SHORT.
* **OI Accumulation Boost ($\kappa_{\text{OI}}$):** $1.20$ if LONG and the 5-day continuous aggregate Open Interest trend (`oi_aggregate_build_5d`) is positive, else $1.0$.
* **Margin-Skew Contraction ($\phi_{\text{Skew}}$):** Compresses leverage when initial margin exceeds realized volatility (clearinghouse positioning skew):

  $$\phi_{\text{Skew}} = \min\left(1.0, \max\left(0.40, 1 - 0.15 \times \max(0, \text{marginGap} - 2.0)\right)\right)$$

  $$\text{where } \text{marginGap} = \text{Initial Margin Percent} - (\text{Realized Volatility} \times \sqrt{252})$$

#### F. Dual-Firewall Clamp

$$\text{Ceiling Lots } (\text{Lots}_{\text{Ceil}}) = \left\lfloor \frac{\text{Capital} \times l_{\text{eff}}}{\text{Price} \times \text{Lot Size}} \right\rfloor$$

$$\text{Final Position Lots} = \max\left(0, \min\left(\text{Lots}_{\text{Raw}}, \text{Lots}_{\text{Ceil}}\right)\right)$$

### 3. Empirical Performance & Stress Testing (Feb 2026 Crash)
Based on a systematic day-by-day simulation of the extreme February 2026 contract collapse, entering long on Dec 29, 2025 at ₹305.20 with ₹5L capital:
* **Max Sizing (6 lots, 4.58× leverage):** Liquidated on Dec 31, 2025 (Day 2 of trade) at ₹288.50. Final P&L: **-55.3%** (₹-2,76,750).
* **Classical VAMB Sizing (3 lots, 2.29× leverage):** Survived 24 additional trading days through a 20% crash, a full V-shaped recovery to ₹390.50, and only hit margin call on Feb 3, 2026 when MCX overnight hiked SPAN margins from 34% to 66%. Final P&L: **-27.7%** (₹-138,375).
* **RSAE v2.0 Sizing:** Dynamic adjustments for drawdown thresholds and tender margins further optimize surviving lots to lock in risk reduction as drawdown boundaries are crossed.

### 4. Quantitative Design Critique & Opinion
* **The $4\sigma$ Statistical Cushion:** The 25% coefficient is mathematically calibrated to absorb a $\approx 4\sigma$ daily price shock under a Gaussian framework (since $0.25 \times \sqrt{252} \approx 3.97$). Given Natural Gas's leptokurtic (fat-tailed) returns, this is an appropriate baseline, whereas lower multipliers would fail during volatility-expansion regimes.
* **Firewall Role of the Leverage Ceiling:** The dynamic $l_{\text{eff}}$ ceiling acts as a physical firewall, preventing over-exposure when lagged historical volatility estimators contract the Safety Shield.
* **Asymmetry and Tail-Risk Management:** Decoupling long and short parameters resolves the unbounded tail risk of short commodity squeeze events. Symmetrically sized engines are fundamentally flawed because commodity price distributions exhibit positive skewness (right-tailed risk). RSAE v2.0 addresses this directly by scaling down short base leverage to $1.75\times$ and widening the short safety shield cushion ($18\%$ floor).

---

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
