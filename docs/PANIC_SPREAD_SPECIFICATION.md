# Panic Spread Signals: Complete System Architecture, Econometric Logic & AI Consultation Blueprint

**Document Version:** 2.0 (Post-Audit Production Release)  
**System:** MCX Natural Gas Margin Prediction Engine & Panic Spread Surveillance  
**Scope:** Architecture · Econometrics · Data Pipelines · Frontend Visuals · Multi-Agent Review Prompt  

---

## Part 1: Philosophy & Institutional Background

### 1. The Core Problem
In exchange-traded commodity futures (specifically **MCX Natural Gas**), margin requirements are not fixed. The clearing corporation (**MCXCCL**, regulated by **SEBI**) dynamically hikes or cuts margins based on SPAN (Standard Portfolio Analysis of Risk), extreme volatility, price limit circuits, and physical tender period entry.

For an energy trader or commodity desk:
* A surprise margin hike from **$15\% \rightarrow 30\%$** immediately doubles capital requirements per lot.
* If an account does not hold sufficient buffer capital, it suffers an **RMS forced liquidation / margin stopout**, often right at the peak of a volatility spike.
* Conversely, when margins are sitting at their historical minimum floor (**13.00%**), they cannot drop further, creating an asymmetric upside risk of future hikes.

### 2. The Purpose of Panic Spread Signals
The **Panic Spread Signals** engine is designed to provide traders with real-time, contract-by-contract forward surveillance:
1. **Level Forecast:** What is the predicted total margin requirement tomorrow for each contract?
2. **Directional Probability:** What is the mathematical probability that MCXCCL will **Hike (>+0.5%)**, keep **Flat (±0.5%)**, or **Cut (<-0.5%)** margins tomorrow?
3. **Surveillance & Early Warning:** Detect volatility clustering, tender step-ups, and model divergences before market close.

---

## Part 2: Underlying Data Architecture

The engine runs on two high-frequency, historical SQLite databases and continuous parquet vault data:

### 1. `data/margins.db` (Clearing House Historical Master)
* **Records:** Over **131,881 records** spanning **2010 to 2026**.
* **Table Schema (`margins`):**
  | Column | Type | Institutional Meaning |
  | :--- | :--- | :--- |
  | `date` | `TEXT` | Margin publication date (`YYYY-MM-DD`). |
  | `symbol` | `TEXT` | `NATURALGAS` (1,250 mmBtu) or `NATGASMINI` (250 mmBtu). |
  | `expiry` | `TEXT` | Contract expiry identifier (`DDMMMYYYY`, e.g. `27OCT2026`). |
  | `initial_margin_pct` | `REAL` | SPAN-mandated base initial margin percentage. |
  | `elm_pct` | `REAL` | Extreme Loss Margin percentage (minimum 1.25%). |
  | `tender_margin_pct` | `REAL` | Statutory delivery tender margin (0% to 25%). |
  | `total_margin_pct` | `REAL` | Total effective margin required by clearing house. |
  | `additional_long_margin_pct`| `REAL` | Ad-hoc regulatory surcharge on long positions. |
  | `additional_short_margin_pct`| `REAL` | Ad-hoc regulatory surcharge on short positions. |
  | `special_long_margin_pct` | `REAL` | Emergency circuit margin on long positions. |
  | `special_short_margin_pct` | `REAL` | Emergency circuit margin on short positions. |
  | `daily_volatility` | `REAL` | MCXCCL EWMA daily volatility parameter ($\sigma_{\text{daily}}$). |
  | `annualized_volatility` | `REAL` | Annualized volatility ($\sigma_{\text{daily}} \times \sqrt{250}$). |
  | `file_id` | `INTEGER` | Circular sequence ID (higher = later intraday revision). |
  | `created_at` | `TEXT` | Ingestion timestamp. |

### 2. `data/prices.db` (Bhavcopy Market Master)
* **Records:** Over **243 contracts** spanning **2007 to 2026**.
* **Table Schema (`prices`):**
  * `date`, `symbol`, `expiry`, `instrument` (`FUTCOM`, `OPTFUT`).
  * `open`, `high`, `low`, `close`, `prev_close`, `volume_lots`, `open_interest`, `value_lacs`.

