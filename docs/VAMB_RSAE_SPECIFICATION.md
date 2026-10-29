# Volatility-Adjusted Margin Buffer (VAMB / RSAE v2.0) System & Data Specification

---

## 1. System Architecture & Objective

### 1.1 The Quantitative Problem
Trading commodity futures—specifically energy contracts such as **MCX Natural Gas** (Multi Commodity Exchange of India)—presents extreme non-linear risk factors that cause standard fixed-fraction or static leverage models to fail:
1. **Exchange Dynamic Margin Expansion:** Clearinghouses (MCXCCL) dynamically adjust SPAN and Extreme Loss Margins (ELM). During extreme volatility expansions, margins frequently double or quadruple overnight (e.g. from 14.5% to 66.05%), instantly causing forced liquidation for traders utilizing typical 3x to 5x leverage.
2. **Asymmetric Tail Risk (Short Squeeze Convexity):** Long commodity positions are bounded at zero price, whereas short positions face mathematically unbounded upside risk with severe positive skewness during supply shocks or pipeline freezes.
3. **Mandatory Tender Period Surcharges:** During the final 5 to 7 days to expiry (DTE), MCX imposes escalating delivery tender margins (typically increasing in 5% daily tranches up to 25%+), while contract liquidity evaporates as volume rolls forward.
4. **Portfolio Path-Dependency (Risk of Ruin):** Static position sizing during an ongoing portfolio drawdown accelerates capital destruction. An institutional sizing model must de-risk exposure as cumulative paper losses deepen.

### 1.2 Core Mandate & The Principle of Asymmetric Aggression
The **Volatility-Adjusted Margin Buffer (VAMB / RSAE v2.0)** sizing engine solves a dual-objective constrained optimization problem governed by the **Principle of Asymmetric Aggression**:

1. **Aggressive Profit Harvesting in Favorable Regimes (Do Not Leave Money on the Table):**
   - When volatility is compressed, clearinghouse margin requirements are stable, institutional open interest confirms trend accumulation, and account equity is healthy, the system must **maximize profit extraction**.
   - It should not be unnecessarily timid or under-leveraged when market fragility is low. The engine is expected to deploy the maximum mathematically safe leverage to extract compounding returns.

2. **Ruthless Capital Preservation in High-Fragility Regimes (Zero-Compromise Defense):**
   - When volatility expands rapidly, exchange margin gaps widen, delivery tender periods approach, or portfolio drawdowns occur, the system must instantly pivot into **hyper-defensive preservation**.
   - Notional exposure must be drastically curtailed to guarantee survival through multi-sigma price shocks, short squeezes, and overnight margin quadruplings without forced liquidation.

---

## 2. Market Contract Specifications

The engine sizes positions across two contract types on MCX:

| Specification | Natural Gas (Standard / Big) | Natural Gas Mini (NGM) |
| :--- | :--- | :--- |
| **Exchange Symbol** | `NATURALGAS` | `NATGASMINI` |
| **Trading Multiplier** | **1,250 MMBtu** per lot | **250 MMBtu** per lot |
| **Quotation Basis** | ₹ per 1 MMBtu | ₹ per 1 MMBtu |
| **Tick Size** | ₹ 0.10 (= ₹125 / lot P&L per tick) | ₹ 0.10 (= ₹25 / lot P&L per tick) |
| **Settlement Type** | Both Physical Delivery & Compulsory Cash | Physical Delivery Tender Mechanism |
| **Standard Tenor** | Monthly expiration (~23rd to 26th of month) | Monthly expiration (~23rd to 26th of month) |
| **Trading Hours** | 09:00 to 23:30 / 23:55 IST | 09:00 to 23:30 / 23:55 IST |

---

## 3. Mathematical Formulation

The engine executes a **Dual-Firewall** quantitative pipeline. It calculates two independent bounds—a **Margin Coverage Firewall** and a **Leverage Ceiling Firewall**—and takes their minimum:

$$\text{VAMB Lots} = \max\left(0, \min\left(\text{Lots}_{\text{Raw}}, \text{Lots}_{\text{Ceil}}\right)\right)$$

