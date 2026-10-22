# MCX Natural Gas Platform: Comprehensive Chart & Tab Candidate Audit for Improvement

---

## 1. System Context & Operational Mandate

This document provides a completely self-contained technical audit of a proprietary quantitative risk and trading analytics platform built for **MCX Natural Gas futures** (Multi Commodity Exchange of India).

### 1.1 The Operational Mandate
Natural Gas on MCX is one of the most volatile energy derivatives in global clearing:
- Characterized by extreme winter price shocks (polar vortex freezes), Thursday US EIA inventory report gaps, and clearinghouse margin hikes of up to $+10.00\%$ overnight.
- Operates under strict clearinghouse (MCXCCL / SEBI) risk parameters: Initial SPAN margin (dynamic VaR), Extreme Loss Margin (ELM, fixed at 1.25%), mandatory physical tender delivery ramps (+5% per day during the final 5 days before expiration, up to 25%), and discretionary exchange surveillance surcharges.
- **The Core Problem**: Unanticipated margin hikes and physical delivery ramps force accounts into immediate Risk Management System (RMS) liquidation if cash buffers are inadequate.
- **Lot Multiplier**: 1 standard MCX Natural Gas contract = 1,250 MMBtu. A 1% margin change on a ₹265 contract is ₹3,312.50 per lot; on a ₹600 contract it is ₹7,500 per lot.

### 1.2 Purpose of This Audit
The platform spans 7 functional areas: **Market Intel & Microstructure**, **Analytics & Models**, **Seasonality**, **History & Regime**, **Term Structure**, **Data Explorer**, and **Overview Auxiliary Charts**. Across these areas, there are 29 distinct visualization candidates, mathematical models, and analytical tools.

This document systematically audits every candidate chart and subtab across the platform: **what it displays on screen, the data and scripts behind it, the mathematical formulation, what we are trying to achieve, its ranking tier, and why it qualifies for improvement, overhaul, or removal.**

## 2. Tab-by-Tab Candidate Evaluation & Detailed Quant Audit

---

### TAB 1: MARKET INTEL & MICROSTRUCTURE (`tab-market`)

The Market tab provides high-frequency microstructure, order flow, and curve intelligence, ingesting over 1.65 million rows of continuous 1-minute and 5-minute parquet tick data and live intraday snapshots.

#### Candidate Rankings in Market Tab:
1. **Rank 1 (Tier 1)**: `TradingView Lightweight Multi-Tier Deep Chart` (`deepChartContainer`)
2. **Rank 2 (Tier 1)**: `Time-of-Day (TOD) Intraday Seasonality Profile` (`chartTODSeasonality`)
3. **Rank 3 (Tier 1)**: `Price/OI 4-Quadrant Phase Map` (`chartMarketPhase`)
4. **Rank 4 (Tier 1)**: `Active Futures Curve & Contango Structure` (`chartMarketCurve`)
5. **Rank 5 (Tier 1)**: `Futures Curve Evolution Overlay` (`chartMarketCurveHistory`)
6. **Rank 6 (Tier 1)**: `Realized Volatility & 3-Regime Classification` (`chartMarketRegime`)
7. **Rank 7 (Tier 2)**: `Volume & Open Interest Flow` (`chartMarketFlow`)
8. **Rank 8 (Tier 2)**: `Contract Capital Efficiency Map` (`chartMarketEfficiency`)
9. **Rank 9 (Tier 2)**: `Margin vs PVOI Linkage Matrix` (`chartMarketLinkage`)
10. **Rank 10 (Tier 3)**: `Front-Month Price & Returns (Static Chart.js)` (`chartMarketPrice`)

---

