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
- **Deep Time-Series Analysis:** A dedicated historical engine with an interactive range slider (1M, 3M, 6M, 1Y, 3Y, ALL) plotting absolute Margins, Realized Volatility over time, Margin Component Decomposition, and Market Flow dynamics.
- **10-Year Multi-Regime Macro Simulator:** An institutional-grade compounding engine that models long-term portfolio growth under multi-regime risk conditions:
  - *Cushion Sizing Firewall:* Dynamically calculates max safe leverage ($L_{max}$) and liquid cash shields based on base margin and catastrophic gap-risk buffers to prevent ruin.
  - *Preset & Custom Capital:* Quick preset buttons (35L, 1Cr, 5Cr, 10Cr) and custom numeric input.
  - *Expanded Frequency:* Models scenarios from 0.5 to 12.0 trades per year.
  - *Capacity Sizing Firewall:* Enforces a ₹378 Cr ADV capacity gate (10% of average daily volume), redirecting excess capital overflow to liquid yields (6.5% default).
  - *Tax Sweep Modes:* Simulates corporate tax drag under Section 115BAA (25.168%) via Annual Sweep (with expense tax shielding) or Per-Trade Drag.
  - *SEBI Peak Margin Audit:* Real-time compliance auditing for domestic exchange upfront collection rules to avoid short-collection penalties.


### 4. Seasonality
- **Year-Over-Year Overlays:** Compares historical margin behavior normalized across the Jan–Dec calendar year. Allows easy spotting of structural seasonal hikes (e.g., winter volatility pricing).

### 5. Analytics
- **Machine Learning & Stats:** Random Forest feature importance, margin-to-volatility linear regression, and cross-regime correlation matrices. Generated entirely from backend data and surfaced gracefully.

### 6. Market
- **8-Year Multi-Resolution Deep Zoom Engine (1.65M Candles):** Powered by TradingView Lightweight Charts (HTML5 WebGL/Canvas running at native 60 FPS). Renders continuous front-month price action from 2019 to 2026 unstitched across roll boundaries to preserve true price discovery. Features an intelligent 3-tier Level-of-Detail (LOD) streaming pyramid:
  - *Macro Horizon (8Y / 5Y / 1Y / YTD):* Streams 1,940 daily macro bars (~169 KB).
  - *Swing Horizon (3M / 1M):* Streams ~26,300 high-definition 15-minute bars.
  - *Microstructure Horizon (1W / 1D / Wheel Zoom):* Dynamically streams 1-minute tick-level execution candles from monthly partitions on demand.
  - *Interactive Controls:* Preset horizon buttons, instant Area Line vs Candlesticks toggle, Volume Histogram overlay with dedicated zero-bleed scale isolation, dynamic glassmorphic cursor-following tooltips (with bar return % and volume), and an IST crosshair HUD.
- **Intraday Time-of-Day (TOD) Volatility & Volume Profile:** Analyzes historical volume surges and Garman-Klass realized volatility spikes across every 15-minute window of the trading session (09:00 to 23:30 IST) across 1,618,198 candles. Features US Daylight Saving Time (DST) toggles:
  - *Combined:* 8-year session baseline volume and volatility curve.
  - *US Summer (EDT):* Captures NYMEX Pit opening at 18:30 IST and Thursday EIA storage release at 20:00 IST.
  - *US Winter (EST):* Captures the 1-hour winter shift (NYMEX 19:30 IST, EIA 21:00 IST).
  - *Thursday (EIA):* Isolates the 2.8x volatility explosion during the weekly storage injection/withdrawal release window.
  - *Regular Weekdays:* Organic trading curve excluding Thursday report distortion.
- **Market Intelligence KPIs:** In-depth metrics including Realized Volatility percentiles, exact OI Flow States (e.g., "Long Unwind", "Short Cover"), and Funding Friction scores.
- **Futures Details Panel:** Heatmapped tabular data highlighting liquidity bandwidth and exact PVOI metrics across all active contract months.