```
                                    ┌─── Capital Available (₹)
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │                   DATA INGESTION & REGIME              │
       │  Price (P), SPAN Margin %, Realized Vol (σ), DTE,      │
       │  Direction (Long/Short), Margin Gap, Portfolio DD %    │
       └────────────────────────────┬───────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│ FIREWALL 1: MARGIN SUFFICIENCY│   │ FIREWALL 2: LEVERAGE CEILING  │
│                               │   │                               │
│ • Asymmetric Vol Shield       │   │ • Base Leverage (3.25L / 1.75S│
│ • Near-Expiry Tender Surch.   │   │ • 5-day OI Trend Boost (1.20x)│
│ • Total Margin Buffer (mReq)  │   │ • Margin-Skew Haircut         │
│                               │   │ • DTE Liquidity Taper         │
│                               │   │ • Portfolio Drawdown Brake    │
│                               │   │                               │
│ Lots_Raw = Floor(Cap / Margin)│   │ Lots_Ceil = Floor(Cap*L / Not)│
└───────────────┬───────────────┘   └───────────────┬───────────────┘
                │                                   │
                └─────────────────┬─────────────────┘
                                  ▼
                ┌───────────────────────────────────┐
                │        DUAL-FIREWALL CLAMP        │
                │ VAMB Lots = min(Lots_Raw,Lots_Ceil│
                └───────────────────────────────────┘
```

---

### Step 1: Direction-Decoupled Asymmetric Safety Shield

The model computes an extra volatility cushion applied over and above the exchange initial margin:

$$\text{Shield} = \min\left(0.40, \max\left(s_{\text{Min}}, c_{\text{Co}} \times \sigma_{\text{ann}}\right)\right)$$

Where:
- $\sigma_{\text{ann}}$ is the 20-day rolling annualized realized volatility (or exchange annualized volatility if higher).
- **Asymmetry Parameters:**
  - **LONG Position:** $s_{\text{Min}} = 0.10$ (10% floor cushion), $c_{\text{Co}} = 0.25$
  - **SHORT Position:** $s_{\text{Min}} = 0.18$ (18% floor cushion), $c_{\text{Co}} = 0.40$
- **Cap:** Hard ceiling at $0.40$ (40% buffer) to prevent excessive capital starvation during extreme vol regimes.

*Rationale:*
- For Longs, $0.25 \times \sigma_{\text{ann}}$ is calibrated to withstand a $\approx 4\sigma$ single-day price shock ($0.25 \times \sqrt{252} \approx 3.97$).
- For Shorts, the higher floor ($18\%$) and multiplier ($0.40$) explicitly account for the right-tailed skewness and explosive upside velocity of commodity squeezes.

---

### Step 2: Near-Expiry Tender Surcharge & Taper

During the final 7 trading days before expiry, the engine introduces a linear tender margin surcharge $\tau$ and a leverage multiplier $\psi_{\text{DTE}}$:

$$\tau = \begin{cases} 
0.08 \times \left(\frac{8 - \max(\text{DTE}, 0)}{7}\right) & \text{if } \text{DTE} \le 7 \\
0 & \text{if } \text{DTE} > 7
\end{cases}$$

$$\psi_{\text{DTE}} = \begin{cases} 
0.50 & \text{if } \text{DTE} \le 3 \\
0.75 & \text{if } 3 < \text{DTE} \le 7 \\
1.00 & \text{if } \text{DTE} > 7
\end{cases}$$

*Rationale:*
- Mirrors MCX tender period rules where delivery margins step up by 5% daily in the final week.
- Forces automated de-leveraging as market liquidity rolls out to the next month's contract.

---

### Step 3: Corporate Portfolio Path-Dependency Drawdown Brake

To safeguard the firm's capital from compounding drawdowns, position sizing incorporates the cumulative peak-to-trough paper loss of the overall portfolio:

$$\text{portfolioBrake} = \begin{cases} 
1.00 & \text{if Drawdown } < 5.0\% \quad \text{(Normal regime: full sizing)} \\
0.65 & \text{if } 5.0\% \le \text{Drawdown} < 10.0\% \quad \text{(35\% defensive haircut)} \\
0.40 & \text{if Drawdown } \ge 10.0\% \quad \text{(60\% capital preservation clamp)}
\end{cases}$$

*Rationale:*
- Prevents revenge trading and statistical ruin by mathematically reducing notional exposure when the account equity curve is impaired.

---

### Step 4: Compound Margin Sufficiency (Firewall 1: $\text{Lots}_{\text{Raw}}$)

$$m_{\text{Req}} = \text{SPAN Margin Pct} + \text{Shield} + \tau$$