#### 1. TradingView Lightweight Multi-Tier Deep Chart (`deepChartContainer`)
- **Ranking**: **Tier 1 (Flagship Execution Surface)**
- **What It Displays on Screen**:
  - Full-width interactive candlestick chart powered by TradingView Lightweight Charts (60 FPS hardware-accelerated canvas).
  - Multi-tier resolution switcher: Daily bars, 15-minute intraday candles, and 1-minute tick candles.
  - Contract Selector: Toggle between Continuous Rollover Series and specific active contract expiries (Nov '26, Dec '26, Jan '27...).
  - Session VWAP (Volume-Weighted Average Price) plotted as an orange curve with dynamic $\pm 1\sigma$ and $\pm 2\sigma$ standard deviation bands.
  - Volume histogram bars below candles, color-coded by bar direction.
  - Live 30-second polling status indicator (e.g., `● MCX Live: 22 Oct 15:15 IST - ₹262.10`).
- **Data & Script Engine**:
  - Scripts: `docs/js/deep_chart.js` (`initDeepChart`, `loadDailyTier`, `load15mTier`, `load1mTier`), `scripts/auto_market_snapshot.py`, `scripts/build_lod_pyramid.py`.
  - Data: `data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet`, `data/mcx_vault/NATURALGAS_5m_continuous_2019_2026.parquet`, and `docs/data/market_snapshot.json`.
- **Mathematical & Quant Formulation**:
  - **Session VWAP**: Reset daily at 09:00 IST open:
    $$\text{VWAP}_t = \frac{\sum_{i=1}^t P_i \cdot V_i}{\sum_{i=1}^t V_i}$$
  - **Volume-Weighted Variance**:
    $$\sigma_{\text{VWAP}, t}^2 = \frac{\sum_{i=1}^t V_i \cdot (P_i - \text{VWAP}_t)^2}{\sum_{i=1}^t V_i}$$
  - **Bands**: $\text{Upper Band}_k = \text{VWAP}_t + k \cdot \sigma_{\text{VWAP}, t}$, $\text{Lower Band}_k = \text{VWAP}_t - k \cdot \sigma_{\text{VWAP}, t}$ ($k \in \{1, 2\}$).
- **What We Are Trying to Do**:
  - Provide an institutional trade timing interface where traders can execute intraday positions around volume-weighted mean reversion levels and identify institutional participation.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: It operates as a standard technical analysis chart. It is completely disconnected from the clearinghouse margin models. It does not display the upper and lower intraday hike trigger boundaries ($P_{\text{up}}^*, P_{\text{dn}}^*$) calculated in the Command Center. Traders cannot visually see how close the live candlestick is to triggering an overnight margin spike.

---

#### 2. Time-of-Day (TOD) Intraday Seasonality Profile (`chartTODSeasonality`)
- **Ranking**: **Tier 1 (Institutional Microstructure Tool)**
- **What It Displays on Screen**:
  - 15-minute interval bar/line chart covering every trading interval across MCX hours (09:00 to 23:30/23:55 IST).
  - Displays three simultaneous series per interval:
    1. **Average Absolute Move %** (blue line): Volatility energy per interval.
    2. **Directional Return Drift %** (green/red bars): Statistical upward or downward bias.
    3. **Volume Share %** (gray background area): Proportion of daily volume traded in that window.
  - Interactive profile buttons: **Combined Session**, **Pre-US Overlap (09:00–17:00 IST)**, **US Overlap (17:00–23:30 IST)**, and **EIA Thursdays (Inventory Shock Window)**.
- **Data & Script Engine**:
  - Script: `docs/js/deep_chart.js` (`initTODSeasonality`), `scripts/export_tod_seasonality.py`.
  - Data: `docs/data/tod_seasonality.json` (compiled from 1.65 million 1m/5m historical bars).
- **Mathematical & Quant Formulation**:
  - For each 15-minute interval $i \in [1, 59]$ on day $d$:
    $$r_{d, i} = \frac{C_{d, i} - O_{d, i}}{O_{d, i}}$$
  - **Mean Absolute Volatility**: $\text{Vol}_i = \frac{1}{N} \sum_{d=1}^N |r_{d, i}| \times 100$
  - **Directional Bias (Drift)**: $\text{Drift}_i = \frac{1}{N} \sum_{d=1}^N r_{d, i} \times 100$
  - **Volume Fraction**: $\text{VolShare}_i = \frac{\sum_{d=1}^N V_{d, i}}{\sum_{d=1}^N V_{d, \text{total}}}$
- **What We Are Trying to Do**:
  - Exploit structural commodity microstructure. MCX Natural Gas follows global gas benchmarks (Henry Hub, TTF). Empirical data proves that over $82\%$ of daily volume and price velocity occurs during the US overlap session (post 17:30 IST), peaking between 19:30 and 21:30 IST. The tool prevents traders from getting trapped during morning illiquid noise.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Displays a static historical distribution. It does not overlay *today's live intraday return and volume path* against the historical expectation. Traders cannot see whether today's session is running hot or cold compared to the historical profile.

---

#### 3. Price/OI 4-Quadrant Phase Map (`chartMarketPhase`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - 2D scatter state-space.
  - $X$-axis: Daily Price Return % ($\Delta P$).
  - $Y$-axis: Daily Open Interest Change % ($\Delta OI$).
  - Origin crosshair at $(0, 0)$ dividing space into 4 colored quadrants:
    - Top-Right (Green): **Long Build** ($\Delta P > 0, \Delta OI > 0$)
    - Top-Left (Red): **Short Build** ($\Delta P < 0, \Delta OI > 0$)
    - Bottom-Left (Amber): **Long Unwind** ($\Delta P < 0, \Delta OI < 0$)
    - Bottom-Right (Blue): **Short Cover** ($\Delta P > 0, \Delta OI < 0$)
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderMarketPhaseMap`).
  - Data: `docs/data/market_intelligence.json`.
- **Mathematical & Quant Formulation**:
  $$\Delta P_t = \frac{P_t - P_{t-1}}{P_{t-1}} \times 100, \quad \Delta OI_t = \frac{OI_t - OI_{t-1}}{OI_{t-1}} \times 100$$
- **What We Are Trying to Do**:
  - Track institutional order flow commitment. When aggressive Short Building occurs during rapid price declines, it signals vulnerable, crowded short positioning. In Natural Gas, crowded shorts are frequently trapped by sudden weather revisions, resulting in violent short squeezes that trigger emergency clearinghouse margin hikes.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Points are uniform dots. There is no volume-weighting (a 500-lot day looks identical to a 50,000-lot day), no contract maturity filtering, and no temporal trail vector showing how a contract transitioned through quadrants over consecutive days.

---

#### 4. Active Futures Curve (`chartMarketCurve`) & Curve Evolution (`chartMarketCurveHistory`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - `chartMarketCurve`: Line chart connecting Settle Prices across all active consecutive monthly expiries (M1 through M6).
  - `chartMarketCurveHistory`: Overlays the curve from Today against 1 Week Ago, 1 Month Ago, and 3 Months Ago.
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderMarketCurve`, `renderMarketCurveHistory`).
  - Data: `docs/data/market_intelligence.json`.