### 3. Continuous Microstructure Vault
* `NATURALGAS_5m_continuous_2019_2026.parquet`: 1.65 million 5-minute OHLCV continuous bars with tick volume.
* `NATURALGAS_1m_continuous_2019_2026.parquet`: 1-minute continuous execution data.

---

## Part 3: Econometric Engine & Mathematical Logic

The engine does not rely on a single black box. It fuses **three complementary mathematical layers**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PANIC SPREAD ENGINE                             │
├──────────────────────────┬─────────────────────────────────────────────┤
│ 1. Point Forecast        │ Level point estimate tomorrow (% per lot)   │
│ 2. Logistic Classifier   │ Directional probability: Cut vs Flat vs Hike│
│ 3. Regime Detection      │ SPAN VaR behavior across Calm vs Crisis     │
└──────────────────────────┴─────────────────────────────────────────────┘
```

### Layer 1: The Point Forecast Engine (`Pred. Total %`)

The predicted total margin for contract $c$ is computed via:

$$\text{Pred Initial}_c = \max\left(13.00\%,\; 0.886 \cdot M_{t,c} + 43.0 \cdot \sigma_{\text{daily},c}\right)$$

$$\text{Tender Margin}_c = \begin{cases} 
\text{tender\_margin\_pct}_c & \text{if present} \\
\max\left(0,\; \text{total\_margin\_pct}_c - M_{t,c}\right) & \text{otherwise}
\end{cases}$$

$$\mathbf{\text{Pred. Total \%}}_c = \text{Pred Initial}_c + \text{Tender Margin}_c$$

#### Institutional Rules Enforced:
1. **The 13.00% Statutory Floor:** MCXCCL and SEBI mandate that Natural Gas margins cannot fall below 13.00%. Across all 78,108 margin records since August 7, 2023, margins have never dipped below 13.00%. Clamping with $\max(13.0, \dots)$ eliminates physically impossible decay (e.g. `12.33%`).
2. **Tender Margin Additivity:** During the final 5 trading days prior to expiry, mandatory physical tender margins step in at +5% per day (10%, 15%, 20%, 25%). Both Current and Predicted margins are displayed on a **Total vs. Total** basis.
3. **Volatility Multiplier:** $43.0 \cdot \sigma_{\text{daily}}$ acts as an asymmetric shock detector. When daily vol exceeds 2.7%, this term overpowers the $0.886$ discount and drives predicted margin upwards.

---

## Layer 2: The Multi-Class Event Probability Classifier

A multi-feature logistic classifier models the probability distribution of tomorrow's margin change:
$$\Delta M_{t+1} = M_{t+1} - M_t$$

Three mutual outcomes are predicted:
* **Hike:** $\Delta M_{t+1} > +0.5\%$
* **Flat:** $-0.5\% \le \Delta M_{t+1} \le +0.5\%$
* **Cut:** $\Delta M_{t+1} < -0.5\%$

#### Feature Vector for Contract $c$:
$$\mathbf{x}_c = \begin{bmatrix}
M_{t,c} & \text{Current Initial Margin \%} \\
\sigma_{\text{daily},c} \times 100 & \text{Exchange Daily Volatility \%} \\
\min(\text{DTE}_c, 300) & \text{Days to Expiry (capped at 300)} \\
\text{Percentile}(M_{t,c}) & \text{Empirical rank across 2010–2026 distribution (0–100)} \\
\min(\text{LCD}_c, 60) & \textbf{Calendar days since contract margin last changed in DB} \\
M_{t,c} - \text{Fair}_c & \text{Policy buffer deviation against Regime B baseline}
\end{bmatrix}$$

#### Model Calibration & Feature Odds Ratios:
* `days_since_last_change` ($\text{LCD}$): $\beta = -3.3991$ (Odds Ratio = **`0.033`**).
  * *Meaning:* When a contract has been dormant for 20–40 days, the probability of an immediate hike tomorrow drops by **97%**.
  * *Crucial Fix:* The pipeline dynamically queries `data/margins.db` for the exact date each contract last changed. Dormant contracts (e.g. Jan 2027 flat for 37 days) evaluate to $P(\text{Flat}) = 100.0\%$, eliminating false hike alarms.
* `vol_pct`: $\beta = +0.1676$ (Odds Ratio = **`1.182`**).
  * *Meaning:* Every 1% increase in daily volatility increases hike odds by 18.2%.

---

## Layer 3: Signal Badge & Conflict Surveillance

In the UI ([`docs/index.html`](file:///c:/Users/Dell/Github/mcx-margins/docs/index.html)):

```javascript
// Dominant class drives badge
const dominant = Math.max(ep.p_hike, ep.p_cut, ep.p_flat);
if (dominant === ep.p_hike)      signalLabel = `<span class="badge-hike">&#9650; HIKE ${pH}%</span>`;
else if (dominant === ep.p_cut)  signalLabel = `<span class="badge-cut">&#9660; CUT ${pC}%</span>`;
else                             signalLabel = `<span class="badge-flat">&#8594; FLAT ${pF}%</span>`;
```

#### Alert Severity & Visual Hierarchy:
* **Normal / Flat:** Subtle grey border, neutral tag (`→ FLAT 100%`).
* **Elevated Risk:** Amber border glow (`border-left: 3px solid #f59e0b`) when $P(\text{Hike}) > 65\%$.
* **High Panic Alert:** Red border glow (`border-left: 3px solid #ef4444`) when $P(\text{Hike}) > 80\%$.
* **Conflict Warning:** If the linear model predicts a cut while the logistic model assigns $P(\text{Hike}) > 50\%$ (or vice versa), the text turns yellow (`#d29922`) with an explanatory conflict tooltip.