### 7. Data Explorer
- **Raw Exportable Data:** A high-density, searchable, and sortable tabular interface of the combined margin + market payloads for quantitative researchers who need raw numbers.

## The Volatility-Adjusted Margin Buffer (VAMB) & Regime-Shifting Alpha Engine (RSAE v3.1)

The dashboard implements the institutional-grade **Volatility-Adjusted Margin Buffer (VAMB)** and its evolutionary upgrades—from the classical linear buffer and **RSAE v2.0** asymmetric engine to the state-of-the-art **RSAE v3.1 coupled convex regime architecture**. The system is engineered to protect trading capital against margin-hike liquidations in hyper-volatile commodity contracts like MCX Natural Gas while safely unlocking commercial leverage during benign market regimes under the **Principle of Asymmetric Aggression**.

### 1. Classical VAMB Sizing Formula (Historical Baseline)

$$\text{Safety Shield} = \min(0.35, \max(0.10, 0.25 \times \sigma_{\text{ann}}))$$

$$\text{Total Required Margin} = \text{SPAN Margin} + \text{Safety Shield}$$

$$\text{Position Lots (Raw)} = \left\lfloor \frac{\text{Capital}}{\text{Price} \times \text{Lot Size} \times \text{Total Required Margin}} \right\rfloor$$

$$\text{Position Lots (Clamped)} = \min\left( \text{Position Lots (Raw)}, \left\lfloor \frac{\text{Capital} \times 2.5}{\text{Price} \times \text{Lot Size}} \right\rfloor \right)$$

*Note: The **2.5x leverage ceiling** acts as a hard stop to prevent over-leverage in artificially low-margin regimes.*

---

### 2. RSAE v2.0 Asymmetric Sizing Engine (Predecessor)
RSAE v2.0 upgraded classical VAMB by introducing direction-decoupled volatility parameters, near-expiry tender week surcharges, path-dependent portfolio drawdown brakes, and dynamic margin-skew contraction.

#### A. Direction-Decoupled Asymmetric Safety Shield
Short positions face unbounded upside risk during short squeezes, requiring a wider buffer:

$$\text{Shield} = \min\left(0.40, \max\left(s_{\text{Min}}, c_{\text{Co}} \times \sigma_{\text{ann}}\right)\right)$$

$$\text{where } s_{\text{Min}} = \begin{cases} 0.10 & \text{for LONG} \\ 0.18 & \text{for SHORT} \end{cases}, \quad c_{\text{Co}} = \begin{cases} 0.25 & \text{for LONG} \\ 0.40 & \text{for SHORT} \end{cases}$$

#### B. Near-Expiry Tender Surcharge & Taper
To prevent near-expiry physical delivery/cash-settlement margin spikes, a linear surcharge $\tau$ and a leverage multiplier $\psi_{\text{DTE}}$ were applied during the final 7 DTE:

$$\tau = \begin{cases} 0.08 \times \frac{8 - \max(\text{DTE}, 0)}{7} & \text{for } \text{DTE} \le 7 \\ 0 & \text{otherwise} \end{cases}$$

$$\psi_{\text{DTE}} = \begin{cases} 0.50 & \text{for } \text{DTE} \le 3 \\ 0.75 & \text{for } \text{DTE} \le 7 \\ 1.00 & \text{otherwise} \end{cases}$$

#### C. Corporate Portfolio Drawdown Brake (Step-Discontinuous)
Applied step-function leverage scale-backs based on portfolio drawdowns:

$$\text{portfolioBrake} = \begin{cases} 0.40 & \text{for } \text{Drawdown} \ge 0.10 \\ 0.65 & \text{for } \text{Drawdown} \ge 0.05 \\ 1.00 & \text{otherwise} \end{cases}$$