$$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{\text{Capital}}{\text{Price} \times \text{Lot Size} \times m_{\text{Req}}} \right\rfloor$$

*Rationale:*
- Ensures that even if the exchange hikes margins overnight by the full safety buffer, the account will not breach regulatory margin limits.

---

### Step 5: Asymmetric Dynamic Leverage Ceilings (Firewall 2: $\text{Lots}_{\text{Ceil}}$)

$$\mathcal{L}_{\text{eff}} = \mathcal{L}_{\text{Base}} \times \kappa_{\text{OI}} \times \phi_{\text{Skew}} \times \psi_{\text{DTE}} \times \text{portfolioBrake}$$

Where:
1. **Base Leverage ($\mathcal{L}_{\text{Base}}$):**
   - $\mathcal{L}_{\text{Base}} = 3.25\times$ for LONG
   - $\mathcal{L}_{\text{Base}} = 1.75\times$ for SHORT
2. **Open Interest Accumulation Multiplier ($\kappa_{\text{OI}}$):**
   - $\kappa_{\text{OI}} = 1.20$ if LONG and 5-day continuous aggregate open interest is positive (`oi_aggregate_build_5d === true`).
   - $\kappa_{\text{OI}} = 1.00$ otherwise.
3. **Clearinghouse Margin-Skew Contraction ($\phi_{\text{Skew}}$):**
   When the exchange initial margin substantially exceeds realized volatility, it signals clearinghouse anticipation of impending volatility spikes:
   $$\text{marginGap} = \text{Initial Margin Pct} - \text{Realized Vol Pct}$$
   $$\phi_{\text{Skew}} = \min\left(1.0, \max\left(0.40, 1 - 0.15 \times \max(0, \text{marginGap} - 2.0)\right)\right)$$

The maximum permitted lots under the leverage ceiling are:
$$\text{Lots}_{\text{Ceil}} = \left\lfloor \frac{\text{Capital} \times \mathcal{L}_{\text{eff}}}{\text{Price} \times \text{Lot Size}} \right\rfloor$$

---

### Step 6: Dual-Firewall Synthesis Clamp

$$\text{VAMB Lots} = \max\left(0, \min\left(\text{Lots}_{\text{Raw}}, \text{Lots}_{\text{Ceil}}\right)\right)$$

The dynamic capital utilization percentage is:
$$\text{VAMB \%} = \min\left(100, \max\left(1, \operatorname{round}\left(\frac{\text{VAMB Lots}}{\text{Max Possible Lots}} \times 100\right)\right)\right)$$

Where $\text{Max Possible Lots} = \left\lfloor \frac{\text{Capital}}{\text{Margin Required per Lot}} \right\rfloor$.

---

## 4. Production Code Implementation

The following JavaScript function runs in production in `docs/index.html` inside `window.updateCalc`:

```javascript
// ====== RSAE v2.0 ASYMMETRIC REGIME ENGINE (VAMB) SIZING ======
const entryMarketRow = entryLookup?.row || null;
const vPrice = Number(entryPrice) || 0;
const vSpanPct = (entryMarginRow && entryMarginRow.initial_margin_pct != null) 
  ? (entryMarginRow.initial_margin_pct / 100) 
  : (entryMarginPct / 100); 

const vSigmaAnn = (entryMarginRow && entryMarginRow.annualized_volatility != null) 
  ? (entryMarginRow.annualized_volatility > 2.0 ? entryMarginRow.annualized_volatility / 100 : entryMarginRow.annualized_volatility) 
  : ((entryMarketRow && entryMarketRow.rolling_realized_vol_20d != null) ? (entryMarketRow.rolling_realized_vol_20d / 100) : 0);

const vMarginGap = (entryMarketRow && entryMarketRow.margin_vs_realized_vol_gap != null) 
  ? entryMarketRow.margin_vs_realized_vol_gap 
  : (
    (entryMarginRow && entryMarginRow.margin_vs_realized_vol_gap != null) 
      ? entryMarginRow.margin_vs_realized_vol_gap 
      : (
        (entryMarginRow && entryMarketRow && entryMarginRow.initial_margin_pct != null && entryMarketRow.rolling_realized_vol_20d != null) 
          ? (entryMarginRow.initial_margin_pct - entryMarketRow.rolling_realized_vol_20d) 
          : 0
      )
  );

const vDte = Number.isFinite(entryMarginRow?.dte) 
  ? Number(entryMarginRow.dte) 
  : (Number.isFinite(entryMarketRow?.dte) ? Number(entryMarketRow.dte) : 999);

const vAggregateOI = (
  entryMarketRow && (entryMarketRow.oi_aggregate_build_5d === true || entryMarketRow.oi_aggregate_build_5d === 1) || 
  (entryMarginRow && (entryMarginRow.oi_aggregate_build_5d === true || entryMarginRow.oi_aggregate_build_5d === 1))
);

const vDirection = (_calcDir || 'long').toUpperCase();
const vPortfolioDD = parseFloat(document.getElementById('portfolioDrawdownInput')?.value) || 0;
const vIsLong = vDirection !== 'SHORT';

let vambLots = 0;
let rsaeCalc = null;

if (vPrice > 0 && capital > 0) {
  // 1. Direction-Decoupled Asymmetric Safety Shield
  const sMin = vIsLong ? 0.10 : 0.18;
  const cCo  = vIsLong ? 0.25 : 0.40;
  const shield = Math.min(0.40, Math.max(sMin, cCo * vSigmaAnn));

  // 2. Near-Expiry Tender Surcharge & Taper
  let tau = 0, psiDTE = 1.0;
  if (vDte <= 7) {
    tau = 0.08 * ((8 - Math.max(vDte, 0)) / 7);
    psiDTE = (vDte <= 3) ? 0.50 : 0.75;
  }

  // 3. Corporate Portfolio Path-Dependency Drawdown Brake
  let portfolioBrake = 1.00;
  if (vPortfolioDD >= 10.0) {
    portfolioBrake = 0.40;
  } else if (vPortfolioDD >= 5.0) {
    portfolioBrake = 0.65;
  }

  // 4. Synthesize Compound Margin Sufficiency
  const mReq = vSpanPct + shield + tau;
  const lotsRaw = Math.floor(capital / (vPrice * lotSize * mReq));

  // 5. Asymmetric Dynamic Leverage Ceilings
  const lBase = vIsLong ? 3.25 : 1.75;
  const kappaOI = (vIsLong && vAggregateOI) ? 1.20 : 1.0;

  // Preemptive Margin-Skew Contraction
  let phiSkew = 1.0;
  const G_STAR = 2.0, BETA = 0.15;
  if (Number.isFinite(vMarginGap)) {
    phiSkew = Math.min(1.0, Math.max(0.40, 1 - BETA * Math.max(0, vMarginGap - G_STAR)));
  }

  // 6. Final Dual-Firewall Synthesis Clamp
  const leff = lBase * kappaOI * phiSkew * psiDTE * portfolioBrake;
  const lotsCeil = Math.floor((capital * leff) / (vPrice * lotSize));
  vambLots = Math.max(0, Math.min(lotsRaw, lotsCeil));
  rsaeCalc = { leff, shield, lotsCeil, lotsRaw, mReq };
}
```

---

## 5. Real Market Data Payloads & Historical Stress Regimes

The data payloads below are extracted directly from production databases (`data/margins.db` and `data/price.db`).

### 5.1 Regime 1: Normal Low-Volatility Consolidation (Dec 2, 2025)
- **Context:** Quiet market regime prior to winter squeeze. Initial margin is low, volatility is moderate.
- **Contract:** `24FEB2026` (MCX Natural Gas Big)

```json
{
  "date": "2025-12-02",
  "symbol": "NATURALGAS",
  "expiry": "24FEB2026",
  "dte": 84,
  "close": 284.50,
  "lot_size": 1250,
  "initial_margin_pct": 14.58,
  "daily_volatility": 2.3087,
  "annualized_volatility": 36.5038,
  "rolling_realized_vol_20d": 35.80,
  "oi_aggregate_build_5d": true,
  "margin_vs_realized_vol_gap": -21.22
}
```

### 5.2 Regime 2: The Extreme Crash & Volatility Quadrupling (Feb 2, 2026)
- **Context:** Massive winter commodity collapse. Price experienced a single-day **-27.15% collapse**, annualized realized volatility exploded to **145.9%**, and MCX quadrupled margin requirements from ~14% to **66.05%**.
- **Contract:** `24FEB2026` (MCX Natural Gas Big)