- **Mathematical & Quant Formulation**:
  - Term structure slope:
    $$S_{i, j} = \frac{F(T_j) - F(T_i)}{T_j - T_i}$$
  - $S > 0$: Contango (storage carrying cost / winter premium). $S < 0$: Backwardation (immediate physical scarcity).
- **What We Are Trying to Do**:
  - Provide physical commodity term structure context. Natural Gas term structure flips dramatically between winter heating months (steep contango into Jan/Feb) and spring injection shoulder months (abrupt flattening).
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Shows nominal prices only. It does not translate the curve shape into actionable trading metrics: annualized roll yield, calendar spread difference ($M1 - M2$), or contango drag in ₹/lot per day.

---

#### 5. Realized Volatility & 3-Regime Bands (`chartMarketRegime`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - Time series line chart of 20-day rolling annualized realized volatility.
  - Divided into 3 horizontal regime bands:
    - **Calm** ($\le 35\%$, green shading)
    - **Elevated** ($35\%–60\%$, amber shading)
    - **Panic** ($> 60\%$, red shading)
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderMarketRegime`), `docs/data/market_intelligence.json`.
- **Mathematical Formulation**:
  $$\sigma_{20} = \sqrt{252} \cdot \sqrt{\frac{1}{19}\sum_{i=1}^{20} (r_i - \bar{r})^2} \times 100$$
- **What We Are Trying to Do**:
  - Contextualize current market behavior. In Calm regimes, Natural Gas mean-reverts within predictable price channels. In Panic regimes ($>60\%$), clearinghouse SPAN models activate non-linear margin expansion.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Uses standard close-to-close returns, which miss massive intraday swings and gap risk.

---

#### 6. Contract Capital Efficiency Map (`chartMarketEfficiency`) & Linkage Matrix (`chartMarketLinkage`)
- **Ranking**: **Tier 2 (High Potential / Needs Upgrade)**
- **What They Display on Screen**:
  - `chartMarketEfficiency`: Scatter plot of Contract Price ($X$-axis) vs Rupee Margin Required per Lot ($Y$-axis), colored by a calculated liquidity score (0 to 100).
  - `chartMarketLinkage`: Matrix cross-tabulating margin changes across Price-Volume-OI regimes.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: High visual clutter with relatively low actionable utility for daily trade decisions. Needs simplification and clearer focus.

---

#### 7. Front-Month Price & Returns (Static Chart.js) (`chartMarketPrice`)
- **Ranking**: **Tier 3 (Redundant / Candidate for Removal)**
- **What It Displays on Screen**:
  - Static Chart.js line chart of daily close prices with a lower bar chart of daily percentage returns.
- **Why It Qualifies for Improvement**:
  - *Critique*: **Completely obsolete.** It sits directly adjacent to the interactive TradingView Deep Chart, which provides far superior zooming, multi-timeframe candles, and volume profiles. Maintaining this static chart slows page rendering and adds visual noise.

---

### TAB 2: ANALYTICS & MODELS (`tab-analytics`)

The Analytics tab provides quantitative model auditing, statistical distributions, and econometric validation of clearinghouse behavior.

#### Candidate Rankings in Analytics Tab:
1. **Rank 1 (Tier 1)**: `Lag Cross-Correlation Engine` (`chartLagCorr`)
2. **Rank 2 (Tier 1)**: `Model Health — Prediction Backtest Scorecard` (`modelHealthTable`)
3. **Rank 3 (Tier 1)**: `Margin Prediction Model — Full Forward Curve` (`chartPanicFull`)
4. **Rank 4 (Tier 2)**: `DTE vs Margin Decay Curve` (`chartDTE`)
5. **Rank 5 (Tier 2)**: `Margin Change Distribution (Gaussian vs Empirical)` (`chartDeltaDist`)
6. **Rank 6 (Tier 2)**: `Historical Percentile Rank Over Time` (`chartPercentile`)
7. **Rank 7 (Tier 3)**: `5-Day Rolling Average vs Spot Margin` (`chartMomentum`)

---

#### 1. Lag Cross-Correlation Engine (`chartLagCorr`)
- **Ranking**: **Tier 1 (Flagship Econometric Tool)**
- **What It Displays on Screen**:
  - Bar/line chart plotting cross-correlation $\rho(\tau)$ across lags from $-10$ days to $+10$ days between Daily Volatility and Initial Margin %.
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderLagCorrChart`), `scripts/export_json.py`, `docs/data/history_ng.json`.
- **Mathematical & Quant Formulation**:
  $$\rho(\tau) = \frac{\sum_{t} (M_t - \bar{M})(\sigma_{t+\tau} - \bar{\sigma})}{\sqrt{\sum_{t} (M_t - \bar{M})^2 \sum_{t} (\sigma_{t+\tau} - \bar{\sigma})^2}}$$