#### D. Effective Leverage Ceilings
Static base leverage ($3.25\times$ Long, $1.75\times$ Short) modulated by 5-day Long OI build ($\kappa_{\text{OI}} = 1.20$), margin-skew contraction ($\phi_{\text{Skew}}$), DTE taper, and drawdown brake.

---

### 3. RSAE v3.1 Coupled Convex Regime Architecture (Current Production)

RSAE v3.1 overcomes the structural paradoxes of predecessor models (benign-regime under-leverage and tail-risk vulnerability during simultaneous price shock and intraday margin hikes) through six quantitative upgrades:

#### A. Strict Fail-Closed Validation & Ratio-Verified Multi-Estimator Volatility ($\sigma_{\text{eff}}$)
1. **Fail-Closed Execution:** The engine requires positive capital, valid price, positive lot size, positive SPAN margin, and strictly explicit direction (`LONG` or `SHORT`).
2. **Dimensionless Ratio Normalization:** Separates decimal vs percentage volatility with zero overlap across all 131,977 rows in `margins.db` using the clearinghouse ratio criterion:
   $$\text{If } \frac{\text{initial\_margin\_pct}}{\text{annualized\_volatility}} < 7.5 \implies \text{decimal} = \frac{\text{annualized\_volatility}}{100}, \quad \text{else } \text{decimal} = \text{annualized\_volatility}$$
3. **Multi-Estimator Synthesis:** Combines exchange SPAN implied vol, 20-day rolling realized vol, 20-day Parkinson intraday range vol, and MCXCCL's structural SPAN floor:
   $$\sigma_{\text{eff}} = \max\left(\sigma_{\text{SPAN}},\; \sigma_{\text{RV, 20d}},\; \sigma_{\text{Parkinson, 20d}},\; \frac{M_{\text{SPAN}}}{0.408}\right), \quad \sigma_{\text{daily}} = \frac{\sigma_{\text{eff}}}{\sqrt{250}}$$

#### B. Complete Regulatory Margin Base & Prospective Next-Day Tender Step ($M_{\text{Surch}}$)
Aggregates all statutory clearinghouse obligations and pre-funds the mandatory $+5\%$ daily tender margin escalation for positions held overnight into the tender window:

$$M_{\text{SPAN}} = \frac{\text{initial\_margin\_pct}}{100}, \quad M_{\text{ELM}} = \frac{\text{elm\_pct} \text{ (default 1.25%)}}{100}$$

$$M_{\text{Tender, actual}} = \frac{\text{tender\_margin\_pct} + \text{delivery\_margin\_pct}}{100}$$

$$\tau_{\text{Prospective}} = \begin{cases} \max\left(M_{\text{Tender, actual}},\; 0.05 \times \max(0, 8 - \max(\text{DTE}, 0))\right) & \text{if } \text{DTE} \le 8 \\ M_{\text{Tender, actual}} & \text{if } \text{DTE} > 8 \end{cases}$$

$$M_{\text{Add, dir}} = \begin{cases} \frac{\text{additional\_long\_margin\_pct} + \text{special\_long\_margin\_pct}}{100} & \text{if LONG} \\ \frac{\text{additional\_short\_margin\_pct} + \text{special\_short\_margin\_pct}}{100} & \text{if SHORT} \end{cases}$$

$$M_{\text{Surch, dir}} = M_{\text{ELM}} + \tau_{\text{Prospective}} + M_{\text{Add, dir}}$$

#### C. Coupled Convex Stress Shock & Exchange EWMA Margin-Expansion Shield (Firewall 1: $\text{Lots}_{\text{Raw}}$)
Predecessor models used naive additive shields ($M_{\text{SPAN}} + \text{Shield}$) that assumed capital only needed to cover post-shock margin OR equity loss, causing liquidation when both occurred simultaneously (as on Feb 2, 2026). RSAE v3.1 mathematically couples mark-to-market loss with exchange margin expansion:

1. **Piecewise-Convex Design Stress Shock ($\delta_{\text{dir}}$):**
   $$\delta_{\text{Long}} = \operatorname{clip}\left(0.19 \sigma_{\text{eff}} + 0.35 \max(0, \sigma_{\text{eff}} - 0.38),\; 0.065,\; 0.350\right)$$
   $$\delta_{\text{Short}} = \operatorname{clip}\left(0.25 \sigma_{\text{eff}} + 0.48 \max(0, \sigma_{\text{eff}} - 0.38),\; 0.100,\; 0.420\right)$$
2. **Exchange EWMA Margin Expansion Multiplier ($\gamma_{\text{EWMA}}$):**
   Models MCXCCL's exact $\lambda = 0.94$ return shock update for shock size $k_{\text{shock}} = \delta_{\text{dir}} / \max(0.015, \sigma_{\text{daily}})$:
   $$\gamma_{\text{EWMA}} = \sqrt{0.94 + 0.06 \cdot k_{\text{shock}}^2}, \quad M_{\text{SPAN, post}} = M_{\text{SPAN}} \cdot \gamma_{\text{EWMA}}$$
3. **Coupled Capital Sufficiency Requirement ($m_{\text{Req}}$):**
   $$m_{\text{Req}} = \begin{cases} \delta_{\text{Long}} + (1 - \delta_{\text{Long}}) \cdot \left(M_{\text{SPAN, post}} + M_{\text{Surch, Long}}\right) & \text{if LONG} \\ \delta_{\text{Short}} + (1 + \delta_{\text{Short}}) \cdot \left(M_{\text{SPAN, post}} + M_{\text{Surch, Short}}\right) & \text{if SHORT} \end{cases}$$
   $$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{\text{FreeCapital}}{\text{Price} \times \text{Lot Size} \times m_{\text{Req}}} \right\rfloor$$

#### D. Inverse-Volatility Dynamic Base Leverage & Bidirectional Conviction (Firewall 2: $\text{Lots}_{\text{Ceil}}$)
Replaces static leverage ceilings with a continuous inverse-volatility power law anchored at $\sigma_{\text{ref}} = 0.35$ ($35\%$ annualized volatility), safely expanding commercial leverage in calm regimes while contracting during volatility storms:

$$\mathcal{L}_{\text{Base}}(\sigma_{\text{eff}}) = \begin{cases} \operatorname{clip}\left(3.85 \times \left(\frac{0.35}{\max(0.20, \sigma_{\text{eff}})}\right)^{1.15},\; 0.90,\; 4.50\right) & \text{if LONG} \\ \operatorname{clip}\left(2.60 \times \left(\frac{0.35}{\max(0.20, \sigma_{\text{eff}})}\right)^{1.25},\; 0.65,\; 3.10\right) & \text{if SHORT} \end{cases}$$

- **Bidirectional Conviction Multiplier ($\kappa_{\text{Conv}}$):** Rewards aligned 5-day Open Interest build ($\kappa_{\text{OI}}$) and continuous 20-day trend-momentum ($\kappa_{\text{Mom}}$), capped at $1.25\times$ Long / $1.20\times$ Short, while remaining strictly subordinate to Firewall 1 survival margins.

#### E. Scale-Consistent Margin-Skew, Smooth DTE Taper, and Continuous Drawdown Curve
1. **Scale-Consistent Clearinghouse Margin-Skew Contraction ($\phi_{\text{Skew}}$):**
   Scales realized volatility by MCXCCL's structural SPAN factor ($0.408$) before computing skew gap:
   $$\text{marginGap}_{\text{corr}} = \text{Initial Margin Pct} - 0.408 \times \text{Realized Vol Pct}$$
   $$\phi_{\text{Skew}} = \operatorname{clip}\left(1.0 - 0.08 \times \max(0, \text{marginGap}_{\text{corr}} - 1.5),\; 0.40,\; 1.00\right)$$