```json
{
  "date": "2026-02-02",
  "symbol": "NATURALGAS",
  "expiry": "24FEB2026",
  "dte": 22,
  "close": 294.90,
  "lot_size": 1250,
  "return_1d_pct": -27.1492,
  "initial_margin_pct": 66.05,
  "daily_volatility": 9.2298,
  "annualized_volatility": 145.936,
  "rolling_realized_vol_20d": 135.35,
  "oi_aggregate_build_5d": false,
  "margin_vs_realized_vol_gap": -69.30
}
```

### 5.3 Regime 3: Near-Expiry Delivery Tender Window (Feb 18–20, 2026)
- **Context:** Mandatory delivery tender week during final 6 DTE. MCX steps up tender margins in 5% daily increments.

```json
[
  {
    "date": "2026-02-18",
    "dte": 6,
    "close": 288.40,
    "initial_margin_pct": 47.49,
    "tender_margin_pct": 5.0,
    "total_margin_pct": 52.49
  },
  {
    "date": "2026-02-19",
    "dte": 5,
    "close": 279.10,
    "initial_margin_pct": 46.10,
    "tender_margin_pct": 10.0,
    "total_margin_pct": 56.10
  },
  {
    "date": "2026-02-20",
    "dte": 4,
    "close": 283.60,
    "initial_margin_pct": 44.70,
    "tender_margin_pct": 15.0,
    "total_margin_pct": 59.70
  }
]
```

### 5.4 Regime 4: Current Live Market Environment (Oct 29, 2026)
- **Context:** Current active front-month contract trading at exchange close.
- **Contract:** `24NOV2026` (MCX Natural Gas Big)

```json
{
  "date": "2026-10-29",
  "symbol": "NATURALGAS",
  "expiry": "24NOV2026",
  "dte": 26,
  "price": 291.50,
  "lot_size": 1250,
  "initial_margin_pct": 13.52,
  "annualized_volatility": 33.9486,
  "rolling_realized_vol_20d": 33.219,
  "oi_aggregate_build_5d": false,
  "margin_vs_realized_vol_gap": -19.519,
  "portfolio_drawdown_pct": 0.0
}
```

---

## 6. Mathematical Step-by-Step Walkthroughs

The following four scenarios trace every intermediate variable through the engine.

### Scenario A: Current Active Contract (Oct 29, 2026) — LONG
- **Inputs:** Capital = ₹1,00,00,000 (₹1 Crore), Price = ₹291.50, Lot Size = 1,250, SPAN Margin = 13.52%, $\sigma_{\text{ann}} = 33.95\%$, DTE = 26, OI Build = False, Direction = LONG, Portfolio Drawdown = 0%.
- **Step 1 (Shield):**
  $$\text{Shield} = \min(0.40, \max(0.10, 0.25 \times 0.3395)) = \min(0.40, \max(0.10, 0.0849)) = 0.1000 \text{ (10.0\%)}$$
- **Step 2 (Tender):** DTE = 26 > 7 $\implies \tau = 0.00$, $\psi_{\text{DTE}} = 1.00$.
- **Step 3 (Drawdown Brake):** DD = 0% $\implies \text{portfolioBrake} = 1.00$.
- **Step 4 (Margin Sufficiency):**
  $$m_{\text{Req}} = 0.1352 + 0.1000 + 0 = 0.2352 \text{ (23.52\%)}$$
  $$\text{Notional per Lot} = 291.50 \times 1250 = \text{₹}3,64,375$$
  $$\text{Margin Req per Lot} = 364375 \times 0.2352 = \text{₹}85,701$$
  $$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{10000000}{85701} \right\rfloor = \mathbf{116 \text{ lots}}$$
- **Step 5 (Leverage Ceiling):**
  $$\mathcal{L}_{\text{Base}} = 3.25, \quad \kappa_{\text{OI}} = 1.00, \quad \phi_{\text{Skew}} = 1.00, \quad \psi_{\text{DTE}} = 1.00, \quad \text{portfolioBrake} = 1.00$$
  $$\mathcal{L}_{\text{eff}} = 3.25 \times 1.0 \times 1.0 \times 1.0 \times 1.0 = 3.25\times$$
  $$\text{Lots}_{\text{Ceil}} = \left\lfloor \frac{10000000 \times 3.25}{364375} \right\rfloor = \left\lfloor \frac{32500000}{364375} \right\rfloor = \mathbf{89 \text{ lots}}$$