- **What We Are Trying to Do**:
  - Provide empirical mathematical proof of clearinghouse reaction latency. Peak correlation ($\rho \approx 0.74$) occurs at **Lag $+1$ to $+2$ days**. This proves that market price volatility leads clearinghouse margin hikes by 24 to 48 hours, validating that margin hikes are mathematically forecastable before exchange circulars appear.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Calculated as a static 15-year aggregate. It does not track whether modern clearinghouse automated intraday margin files have shortened this reaction lag in recent years.

---

#### 2. Model Health Scorecard (`modelHealthTable`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - Quantitative audit scorecard table evaluating prediction accuracy over 30-day, 90-day, and 365-day rolling evaluation windows.
  - Reports:
    - **Mean Absolute Error (MAE)**: 0.792 pp (30d), 0.494 pp (90d), 0.731 pp (365d).
    - **Directional Accuracy**: 70.0% (30d), 61.1% (90d), 66.0% (365d).
    - **$1\sigma$ Coverage Rate**: 80.0% (30d), 81.1% (90d).
    - **$2\sigma$ Coverage Rate**: 90.0% (30d), 93.3% (90d).
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderModelHealthTable`), `docs/data/model_health.json`.
- **What We Are Trying to Do**:
  - Provide empirical transparency and backtested accountability for the platform's risk forecasting models.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Static table showing current numbers. It lacks a rolling time-series graph of prediction error over time to verify error stability across different volatility spikes.

---

#### 3. Margin Prediction Model — Full Forward Curve (`chartPanicFull`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - Slices all active forward contract expiries simultaneously.
  - Plots actual current margin (solid line) vs predicted margin tomorrow (dashed line), bounded by shaded $\pm 1\sigma$ and $\pm 2\sigma$ error cones.
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderPanicFull`), `docs/data/panic_spread.json`.
- **What We Are Trying to Do**:
  - Validate model behavior across the entire term structure simultaneously.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Graphically redundant with the Forward Margin Cone on the Term Structure tab.

