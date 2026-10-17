import re
import os
import sys

section7_text = '''## 7. Natural Gas Quantitative Swing Dynamics, Margin Traps & The Optimal Buffer Engine

Based on empirical backtesting across **123 contract legs** (2020–2026) from [`models/Master_Commodity_Treasury_Model.xlsx`](file:///c:/Users/Dell/Github/mcx-margins/models/Master_Commodity_Treasury_Model.xlsx) (`NG Data` tab):

```mermaid
flowchart TD
    Market["Empirical Natural Gas Market (123 Contract Legs: 2020 - 2026)"]
    
    subgraph Symmetry["Long vs Short Directional Symmetry"]
        S1["Long Legs: 62 (50.4%) | Short Legs: 61 (49.6%)"]
        S2["Zero Directional Bias — Identical Profitability Long or Short"]
    end
    
    subgraph Frequency["Annual Opportunity Universe (Moves per Year)"]
        F1["Swings >= 15%: 17.6 legs / year (1.5 per month)"]
        F2["Swings >= 20%: 11.6 legs / year (1.0 per month)"]
        F3["Swings >= 25%: 7.9 legs / year (8 major legs/yr)"]
        F4["Swings >= 30%: 5.4 legs / year (5 to 6 mega-trends/yr)"]
    end

    subgraph Capture["What You Actually Need to Capture"]
        C1["To make 50% ROC: Capture only 14.2% net move (ONE 15% leg out of 18)"]
        C2["To make 75% ROC: Capture only 21.5% net move (TWO 15%-20% legs out of 12)"]
        C3["To make 85% ROC: Capture only 24.5% net move (TWO 18% legs out of 12)"]
    end

    Market --> Symmetry
    Market --> Frequency
    Frequency --> Capture
```

---

### 7.1 The Buffer Decision: Stress-Testing 7% to 30% Against Adverse Moves

When holding futures, your equity is divided between **Initial Margin (IM)** and a **Cash Buffer**:
$$\\text{Total Trading Capital} = \\text{Margin Deployed} + \\text{Cash Buffer}$$

In Natural Gas, annualized volatility runs at **45% to 55%** (daily volatility $\\sigma \\approx 2.8\\%$ to $3.5\\%$, with weekend weather shocks and weekly EIA inventory gaps reaching $5\\%$ to $9\\%$). Here is how each candidate buffer performs under real-world stress:

```mermaid
flowchart LR
    B7["7% Buffer<br/>❌ FRAGILE<br/>Wiped out by regular 8% inventory gap"]
    --> B10["10% Buffer<br/>⚠️ BARE MINIMUM<br/>Survives gap, zero room for margin hike"]
    --> B15["15% Buffer<br/>⚡ TACTICAL STOP<br/>Absorbs single-day adverse shock"]
    --> B25["20% - 25% Buffer<br/>✅ INSTITUTIONAL GOLD STANDARD<br/>Absorbs 10% gap PLUS 8% margin hike without margin call"]
    --> B30["30% Buffer<br/>🛡️ HYPER-CONSERVATIVE<br/>High safety, drops leverage to <3x"]
```

| Buffer % | Capital Deployed into Margin | Effective Leverage (at 22% Margin) | Max Adverse Move Absorbed | Simultaneous Margin Spike Handled | Desk Recommendation |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **7% Buffer** | 93.0% | **$4.23\\times$** | **-1.65%** | **Zero room** (Immediate margin call) | ❌ **PROHIBITED (Suicidal)** |
| **10% Buffer** | 90.0% | **$4.09\\times$** | **-2.44%** | Can handle +2.0% IM hike | ⚠️ **Bare Minimum (High Stress)** |
| **15% Buffer** | 85.0% | **$3.86\\times$** | **-3.88%** | Can handle +4.0% IM hike | ⚡ **Acceptable with Hard Stop Loss** |
| **20% Buffer** | 80.0% | **$3.64\\times$** | **-5.50%** | Can handle +6.0% IM hike | ✅ **Strong Quant Standard** |
| **25% Buffer** | 75.0% | **$3.41\\times$** | **-7.33%** | Can handle **+8.0% IM hike** | 🏆 **DESK STANDARD (Recommended)** |
| **30% Buffer** | 70.0% | **$3.18\\times$** | **-9.43%** | Can handle +10.0% IM hike | 🛡️ **Hyper-Conservative (Low Drawdown)** |

> [!IMPORTANT]
> **The Dual Shock Principle**: In commodity futures, a sharp adverse move is almost always accompanied by the clearing corporation (MCXCCL) **raising the margin requirement** (e.g. from 18% to 26%). 
> * A **25% Cash Buffer** (earning 6.5% overnight yield) is the institutional sweet spot: it allows you to absorb up to a **7.3% adverse gap** while simultaneously absorbing an unexpected **+8% margin hike** without receiving a margin call or being forced to liquidate at the worst price.

---

### 7.2 Return on Capital (ROC) vs. Underlying Move % Matrix

How much does the underlying Natural Gas contract need to move across an entire year to generate **50%**, **75%**, **85%**, or **100% Return on Capital (ROC)**?

$$\\text{Annual ROC} = \\text{Effective Leverage} \\times \\text{Net Underlying Move Captured} + (\\text{Buffer} \\times \\text{Idle Yield } 6.5\\%)$$

| MCX Initial Margin Regime | Selected Cash Buffer | Effective Leverage | Underlying Move Needed for **50% ROC** | Underlying Move Needed for **75% ROC** | Underlying Move Needed for **85% ROC** | Underlying Move Needed for **100% ROC** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Low Volatility (18% Margin)** | 20% Buffer | $4.44\\times$ | **11.0%** | **16.6%** | **18.8%** | **22.2%** |
| **Low Volatility (18% Margin)** | 25% Buffer | $4.17\\times$ | **11.6%** | **17.6%** | **20.0%** | **23.6%** |
| **Average Regime (22% Margin)** | 20% Buffer | $3.64\\times$ | **13.4%** | **20.3%** | **23.0%** | **27.1%** |
| **Average Regime (22% Margin)** | **25% Buffer** | **$3.41\\times$** | **14.2%** | **21.5%** | **24.5%** | **28.8%** |
| **Average Regime (22% Margin)** | 30% Buffer | $3.18\\times$ | **15.1%** | **23.0%** | **26.1%** | **30.8%** |
| **High Volatility (26% Margin)** | 20% Buffer | $3.08\\times$ | **15.8%** | **24.0%** | **27.2%** | **32.1%** |
| **High Volatility (26% Margin)** | 25% Buffer | $2.88\\times$ | **16.8%** | **25.4%** | **28.9%** | **34.1%** |

---

### 7.3 Empirical Evidence: 123 Contract Legs Breakdown (2020–2026)

From the official 7-year tick/contract history across 123 contract cycles:

| Year | Total Contract Legs | Direction: Long vs Short | Moves $\\ge 15\\%$ | Moves $\\ge 20\\%$ | Moves $\\ge 25\\%$ | Moves $\\ge 30\\%$ | Average Move % | Average MCX Margin % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2020** | 20 legs | 9 Longs / 11 Shorts | 20 | 12 | 4 | 3 | 23.1% | 19.1% |
| **2021** | 14 legs | 9 Longs / 5 Shorts | 14 | 9 | 6 | 5 | 26.4% | 20.0% |
| **2022** | 25 legs | 13 Longs / 12 Shorts | 25 | 20 | 17 | 11 | 33.9% | 29.5% |
| **2023** | 19 legs | 8 Longs / 11 Shorts | 19 | 11 | 6 | 5 | 26.0% | 21.9% |
| **2024** | 18 legs | 9 Longs / 9 Shorts | 18 | 12 | 7 | 5 | 26.6% | 20.5% |
| **2025** | 17 legs | 10 Longs / 7 Shorts | 17 | 11 | 10 | 5 | 27.2% | 23.1% |
| **2026** | 10 legs | 4 Longs / 6 Shorts | 10 | 6 | 5 | 4 | 31.4% | 30.6% |
| **7-YR TOTAL** | **123 legs** | **62 Long (50.4%) / 61 Short (49.6%)** | **123** | **81** | **55** | **38** | **27.4%** | **22.8%** |
| **ANNUAL AVG** | **17.6 / yr** | **8.9 Long / 8.7 Short** | **17.6 / yr** | **11.6 / yr** | **7.9 / yr** | **5.4 / yr** | **—** | **—** |

---

### 7.4 The Game-Changing Takeaways for Desk Execution

```mermaid
flowchart TD
    Insight1["(1) PERFECT 50/50 TWO-WAY MARKET<br/>• 62 Longs vs 61 Shorts over 7 years<br/>• Zero structural upward or downward bias<br/>• Shorting natural gas is just as mathematically lucrative as going long"]

    Insight2["(2) YOU ONLY NEED 1 TO 2 SWINGS PER YEAR<br/>• Natural Gas generates 11.6 swings >= 20% every year<br/>• To make 50% ROC: Catch just ONE 15% leg (Capture rate: 1 out of 18)<br/>• To make 75% ROC: Catch just TWO 15%-20% legs (Capture rate: 2 out of 12)"]

    Insight3["(3) OVERTRADING IS THE REAL RISK<br/>• You do NOT need 100 intraday scalps<br/>• Natural gas is an episodic, fat-tailed trend commodity<br/>• Sit in cash buffer earning 6.5% yield until high-conviction structural inflection"]

    Insight1 --- Insight2 --- Insight3
```

1. **Perfect Directional Symmetry (50.4% Long vs. 49.6% Short)**:
   * Natural Gas has zero structural bias. Commodity supply gluts crash prices as violently as winter freezes spike them. Shorting is fully supported and equal in frequency to longing.
2. **The "Two-Swing" Capture Rule**:
   * To achieve **50% Annual Return on Capital**: You only need to capture a net **14.2% underlying move**. In a market offering **17.6 moves of $\\ge 15\\%$ every year**, catching just **1 swing** achieves your entire annual target.
   * To achieve **75% Annual Return on Capital**: You only need to capture a net **21.5% underlying move**. Catching just **2 out of the 12 annual swings $\\ge 20\\%$** satisfies your full 75% compounding requirement.
3. **Execution Friction & Contango Drag**:
   * Factoring in roll costs (~0.50% to 1.0% per roll), exchange turnover fees/CTT (~0.06% round trip), and execution slippage (~0.15%):
     $$\\text{Total Annual Friction} \\approx 1.5\\% \\text{ to } 2.5\\%.$$
   * A gross captured move of **23% to 24%** easily covers all transaction friction and delivers a clean **75% net return on capital**.
4. **MCX Capacity Bound vs CME**:
   * On MCX, front-month ADV is 20,000–25,000 lots, but **next-month open interest is only 6,000–9,500 lots**.
   * When your position exceeds 4,000 lots, rolling contracts across months moves the market against you. That is why the model caps MCX deployment at **₹103.09 Crores** and sweeps all overflow capital into **Level 4 GIFT City (CME Henry Hub)**, where $15 Billion USD/day absorbs thousands of contracts with zero contango friction.'''

def update_docs():
    paths = [
        "C:/Users/Dell/.gemini/antigravity/brain/e90b5b2c-13aa-474e-9bfa-a42b74b47f3c/plan.md",
        "models/execution_and_tax_validation_plan.md"
    ]
    
    pattern = re.compile(r'## 7\..*?## 8\. GIFT City IFSC Setup Reality, Approvals & Expenses', re.DOTALL)
    
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        
        replacement = section7_text + "\n\n---\n\n## 8. GIFT City IFSC Setup Reality, Approvals & Expenses"
        new_content = pattern.sub(lambda m: replacement, content)
        
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated Section 7 in {p}")

if __name__ == "__main__":
    update_docs()