- **Step 6 (Synthesis):**
  $$\text{VAMB Lots} = \min(116, 89) = \mathbf{89 \text{ lots}}$$
  $$\text{Max Possible Lots (at SPAN 13.52\%)} = \left\lfloor \frac{10000000}{364375 \times 0.1352} \right\rfloor = \left\lfloor \frac{10000000}{49263.5} \right\rfloor = 202 \text{ lots}$$
  $$\text{VAMB Utilization \%} = \operatorname{round}\left(\frac{89}{202} \times 100\right) = \mathbf{44\%}$$
- *Binding Constraint:* **Leverage Ceiling Firewall** clamps the trade to 89 lots (protects against over-leveraging during low SPAN margin).

---

### Scenario B: Current Active Contract (Oct 29, 2026) — SHORT
- **Inputs:** Capital = ₹1,00,00,000, Price = ₹291.50, Lot Size = 1,250, SPAN Margin = 13.52%, $\sigma_{\text{ann}} = 33.95\%$, DTE = 26, Direction = SHORT, Portfolio Drawdown = 0%.
- **Step 1 (Shield):**
  $$\text{Shield} = \min(0.40, \max(0.18, 0.40 \times 0.3395)) = \min(0.40, \max(0.18, 0.1358)) = 0.1800 \text{ (18.0\%)}$$
- **Step 2 (Tender):** $\tau = 0$, $\psi_{\text{DTE}} = 1.00$.
- **Step 3 (Drawdown Brake):** $\text{portfolioBrake} = 1.00$.
- **Step 4 (Margin Sufficiency):**
  $$m_{\text{Req}} = 0.1352 + 0.1800 + 0 = 0.3152 \text{ (31.52\%)}$$
  $$\text{Margin Req per Lot} = 364375 \times 0.3152 = \text{₹}1,14,851$$
  $$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{10000000}{114851} \right\rfloor = \mathbf{87 \text{ lots}}$$
- **Step 5 (Leverage Ceiling):**
  $$\mathcal{L}_{\text{Base}} = 1.75 \text{ (Short Base Leverage)}$$
  $$\mathcal{L}_{\text{eff}} = 1.75\times$$
  $$\text{Lots}_{\text{Ceil}} = \left\lfloor \frac{10000000 \times 1.75}{364375} \right\rfloor = \left\lfloor \frac{17500000}{364375} \right\rfloor = \mathbf{48 \text{ lots}}$$
- **Step 6 (Synthesis):**
  $$\text{VAMB Lots} = \min(87, 48) = \mathbf{48 \text{ lots}}$$
  $$\text{VAMB Utilization \%} = \operatorname{round}\left(\frac{48}{202} \times 100\right) = \mathbf{24\%}$$
- *Binding Constraint:* **Short Asymmetric Leverage Ceiling** limits position to 48 lots (insulates against explosive squeeze risk).

---

### Scenario C: Extreme Volatility Spike Regime (Feb 2, 2026 Crash) — LONG
- **Inputs:** Capital = ₹1,00,00,000, Price = ₹294.90, Lot Size = 1,250, SPAN Margin = 66.05%, $\sigma_{\text{ann}} = 135.35\%$, DTE = 22, Direction = LONG, Portfolio Drawdown = 0%.
- **Step 1 (Shield):**
  $$\text{Shield} = \min(0.40, \max(0.10, 0.25 \times 1.3535)) = \min(0.40, 0.3384) = 0.3384 \text{ (33.84\%)}$$
- **Step 2 (Tender):** $\tau = 0$, $\psi_{\text{DTE}} = 1.00$.
- **Step 3 (Drawdown Brake):** $\text{portfolioBrake} = 1.00$.
- **Step 4 (Margin Sufficiency):**
  $$m_{\text{Req}} = 0.6605 + 0.3384 = 0.9989 \text{ (99.89\% margin requirement!)}$$
  $$\text{Notional per Lot} = 294.90 \times 1250 = \text{₹}3,68,625$$
  $$\text{Margin Req per Lot} = 368625 \times 0.9989 = \text{₹}3,68,220$$
  $$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{10000000}{368220} \right\rfloor = \mathbf{27 \text{ lots}}$$
- **Step 5 (Leverage Ceiling):**
  $$\mathcal{L}_{\text{Base}} = 3.25 \implies \text{Lots}_{\text{Ceil}} = \left\lfloor \frac{10000000 \times 3.25}{368625} \right\rfloor = 88 \text{ lots}$$