---

#### 4. DTE vs Margin Decay Curve (`chartDTE`) & Margin Change Distribution (`chartDeltaDist`)
- **Ranking**: **Tier 2 (High Potential / Needs Upgrade)**
- **What They Display on Screen**:
  - `chartDTE`: Scatter/line curve of margin % as a function of Days to Expiration ($DTE$).
  - `chartDeltaDist`: Histogram of daily margin changes ($\Delta M$) overlaid with a fitted Gaussian normal distribution.
- **Why It Qualifies for Improvement**:
  - `chartDTE` lacks interquartile dispersion bands.
  - `chartDeltaDist` overlays a Gaussian bell curve on data that is inherently non-Gaussian (margin changes exhibit massive positive excess kurtosis / fat jumps); it needs an extreme value or fat-tail distribution model.

---

#### 5. 5-Day Rolling Average vs Spot Margin (`chartMomentum`)
- **Ranking**: **Tier 3 (Underperforming / Candidate for Removal)**
- **What It Displays on Screen**:
  - Spot margin overlaid with its 5-day simple moving average.
- **Why It Qualifies for Improvement**:
  - *Critique*: **Low theoretical value.** Margin is an administrative step-variable governed by exchange circulars and volatility thresholds, not a continuous trending asset price. Moving averages lag sudden $+5\%$ tender steps or $+3.25\%$ volatility spikes, providing no predictive edge.

---

### TAB 3: SEASONALITY (`tab-seasonality`)

The Seasonality tab analyzes cyclical calendar patterns across months, years, and contract lifecycles.

#### Candidate Rankings in Seasonality Tab:
1. **Rank 1 (Tier 1)**: `Monthly Margin Heatmap (Year × Month Grid)`
2. **Rank 2 (Tier 2)**: `Contract Lifecycle Margin Heatmap (Year × Expiry Month)`
3. **Rank 3 (Tier 2)**: `Average Margin by Month` (`chartSeasonMonth`)
4. **Rank 4 (Tier 3)**: `Average Margin by Year` (`chartSeasonYear`)

---