2. **Smooth Near-Expiry Liquidity Taper ($\psi_{\text{DTE}}$):**
   Begins at $\text{DTE} = 8$ and ramps smoothly down to $0.25$ without step-function cliff edges:
   $$\psi_{\text{DTE}} = \begin{cases} 1.00 & \text{if } \text{DTE} > 8 \\ \operatorname{clip}\left(\frac{\max(\text{DTE}, 1) - 1}{7},\; 0.25,\; 0.85\right) & \text{if } \text{DTE} \le 8 \end{cases}$$
3. **Continuous Exponential-Quadratic Portfolio Drawdown Brake ($\text{portfolioBrake}$):**
   Eliminates the artificial 35% cliff edge at 5% drawdown with a smooth, continuous convex decay curve:
   $$\text{portfolioBrake}(\text{DD}) = \operatorname{clip}\left(\exp\left(-0.06 \cdot \text{DD} - 0.0025 \cdot \text{DD}^2\right),\; 0.25,\; 1.00\right)$$

| Portfolio Drawdown (DD) | RSAE v2.0 Step Multiplier | RSAE v3.1 Continuous Multiplier | Operational Risk Profile |
| :--- | :--- | :--- | :--- |
| **0.0%** | 1.00 | **1.000** | Full sizing at equity peak |
| **2.0%** | 1.00 | **0.878** | Gentle pre-emptive de-risking |
| **5.0%** | 0.65 (-35% cliff) | **0.696** | Smooth, continuous transition |
| **8.0%** | 0.65 | **0.527** | Continuous risk reduction |
| **10.0%** | 0.40 (-38% cliff) | **0.427** | Smooth transition through 10% threshold |
| **15.0%+** | 0.40 | **0.250** (Floor) | Deep capital protection in severe drawdowns |

#### F. Multi-Firewall Minimum Clamp with Stop-Risk and Liquidity Safety Clamps
The synthesized position size is clamped across capital sufficiency, leverage ceiling, trade-level stop risk ($\text{Lots}_{\text{Stop}}$), and clearinghouse market liquidity ($\text{Lots}_{\text{Liquidity}}$):

$$\text{Lots}_{\text{Ceil}} = \left\lfloor \frac{\text{FreeCapital} \times \left(\mathcal{L}_{\text{Base}} \times \kappa_{\text{Conv}} \times \phi_{\text{Skew}} \times \psi_{\text{DTE}} \times \text{portfolioBrake}\right)}{\text{Price} \times \text{Lot Size}} \right\rfloor$$

$$\text{Final VAMB Lots} = \max\left(0, \min\left(\text{Lots}_{\text{Raw}},\; \text{Lots}_{\text{Ceil}},\; \text{Lots}_{\text{Stop}},\; \text{Lots}_{\text{Liquidity}}\right)\right)$$

$$\text{VAMB Utilization \%} = \begin{cases} 0 & \text{if } \text{Final VAMB Lots} = 0 \\ \min\left(100, \max\left(1, \operatorname{round}\left(\frac{\text{Final VAMB Lots}}{\text{Max Possible Lots}} \times 100\right)\right)\right) & \text{if } \text{Final VAMB Lots} > 0 \end{cases}$$

---

### 4. Empirical Performance & Stress Testing (Feb 2026 Crash)
Based on a systematic day-by-day simulation of the extreme February 2026 contract collapse, entering long on Dec 29, 2025 at ₹305.20 with ₹5L capital:
* **Max Sizing (6 lots, 4.58x leverage):** Liquidated on Dec 31, 2025 (Day 2 of trade) at ₹288.50. Final P&L: **-55.3%** (₹-2,76,750).
* **Classical VAMB Sizing (3 lots, 2.29x leverage):** Survived 24 additional trading days through a 20% crash, a full V-shaped recovery to ₹390.50, and hit margin call on Feb 3, 2026 when MCX overnight hiked SPAN margins from 34% to 66%. Final P&L: **-27.7%** (₹-138,375).
* **RSAE v2.0 Sizing:** Dynamic adjustments for drawdown thresholds and tender margins improved risk posture but failed on Feb 2, 2026 when intraday margin expansion outpaced the additive shield.
* **RSAE v3.1 Coupled Convex Sizing:** Zero margin calls and zero forced liquidations across the entire cycle. The coupled EWMA margin-expansion pre-pricing correctly capped trade sizing to 2 lots at entry, preserving sufficient free collateral to absorb both the 25% price drop and the subsequent clearinghouse margin hike to 66%.