- **Step 6 (Synthesis):**
  $$\text{VAMB Lots} = \min(27, 88) = \mathbf{27 \text{ lots}}$$
  $$\text{Max Possible Lots (at SPAN 66.05\%)} = \left\lfloor \frac{10000000}{368625 \times 0.6605} \right\rfloor = 41 \text{ lots}$$
  $$\text{VAMB Utilization \%} = \operatorname{round}\left(\frac{27}{41} \times 100\right) = \mathbf{66\%}$$
- *Binding Constraint:* **Margin Sufficiency Firewall** binds the trade to 27 lots. If a trader held the max 41 lots, any 3% intraday wiggle would cause liquidation. With 27 lots, the account safely absorbs the extreme volatility.

---

### Scenario D: Near-Expiry Tender Window with Portfolio Drawdown (DTE = 3, DD = 8%)
- **Inputs:** Capital = ₹50,00,000, Price = ₹280.00, Lot Size = 1,250, SPAN Margin = 45.0%, $\sigma_{\text{ann}} = 40.0\%$, DTE = 3, Direction = LONG, Portfolio Drawdown = 8.0%.
- **Step 1 (Shield):**
  $$\text{Shield} = \min(0.40, \max(0.10, 0.25 \times 0.40)) = 0.1000 \text{ (10.0\%)}$$
- **Step 2 (Tender Surcharge & Taper):**
  $$\text{DTE} = 3 \le 7 \implies \tau = 0.08 \times \left(\frac{8 - 3}{7}\right) = 0.08 \times \frac{5}{7} = 0.0571 \text{ (+5.71\% surcharge)}$$
  $$\text{DTE} = 3 \le 3 \implies \psi_{\text{DTE}} = 0.50 \text{ (50\% leverage reduction)}$$
- **Step 3 (Drawdown Brake):**
  $$\text{DD} = 8.0\% \ge 5.0\% \implies \text{portfolioBrake} = 0.65 \text{ (35\% defensive haircut)}$$
- **Step 4 (Margin Sufficiency):**
  $$m_{\text{Req}} = 0.4500 + 0.1000 + 0.0571 = 0.6071 \text{ (60.71\%)}$$
  $$\text{Notional per Lot} = 280 \times 1250 = \text{₹}3,50,000$$
  $$\text{Margin Req per Lot} = 350000 \times 0.6071 = \text{₹}2,12,485$$
  $$\text{Lots}_{\text{Raw}} = \left\lfloor \frac{5000000}{212485} \right\rfloor = \mathbf{23 \text{ lots}}$$
- **Step 5 (Leverage Ceiling):**
  $$\mathcal{L}_{\text{eff}} = 3.25 \times 1.0 \times 1.0 \times 0.50 \times 0.65 = 1.056\times$$
  $$\text{Lots}_{\text{Ceil}} = \left\lfloor \frac{5000000 \times 1.056}{350000} \right\rfloor = \left\lfloor \frac{5280000}{350000} \right\rfloor = \mathbf{15 \text{ lots}}$$
- **Step 6 (Synthesis):**
  $$\text{VAMB Lots} = \min(23, 15) = \mathbf{15 \text{ lots}}$$
- *Binding Constraint:* Both the Tender Taper ($\psi_{\text{DTE}} = 0.50$) and Portfolio Drawdown Brake ($0.65$) combine to compress gross leverage to $1.05\times$, preserving capital during late-stage contract rollover.

---

## 7. Open Technical Constraints & Potential Improvement Vectors

1. **Discrete vs. Continuous Drawdown Brake:** The drawdown brake uses step functions ($5\%$ and $10\%$). A continuous sigmoidal or exponential decay curve could eliminate cliff-edge sizing jumps.
2. **Backward-Looking Realized Volatility:** The model relies on 20-day historical realized volatility ($\sigma_{\text{ann}}$). Incorporating options implied volatility (IV) or high-frequency Parkinson/Garman-Klass intraday range volatility could provide faster reaction time to emerging market shocks.
3. **Decoupling from Trade Stop Distance:** The engine derives lots purely from clearinghouse margin absorption and macro leverage ceilings. It does not explicitly take an Average True Range (ATR) stop distance into account.
4. **Term Structure Slope (Contango / Backwardation):** The base leverage ceiling ($\mathcal{L}_{\text{Base}}$) is fixed regardless of whether the forward curve is in steep Contango (storage overhang) or acute Backwardation (immediate physical scarcity).