---

## Part 4: The Frontend Presentation Surface

The UI renders the **Panic Spread Signals** table directly on the primary Overview tab:

| Column | Header | Meaning to Trader | Example Row (Nov 2026) | Example Row (Jan 2027) |
| :---: | :--- | :--- | :---: | :---: |
| 1 | **Expiry** | Delivery month + short expiry date | `Nov 2026` *(27 Oct '26)* | `Jan 2027` *(28 Dec '26)* |
| 2 | **Total %** | Today's total margin (Initial + ELM + Tender) | `29.02%` | `13.00%` |
| 3 | **Pred. Total %** | Model's tomorrow total margin point forecast | `28.13%` | `13.00%` |
| 4 | **Probability** | Visual 3-part bar: Cut (Green) \| Flat (Grey) \| Hike (Red) | `[Green 37% \| Grey 44% \| Red 19%]` | `[Grey 100%]` |
| 5 | **Signal** | Dominant outcome badge with confidence | `→ FLAT 44%` | `→ FLAT 100%` |

---

## Part 5: The Independent AI Review Prompt

Below is the copy-pasteable prompt designed for consultation with other frontier AI models (Claude 3.5 Sonnet, GPT-4o, o1, etc.). It describes the entire system objectively without imposing biased conclusions:

```markdown
### SYSTEM ROLE
You are an elite quantitative derivatives architect and chief risk officer specializing in commodity clearing houses, SPAN margin methodologies, and exchange surveillance.

### CONTEXT
We have developed an institutional surveillance engine for MCX Natural Gas futures called "Panic Spread Signals". Its purpose is to forecast tomorrow's margin requirements and detect impending margin hikes/cuts across the forward curve.

We want an unconstrained, deeply rigorous peer review. Do not sugarcoat your feedback. Do not hold back. If something in our mathematical or institutional reasoning is flawed, point it out with empirical justification. If something is optimal, state why. If there are high-value improvements we have missed, lay them out clearly.

---

### OUR CURRENT ARCHITECTURE & DATASETS

1. DATASETS AVAILABLE:
- 131,881 clearing margin records (2010–2026) in SQLite (`date, symbol, expiry, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct, additional_margins, daily_volatility, annualized_volatility, file_id`).
- 243 contracts (2007–2026) in SQLite (`date, symbol, expiry, open, high, low, close, volume_lots, open_interest`).
- 1.65 million 5-minute continuous bars (2019–2026) in Parquet.

2. THE TWO-ENGINE SETUP:

Engine A: Continuous Linear Point Forecaster
Formula:
  Raw Initial = 0.886 * M_t + 43.0 * sigma_daily
  Pred Initial = max(13.00%, Raw Initial)
  Tender Surcharge = tender_margin_pct (or total_margin - initial_margin)
  Pred. Total % = Pred Initial + Tender Surcharge

Rules:
- Clamped at 13.00% statutory floor (MCXCCL/SEBI regulatory floor for Natural Gas since August 2023).
- Tender margins (+5%/day up to 25%) are added so both Current and Predicted display Total vs Total.

Engine B: Discrete 3-Class Logistic Event Probability Model
Trained via walk-forward L-BFGS to predict tomorrow's margin change (Hike >+0.5%, Flat ±0.5%, Cut <-0.5%).
Features:
- Current initial margin level
- Daily volatility % (sigma * 100)
- min(DTE, 300)
- Empirical margin percentile rank (0–100)
- min(days_since_last_change, 60) (dynamically queried from DB per contract)
- Policy buffer (deviation from Regime B regression line)
Outputs:
- Normalized probabilities: P(Cut), P(Flat), P(Hike)
- Dominant class drives UI badge: [▲ HIKE pH%], [→ FLAT pF%], [▼ CUT pC%]
- Border glow: Amber if P(Hike) > 65%, Red if P(Hike) > 80%.

3. EMPIRICAL OBSERVATIONS FROM OUR BACKTEST:
- Margin is a step function: 52%–70% of days have delta = 0.00%.
- Random walk (tomorrow = today) has MAE = 1.01% on modern data. The linear model (0.886*M + 43*sigma) has MAE = 1.30% because it forces continuous daily decay on calm days.
- In Regime B (daily vol >= 4.5%), the relationship between vol and margin is near-deterministic (R^2 = 0.9992, Margin = 7.589 * vol% - 4.845).
- Adding raw price returns (1d, 3d) to the logistic model slightly degraded out-of-sample AUC-ROC (0.618 -> 0.605) due to collinearity with exchange EWMA daily volatility.

---

### QUESTIONS FOR YOUR AUDIT

1. MATHEMATICAL & ECONOMETRIC SOUNDNESS:
- Is combining a continuous linear point forecaster with a discrete logistic classifier the optimal architecture for regulatory step functions?
- What are the mathematical weaknesses or edge cases of the current linear formula (0.886*M + 43*sigma)?

2. CLASSIFIER & FEATURE ENGINEERING:
- What features, if any, could meaningfully improve the logistic model's hike prediction skill without causing collinearity or overfitting?
- Would a 2-stage Hurdle Model (classify Flat vs Action first, then forecast magnitude only if Action occurs) strictly outperform the current dual-track setup?

3. INSTITUTIONAL & CLEARING HOUSE REALITIES:
- Are there specific SEBI/MCX margin mechanics (e.g. circuit filter revisions, margin periods, intraday peak margin snapshots, spread margin benefits) that our current model overlooks?

4. USER EXPERIENCE & DECISION INTELLIGENCE:
- In the table display (Expiry, Total %, Pred. Total %, Probability, Signal), what information would institutional commodity traders consider missing or redundant?
- How should model conflicts (e.g. linear model pointing slightly down while logistic assigns 55% hike) be best communicated without causing cognitive dissonance?

5. RADICAL IMPROVEMENTS vs. "LEAVE IT ALONE":
- If our system is already institutional-grade and additional complexity would only invite regressions, please state so honestly.
- If there are 1 to 2 high-leverage improvements worth testing, specify exact mathematical formulas and implementation steps.
```