#### 1. Monthly Margin Heatmap (Year × Month Grid)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - 15-year historical matrix. Rows: Years (2010 to 2026). Columns: Calendar Months (Jan through Dec).
  - Each cell is color-shaded based on average margin percentage (green $\le 15\%$, amber $15\%–25\%$, red $> 25\%$).
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderSeasonalityHeatmap`), `docs/data/history_ng.json`.
- **What We Are Trying to Do**:
  - Expose macro seasonal cycles. Clearly shows that December, January, and February consistently produce high-margin stress regimes due to winter weather drawdowns.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Cells show color only. Hovering or clicking does not show underlying price returns or volatility context for that month.

---

#### 2. Average Margin by Month (`chartSeasonMonth`) & Lifecycle Heatmap
- **Ranking**: **Tier 2 (High Potential / Needs Upgrade)**
- **What They Display on Screen**:
  - `chartSeasonMonth`: Bar chart showing the 15-year average margin percentage for each month.
  - Lifecycle Heatmap: Evaluates average margin by specific contract delivery month.
- **Why It Qualifies for Improvement**:
  - `chartSeasonMonth` displays only the mean value without error bars or standard deviation, hiding the variance between mild and severe winters.

---

#### 3. Average Margin by Year (`chartSeasonYear`)
- **Ranking**: **Tier 3 (Underperforming / Candidate for Removal)**
- **What It Displays on Screen**:
  - Bar chart of average margin percentage per calendar year (2010–2026).
- **Why It Qualifies for Improvement**:
  - *Critique*: **Zero actionable edge.** Aggregating 250 trading days into an annual average erases all seasonality, contract roll dynamics, and volatility spikes. A trader cannot make hedging or capital sizing decisions based on annual averages.

---

### TAB 4: HISTORY & REGIME (`tab-history`)

The History tab provides long-term macro analysis, regime classification, and portfolio capital stress testing.

#### Candidate Rankings in History Tab:
1. **Rank 1 (Tier 1)**: `Trade Intelligence & Capital Calculator` (`chartCalcEquity`)
2. **Rank 2 (Tier 1)**: `15-Year Multi-Regime Macro Simulator` (`chartMacroSimulation`)
3. **Rank 3 (Tier 1)**: `Margin vs Volatility Scatter Frontier` (`chartScatter`)
4. **Rank 4 (Tier 1)**: `Margin Decomposition: Structural vs Policy Buffer` (`chartDecomp`)
5. **Rank 5 (Tier 1)**: `Initial Margin % Over Time` (`chartHistMargin`)
6. **Rank 6 (Tier 2)**: `Contract Lifecycle Explorer` (`chartLifecycle`)
7. **Rank 7 (Tier 2)**: `MCX Market Flow: Volume & Open Interest` (`chartHistMarketFlow`)
8. **Rank 8 (Tier 2)**: `Daily Volatility Over Time` (`chartHistVol`)

---

#### 1. Trade Intelligence & Capital Calculator (`chartCalcEquity`)
- **Ranking**: **Tier 1 (Flagship Portfolio Engine)**
- **What It Displays on Screen**:
  - Interactive portfolio sizing tool.
  - User Inputs: Account Equity (₹), Trade Direction (Long/Short), Leverage Ceiling (VaMB $\le 2.5\times$).
  - Outputs: Max safe lots, cash buffer required, margin call trigger price, liquidation price, and projected equity degradation under historical $1\sigma, 2\sigma, 3\sigma$ price shocks combined with margin expansion.
- **Data & Script Engine**:
  - Script: `docs/index.html` (`updateCalculator`), `scripts/export_json.py`.
- **Mathematical & Quant Formulation**:
  - Enforces the VaMB leverage ceiling constraint:
    $$\text{Max Lots} = \min\left(\left\lfloor\frac{\text{Capital}}{P \times 1250 \times (M / 100)}\right\rfloor, \left\lfloor\frac{\text{Capital} \times 2.5}{P \times 1250}\right\rfloor\right)$$
- **What We Are Trying to Do**:
  - Directly answer the primary capital allocation question: *"How many lots can I hold without getting wiped out by an overnight gap and margin hike?"*
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Models single-contract outright positions only. It does not account for calendar spread margin concessions (where holding Long M1 vs Short M2 receives up to 75% margin discount).

---

#### 2. 15-Year Multi-Regime Macro Simulator (`chartMacroSimulation`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What It Displays on Screen**:
  - Stress testing engine replaying account survival across the 4 most severe historical Natural Gas crises:
    1. 2018 Polar Vortex Freeze
    2. 2020 Negative Oil/Gas Capitulation
    3. 2022 Ukraine Invasion Global Energy Spike
    4. 2023–2024 SEBI Additional Margin Surcharge Regime
- **What We Are Trying to Do**:
  - Test portfolio resilience against out-of-sample historical black-swan events.
- **Why It Qualifies for Improvement**:
  - Assumes fixed position sizing without dynamic stop-out or deleveraging rules.

---

#### 3. Margin vs Volatility Scatter Frontier (`chartScatter`) & Decomposition (`chartDecomp`)
- **Ranking**: **Tier 1 (Institutional Core)**
- **What They Display on Screen**:
  - `chartScatter`: Scatter plot ($X = \sigma_{\text{daily}}$, $Y = M_{\text{initial}}$) providing visual proof of the non-linear hurdle gate: flat at $13.00\%$ floor until $\sigma > 2.35\%$, then linear expansion.
  - `chartDecomp`: Stacked area chart decomposing gross margin into SPAN VaR, ELM (1.25%), Tender Ramp, and Policy Surcharges (+7% / +10%).
- **Why It Qualifies for Improvement**:
  - Both charts are mathematically sound and institutional. `chartScatter` could benefit from coloring points by regulatory era (FMC pre-2018 vs SEBI post-2018).

---

#### 4. Contract Lifecycle Explorer (`chartLifecycle`)
- **Ranking**: **Tier 2 (High Potential / Needs Upgrade)**
- **What It Displays on Screen**:
  - Line plot tracing the margin percentage of any selected historical contract as it matured from 180 DTE down to 0 DTE.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Displays only one contract at a time. It lacks an aggregate median curve with interquartile range bands across all 240+ contracts.

---

### TAB 5: TERM STRUCTURE (`tab-termstructure`)

The Term Structure tab visualizes margin curves, volatility curves, and contract spreads across forward expiries.

#### Candidate Rankings in Term Structure Tab:
1. **Rank 1 (Tier 1)**: `Forward Margin Curve & Historical Cone` (`chartFwdFull`)
2. **Rank 2 (Tier 2)**: `Volatility Term Structure` (`chartVolCurve`)
3. **Rank 3 (Tier 3)**: `Margin Spread: Big vs Mini` (`chartSpread`)

---

#### 1. Forward Margin Curve & Historical Cone (`chartFwdFull`)
- **Ranking**: **Tier 1 (Flagship Cone Visual)**
- **What It Displays on Screen**:
  - Line chart of Total Margin % across active forward contract expiries (M1 through M6).
  - Enveloped by historical percentile cones: $P_{10}$ (lower dashed), $P_{50}$ (median dashed), $P_{90}$ (upper dashed).
  - Toggles for All-Time vs Trailing 5-Year cones, MCX Close Price overlay, and Liquidity score markers.
- **Data & Script Engine**:
  - Script: `docs/index.html` (`renderFwdCone`), `docs/data/term_cone.json`.
- **What We Are Trying to Do**:
  - Inform portfolio managers whether back-month contracts are historically cheap or expensive in margin space.
- **Why It Qualifies for Improvement**:
  - *Current Limitation*: Cones aggregate all historical months together, masking winter vs summer structural term structure differences.

---

#### 2. Margin Spread: Big vs Mini (`chartSpread`)
- **Ranking**: **Tier 3 (Underperforming / Candidate for Overhaul or Removal)**
- **What It Displays on Screen**:
  - Percentage margin differential between standard Natural Gas (1,250 MMBtu) and Mini (250 MMBtu) contracts.
- **Why It Qualifies for Improvement**:
  - *Critique*: **Zero informational value today.** Following SEBI risk harmonization guidelines, MCX maintains identical margin percentages for Big and Mini contracts ($\Delta M \equiv 0.00\%$). The chart renders a flat line at zero across all expiries.
  - *Recommendation*: Candidate to be replaced with a **Calendar Roll Spread Chart** ($M1 - M2$ price spread and contango/backwardation roll yield in ₹/lot).

---

### TAB 6: DATA EXPLORER (`tab-explorer`)

- **Candidate**: `Historical Data Explorer Table & CSV Export` (`explorerTable`) &mdash; **Tier 1**
- **What It Displays on Screen**: Filterable raw data table with date pickers, contract filters, column sorting, and one-click institutional CSV download.
- **Objective**: Full compliance auditability and reproducible research.

---

### TAB 7: OVERVIEW AUXILIARY CHARTS (	ab-overview)

The Overview tab contains three auxiliary visualization candidates alongside core snapshot tables:
1. **Intraday Panic Trigger Bands (`chartPanicTriggers`)** &mdash; **Tier 1**: Settle prices flanked by upper and lower hike trigger price bands ($P_{\text{up}}^*, P_{\text{dn}}^*$). Strong concept; could be integrated with live candlestick charts.
2. **Price & Margin Confluence Chart (`chartPriceMarginConfluence`)** &mdash; **Tier 2**: Dual-axis line chart overlaying price against gross margin %. Could add rolling correlation and elasticity subplots.
3. **Mini Forward Curve (`miniForwardCurve`)** &mdash; **Tier 3**: Small line chart duplicating `chartFwdFull` on Tab 5. Prime candidate for removal or replacement with an intraday shock meter.

---

## 3. Master Classification Matrix Across All 31 Candidates

| Rank | Candidate / Module | Tab Location | Tier | Status & Qualification |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **TradingView Lightweight Deep Chart** | Market | **Tier 1** | Preserve & Improve: Bridge with intraday trigger thresholds. |
| **2** | **Time-of-Day (TOD) Seasonality Profile** | Market | **Tier 1** | Preserve & Improve: Add live session path against historical curve. |
| **3** | **Trade Intelligence & Capital Calculator** | History | **Tier 1** | Preserve & Improve: Add calendar spread margin relief offsets. |
| **4** | **Forward Margin Curve & Historical Cone** | Term Structure | **Tier 1** | Preserve & Improve: Seasonally condition cones by calendar month. |
| **5** | **Lag Cross-Correlation Engine** | Analytics | **Tier 1** | Preserve & Improve: Add rolling 90-day lag shift tracking. |
| **6** | **Price/OI 4-Quadrant Phase Map** | Market | **Tier 1** | Preserve & Improve: Scale markers by trade volume. |
| **7** | **15-Year Multi-Regime Macro Simulator** | History | **Tier 1** | Preserve & Improve: Add dynamic stop-out / deleveraging rules. |
| **8** | **Intraday Panic Trigger Bands** | Overview | **Tier 1** | Preserve & Improve: Overlay live prices and historical breach markers. |
| **9** | **Margin vs Volatility Scatter Frontier** | History | **Tier 1** | Preserve: Clear visual proof of hurdle-gated non-linearity. |
| **10** | **Margin Decomposition (Structural vs Buffer)** | History | **Tier 1** | Preserve: Flawless regulatory policy transparency. |
| **11** | **Active Futures Curve & Contango Structure** | Market | **Tier 1** | Preserve: Clear term structure shape. |
| **12** | **Futures Curve Evolution Overlay** | Market | **Tier 1** | Preserve: Tracks weekly and monthly curve shifts. |
| **13** | **Realized Volatility & Regime Classification** | Market | **Tier 1** | Preserve: Clear 3-regime volatility tracking. |
| **14** | **Monthly Margin Heatmap (Year × Month)** | Seasonality | **Tier 1** | Preserve: Clean seasonal grid. |
| **15** | **Model Health Prediction Scorecard** | Analytics | **Tier 1** | Preserve: Objective empirical accountability. |
| **16** | **Data Explorer Table & CSV Export** | Explorer | **Tier 1** | Preserve: Raw data auditability and compliance export. |
| **17** | **Price & Margin Confluence Chart** | Overview | **Tier 2** | Upgrade: Add rolling correlation and margin elasticity subplots. |
| **18** | **Contract Lifecycle Explorer** | History | **Tier 2** | Upgrade: Overlay aggregate median lifecycle curve with IQR bands. |
| **19** | **Volatility Term Structure** | Term Structure | **Tier 2** | Upgrade: Compare exchange EWMA vol against Parkinson realized vol. |
| **20** | **Contract Capital Efficiency Map** | Market | **Tier 2** | Upgrade: Simplify visual density and add spread costs. |
| **21** | **Margin vs PVOI Linkage Matrix** | Market | **Tier 2** | Upgrade: Filter by contract maturity ($DTE$). |
| **22** | **Margin Change Distribution** | Analytics | **Tier 2** | Upgrade: Add student's $t$ fat-tail fit overlay. |
| **23** | **Historical Percentile Rank Over Time** | Analytics | **Tier 2** | Upgrade: Better integration with current margin level. |
| **24** | **Contract Lifecycle Margin Heatmap** | Seasonality | **Tier 2** | Upgrade: Add rollover volume weighting. |
| **25** | **Average Margin by Month** | Seasonality | **Tier 2** | Upgrade: Add dispersion / error bars. |
| **26** | **Volume & Open Interest Flow** | Market | **Tier 2** | Upgrade: Consolidate with Deep Chart volume. |
| **27** | **Mini Forward Curve (Overview)** | Overview | **Tier 3** | **Candidate for Removal / Replacement**: Duplicates Tab 5. |
| **28** | **Margin Spread: Big vs Mini** | Term Structure | **Tier 3** | **Candidate for Removal / Replacement**: Spread is 0.00% today. |
| **29** | **Front-Month Price & Returns (Static)** | Market | **Tier 3** | **Candidate for Removal**: Obsolete next to TradingView Deep Chart. |
| **30** | **Average Margin by Year** | Seasonality | **Tier 3** | **Candidate for Removal**: Annual averaging hides all volatility. |
| **31** | **5-Day Rolling Margin Momentum** | Analytics | **Tier 3** | **Candidate for Removal**: Moving average lags jump-process steps. |