### 5. Quantitative Design Critique & Architecture Comparison
* **Elimination of the Double-Counting Defect:** Classical VAMB and RSAE v2.0 treated MTM equity shock and clearinghouse margin hike as separate additive risks. In reality, they strike simultaneously. RSAE v3.1 solves this by evaluating capital against post-shock equity and expanded exchange margin simultaneously.
* **The Principle of Asymmetric Aggression:** In benign regimes ($\sigma_{\text{ann}} \approx 20\% - 30\%$), v2.0 capped long positions at $3.25\times$ and short positions at $1.75\times$, leaving excessive idle capital. RSAE v3.1 safely scales base leverage up to $4.50\times$ (long) and $3.10\times$ (short) while anchoring survival to the non-negotiable Firewall 1 coupled convex shield.
* **Tail-Risk Asymmetry:** Long commodity exposure is bounded below by zero price, but short exposure faces unbounded right-tail risk from physical squeeze dynamics. RSAE v3.1 maintains strict parameter asymmetry: short base leverage is throttled, short stress shocks are elevated (up to 42%), and the short convex slope ($+0.48$) is 37% steeper than the long slope.

---

## Architecture

The project is split into a robust Python data pipeline and a stateless frontend:

### 1. Data ingestion & surveillance
- [`src/scraper.py`](src/scraper.py): Playwright scraper for MCX CCL daily margin data
- [`scripts/main.py`](scripts/main.py): Fetch a specific trading date
- [`scripts/fetch_today.py`](scripts/fetch_today.py): Retry-oriented daily fetch
- [`scripts/lookback.py`](scripts/lookback.py): Recent-gap backfill
- [`scripts/backfill.py`](scripts/backfill.py): Historical backfill
- [`scripts/fetch_prices.py`](scripts/fetch_prices.py): MCX futures bhavcopy scraper into `data/prices.db`
- [`scripts/alert.py`](scripts/alert.py): Real-time multi-expiry clearing risk surveillance & institutional alert engine

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
|   |-- js/
|   |   `-- deep_chart.js
|   `-- data/
|-- scripts/
|   |-- alert.py
|   |-- auto_market_snapshot.py
|   |-- build_lod_pyramid.py
|   |-- export_json.py
|   |-- export_tod_seasonality.py
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
    |-- test_audit_fixes.py
    |-- test_commodity_harvester.py
    |-- test_deep_lod.py
    |-- test_fetch_prices.py
    |-- test_margin_integrity.py
    `-- test_market_export.py
```

## Automation & Clearing Surveillance

### Margin & Clearing Risk Surveillance Workflow
Defined in [`daily_margin.yml`](.github/workflows/daily_margin.yml):
- **Multi-Tier Cron Schedule (Mon–Fri):**
  - `08:50 AM IST` (10 min before market open)
  - `09:15 AM IST` (opening bell catch)
  - `09:45 AM IST` (mid-morning backup)
  - `11:30 AM IST` (late morning safety net)
  - `10:30 AM IST (Sat)` (weekend reconciliation sweep)
- **Scrapes New Margin Files:** Queries MCX CCL for daily SPAN margin parameters.
- **Lookback Gap-Fill:** Self-heals any missing trading dates from the prior 5 weekdays.
- **Automated Clearing Surveillance & Alerting ([`scripts/alert.py`](scripts/alert.py)):**
  - **Full Term Structure Surveillance:** Scans all active contracts ($DTE \ge 0$) simultaneously, rather than monitoring only the front month.
  - **Total Gross Margin %:** Always reports Total Margin % (Initial Margin + Tender Period Margin + ELM) as the primary headline KPI.
  - **Overnight Capital Quantification:** Merges with `data/prices.db` settlement prices to compute exact ₹ Capital Required per Lot (1,250 mmBtu) and overnight capital calls or releases.
  - **Tender Delivery vs. Volatility Attribution:** Distinguishes routine scheduled tender steps (+5%/day over the 5-day delivery window) from genuine SPAN volatility shocks ($\ge 2.0\text{ pp}$), suppressing false alarms while flagging initial tender window entrance and compound volatility shocks.
  - **Institutional Email Advisory:** Dispatches a structured, mobile-responsive HTML notice to risk managers when actionable margin shocks occur.
- **Static Export & Git Push:** Regenerates dashboard JSON and pushes updated databases to GitHub Pages.
- **Relays Intraday Loop:** Triggers the live market snapshot runner during MCX session hours.

### Price & LOD Pyramid Workflow
Defined in [`daily_prices.yml`](.github/workflows/daily_prices.yml):
- Refreshes futures price/volume/OI data from MCX bhavcopy (runs post-close at `00:15 AM`, `01:00 AM`, `05:00 AM`, and `09:05 AM IST`).
- Re-runs JSON export so linked market outputs stay synchronized.
- Runs incremental LOD pyramid builder (`python scripts/build_lod_pyramid.py --incremental`) to append new daily trading bars to the Deep Zoom chart.
- Commits updated DB and static files directly to GitHub Pages.

## MCX Quant Vault (6.18M Records)

The repository includes scripts to manage an institutional data vault stored in `data/mcx_vault/`, containing **6,182,507 execution records** across 25 Parquet datasets:

| Category | Datasets | Records | Description |
| :--- | :--- | :--- | :--- |
| **Benchmark Continuous Futures** | `NATURALGAS` & `NATGASMINI` | 2,715,075 | 1-minute & 5-minute continuous futures (2019–2026) |
| **Options Order Flow** | `naturalgas_options_oct26` & `natgasmini_options` | 1,635,850 | All-strikes CE/PE 1-minute execution series |
| **Unstitched Contract Futures** | 12 monthly contracts (OCT, NOV, DEC, JAN, FEB, MAR) | 458,844 | Clean contract boundaries with zero roll distortion |
| **Cross-Asset Commodities** | `CRUDEOIL`, `GOLD`, `SILVER`, `COPPER` | 881,723 | 1-year continuous 1-minute series for cross-commodity correlation |

*Audit catalog available in [`data/mcx_vault/VAULT_CATALOG.md`](data/mcx_vault/VAULT_CATALOG.md).*

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
pytest -v
```
Current test coverage spans 36 automated unit & regression tests across:
- **Margin Surveillance & Alert Integrity:** Multi-expiry surveillance, DTE sorting, post-expiry rejection, tender attribution, and tie-breaking by `file_id`.
- **Market Export & Signal Analytics:** Front-month selection, rolling PVOI enrichment, explainable regime classification, freshness status, and causal percentile rank isolation.
- **Deep LOD & Microstructure Parity:** 1-minute monthly partitions, 15-minute streaming tiers, LOD pyramid integrity, dynamic options chains, and continuous contract crosswalks.
- **Quant Vault Integrity:** Parquet schema validation, DuckDB views, and zero-shrink invariants.

## Notes
- The dashboard is fully static at runtime; expensive analytics are computed entirely in Python during export.
- `numpy` and `scikit-learn` enable the heavier statistical outputs, but the site still renders core data natively in the browser.
- Margin-only usage still works gracefully even if `data/prices.db` is completely absent or empty.
