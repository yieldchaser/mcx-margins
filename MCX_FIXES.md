# MCX Margins Dashboard — Post-Build Fix Pass

This file contains all identified issues from a visual audit of the
implemented dashboard. Work through each fix exactly as written.
Complete and verify one fix before moving to the next.
Do not batch multiple fixes into a single edit.

Before touching any fix, read the current state of the relevant
section in index.html and export_json.py first. Match existing
naming conventions exactly.

---

## CRITICAL FIXES
These break core analytical value. Do these first, in order.

---

### FIX 1 — Add ±2σ band to the Prediction Model chart

**File:** `docs/index.html`
**Location:** Analytics tab — "Margin Prediction Model — Panic Spread
(Full Forward Curve)" chart

**Problem:** Only ±1σ band is rendered. The ±2σ outer band is
completely absent despite being specified and computed in
`forecast_bands.json`.

**What to do:**
- Read `docs/data/forecast_bands.json` to confirm `sigma_2` exists
  per expiry
- On the prediction model chart, add two additional fill datasets:
  - upper_2σ and lower_2σ as a shaded fill, lighter opacity than 1σ
    (e.g. rgba(34, 197, 94, 0.10) vs 1σ at rgba(34, 197, 94, 0.22))
  - The 2σ fill sits behind the 1σ fill visually
- Update the legend to show three items:
  "Current Margin % | Predicted Tomorrow % | ±1σ | ±2σ"
- Update the chart tooltip to show:
  "Predicted: X% | 1σ range: [A%–B%] | 2σ range: [C%–D%]"

Verify the 2σ band is visibly wider than the 1σ band before proceeding.

---

### FIX 2 — Fix 1σ and 2σ hit rate color logic in Model Health scorecard

**File:** `docs/index.html`
**Location:** Analytics tab — "Model Health — Prediction Backtest Scorecard"

**Problem:** The 1σ hit rate is 86.7% (target 68%) and is colored green.
This is wrong. A hit rate significantly *above* the theoretical target
means the uncertainty bands are too wide — the model is over-conservative.
This should be flagged as a calibration warning, not a success.

**What to do:**
- Redefine the color logic for interval hit rate rows:
  - Green: within ±5 percentage points of the theoretical target
    (68% for 1σ, 95% for 2σ)
  - Amber: 5–15 percentage points above OR below target
  - Red: more than 15 percentage points away from target in either
    direction
- With this logic, 86.7% (1σ, 30d) should be red (18.7pp above target)
- 93.3% (2σ, 30d) should be green (within 5pp of 95%)
- 81.1% (1σ, 90d) should be red (13.1pp above)
- Add a small italicized note below the hit rate rows:
  "Hit rates above target indicate bands are too wide (model is
  over-conservative). Hit rates below target indicate bands are
  too narrow (model underestimates uncertainty)."
- Tooltip on 1σ hit rate label: "% of actual next-day margins that
  fell within the ±1σ prediction band. Target: ~68% (1 standard
  deviation). Significantly above 68% = bands are too wide.
  Below 68% = bands are too narrow and unreliable."
- Tooltip on 2σ hit rate label: "% of actuals within the ±2σ band.
  Target: ~95%. Values well above 95% mean the model is being
  overly cautious in its uncertainty estimate."

Verify the hit rate cells for 1σ (30d and 90d) now show red or amber
before proceeding.

---

### FIX 3 — Fill the P10–P90 confidence cone on Term Structure

**File:** `docs/index.html`
**Location:** Term Structure tab — "Forward Margin Curve — All Active
Expiries" chart

**Problem:** The P10, P50, P90 confidence cone is rendered as three
dashed lines only. No shaded fill exists between P10 and P90.
The fill is what makes the cone readable as a range band.

**What to do:**
- Add a Chart.js `fill` between the P10 and P90 datasets using
  `fill: '+1'` or equivalent target-fill syntax
- Fill color: rgba(99, 102, 241, 0.15) — subtle indigo, distinct from
  the existing blue/orange curve colors
- The P50 line should sit inside the filled band as a visible dashed
  line (no fill of its own)
- The P10 and P90 boundary lines should remain as dashed lines at the
  edges of the filled area
- On hover at any point on the cone, show:
  "At this DTE historically — P10: X% | P50: X% | P90: X% |
  Current is P[N] — [above/below/near] the median"

Verify the shaded region is visibly filled between P10 and P90
before proceeding.

---

### FIX 4 — Add "All-time / Recent 5Y" toggle to Term Structure cone

**File:** `docs/index.html`
**Location:** Term Structure tab — same chart as FIX 3

**Problem:** The toggle between all-time and Regime B (last 5 years)
percentile bands was specified but is completely absent.

**What to do:**
- Add two toggle buttons above the forward curve chart, styled to match
  the existing toggle buttons on the Seasonality tab (same CSS class):
  "All-time" | "Recent (5Y)"
- Default active state: "All-time"
- When "Recent (5Y)" is selected, swap the P10/P50/P90 datasets from
  `p10_alltime / p50_alltime / p90_alltime` to
  `p10_recent / p50_recent / p90_recent` in `curve_cone.json`
- The chart title should update to reflect the selection:
  "Forward Margin Curve — All Active Expiries
  [Historical cone: All-time | Recent 5Y]"
- Add a tooltip on the toggle: "All-time uses all historical data
  back to 2010. Recent (5Y) uses only Regime B observations (2019–
  present, elevated vol era) for a like-for-like comparison with
  today's market structure."

Verify both toggle states render different cone widths and that
the "Recent 5Y" cone is meaningfully different from the all-time
cone before proceeding.

---

### FIX 5 — Add gradient progress bar to Regime/Stress Score badge

**File:** `docs/index.html`
**Location:** Global header — Regime badge (top right, all tabs)

**Problem:** The badge shows "NORMAL" and "Score: 56 / 100" as text
only. The specified gradient progress bar (0–100 visual scale with
green→yellow→orange→red gradient) is completely absent. Without it,
the score is just a number with no visual weight.

**What to do:**
- Below the "NORMAL" label and "Score: 56 / 100" text, add a thin
  horizontal progress bar (height: 4px, width: ~80px)
- The bar background is the full gradient:
  `linear-gradient(to right, #22c55e, #eab308, #f97316, #ef4444)`
- The bar has a white/bright indicator line or notch positioned at
  the score percentage (56% from left = 56/100)
- Alternatively: fill the bar from left to the score position with
  the color corresponding to that score zone, leaving the rest dark
- Score-to-color mapping:
  - 0–40: green (#22c55e)
  - 40–60: yellow (#eab308)
  - 60–75: orange (#f97316)
  - 75–90: red-orange
  - 90–100: red (#ef4444)
- Tooltip on the entire badge widget:
  "Composite stress score (0–100) = average of margin percentile
  rank (P[X] all-time, 5-year trailing) and volatility percentile
  (P[Y], 5-year trailing). Score 0–40 = CALM, 40–60 = NORMAL,
  60–75 = MONITOR, 75–90 = ELEVATED, 90+ = STRESS. Today: margin
  at P[X], vol at P[Y], composite = [score]."
  Replace [X], [Y], [score] with live values from stress_score.json.

Verify the gradient bar is visible and the notch/fill correctly
reflects the current score before proceeding.

---

## HIGH PRIORITY FIXES
Specified features that are missing or incorrect.

---

### FIX 6 — Color-code the Hist. Pct column in Overview expiry table

**File:** `docs/index.html`
**Location:** Overview tab — "Current Margin Snapshot" table,
"Hist. Pct" column

**Problem:** P68, P65, P54, P13, P14, P7 are all displayed in identical
white text. The column's entire purpose is relative context — without
color, low and high percentiles are visually indistinguishable.

**What to do:**
- Apply text color to each Hist. Pct cell based on its value:
  - P0–P33: green (#22c55e) — cheap margin territory
  - P33–P66: white/neutral — normal range
  - P66–P80: amber (#f59e0b) — elevated, watch
  - P80–P100: red (#ef4444) — historically expensive
- With current data: P68 → amber, P65 → neutral, P54 → neutral,
  P13 → green, P14 → green, P7 → green
- Tooltip on the "Hist. Pct" column header:
  "Percentile rank of today's margin vs all historical observations
  at the same days-to-expiry (±15 days). Green = historically cheap.
  Amber = elevated. Red = historically expensive. P50 = median."
- Tooltip on each individual cell value:
  "This expiry's margin of [X]% is higher than [N]% of all
  historical readings at equivalent DTE (±15 days). Based on
  [n] historical observations."

Verify P7 and P13 are green, P65 is white, P68 is amber
before proceeding.

---

### FIX 7 — Add amber row glow for high P(hike) rows in Panic Spread table

**File:** `docs/index.html`
**Location:** Overview tab — "Panic Spread Signals" table

**Problem:** Rows with P(hike) > 65% (28JUL at 67%, 26AUG at 78%,
and 25SEP if applicable) have no visual distinction from lower-probability
rows. The amber glow was specified as the primary at-a-glance warning.

**What to do:**
- For any row where `p_hike > 0.65`, apply a subtle left border and
  background tint:
  - `border-left: 3px solid #f59e0b`
  - `background: rgba(245, 158, 11, 0.07)`
- Do NOT apply this to CUT-dominant or FLAT-dominant rows regardless
  of their probability
- The existing HIKE badge color and probability text stay as-is —
  this is purely an additive row-level indicator
- If P(hike) > 0.80, escalate the glow:
  - `border-left: 3px solid #ef4444`
  - `background: rgba(239, 68, 68, 0.09)`
- Add a tooltip on the amber/red row indicator:
  "High hike probability alert. The logistic model assigns [X]%
  probability of a margin increase >0.5% for this expiry tomorrow.
  Historically, readings above 65% were followed by an actual hike
  within 2 days in [Y]% of cases." (Compute [Y] from your backtest
  data and insert it — do not hardcode.)

Verify the 28JUL and 26AUG rows have visible amber tinting
before proceeding.

---

### FIX 8 — Add vertical reference lines to the Delta Distribution histogram

**File:** `docs/index.html`
**Location:** Analytics tab — "Margin Change Distribution" chart

**Problem:** Two reference lines are missing:
1. A vertical line at delta = 0 (separating cut from hike territory)
2. A vertical line at today's model-predicted delta

**What to do:**
- Add a delta=0 reference line as a Chart.js annotation plugin line,
  or implement as a zero-width dataset with a point at max frequency:
  - Color: white, opacity 0.4, dashed (2px dash)
  - Label: "0" at the top of the line
- Add today's predicted delta line:
  - Pull the predicted delta from `forecast_bands.json`
    (predicted[front_month] - current[front_month])
  - Color: orange (#f97316), dashed, labeled "Model: [+/-X%]"
- Both lines should sit behind the histogram bars in z-order
- Tooltip when hovering near the predicted delta line:
  "Today's model predicts a [+/-X%] change for the front-month.
  This falls at approximately the P[N] percentile of historical
  daily changes in the current DTE bucket."

Verify both vertical lines are visible against the histogram bars
before proceeding.

---

### FIX 9 — Fix "Full: 0%–100%" range in Seasonality tooltip

**File:** `export_json.py` (data fix) + `docs/index.html` (tooltip fix)
**Location:** Seasonality tab — monthly box plot tooltips

**Problem:** The tooltip shows "Full: 0%–100%" for December (and likely
other months). This is occurring because the min/max computation is
running on individual daily rows rather than monthly averages. A range
of 0%–100% is meaningless and destroys trust in the chart.

**What to do in export_json.py:**
- For the seasonality box plot computation, group data by year-month
  first, compute the monthly average for each year, then compute
  min/p10/p25/median/p75/p90/max across those ~16 annual averages
- This means for December, you get ~16 data points (one per year),
  not 16×31 daily rows
- The resulting min/max will be meaningful (e.g. 7%–34% for December)
- Rerun and verify `seasonality_boxplot.json` has sensible ranges

**What to do in index.html:**
- Remove the "Full: 0%–100%" line from the tooltip if it's hardcoded
- Replace with the correctly computed min/max from the updated JSON
- Updated tooltip format:
  "[Month] — Median: X% | Mean: X% | IQR: [P25–P75] |
  Range (P10–P90): [A–B]% | Min/Max: [C%–D%] | n=[N] years"
  where n is the number of annual data points, not daily rows

Verify December shows a sensible range (not 0%–100%) before proceeding.

---

### FIX 10 — Highlight current month in Seasonality box plot

**File:** `docs/index.html`
**Location:** Seasonality tab — "Average Margin by Month" box plot

**Problem:** April (the current month) has no visual distinction from
other months. The prompt specified it should be highlighted distinctly.

**What to do:**
- Apply a distinct highlight to the current month's box:
  - IQR bar (P25–P75): brighter color, e.g. rgba(99, 102, 241, 0.7)
    vs other months at rgba(99, 102, 241, 0.4)
  - Add a subtle top label or arrow above the current month bar:
    "▲ Now"
- The current month is determined dynamically from today's date
  (new Date().getMonth()), not hardcoded
- The highlight should also apply in "Last 5 Years" toggle mode
- Add to the current month's tooltip:
  "← Current month. Today's front-month margin of [X]% is P[N]
  for [Month] historically. The current reading is
  [above/below/near] the seasonal median."

Verify April has a visibly brighter bar and a "▲ Now" label
before proceeding.

---

## MEDIUM PRIORITY FIXES
Polish, calibration, and completeness.

---

### FIX 11 — Add tooltips to each metric row in Model Health scorecard

**File:** `docs/index.html`
**Location:** Analytics tab — Model Health table metric name cells

**Problem:** The metric name cells (Directional Accuracy, MAE, RMSE,
1-sigma Hit Rate, 2-sigma Hit Rate, Sample Size) are plain text
with no hover context. Every new element was supposed to have a tooltip.

**What to do:**
- Add a `title` attribute or custom tooltip to each metric label cell:
  - Directional Accuracy: "% of days where the model correctly
    predicted whether margin would go up or down. Random guessing = 50%.
    Edge begins above ~55%. Strong edge above 60%."
  - MAE: "Mean Absolute Error — average size of prediction error in
    percentage points. Lower = more accurate level forecasts.
    Current regime MAE of [X]% means predictions are off by [X]%
    on average."
  - RMSE: "Root Mean Squared Error — like MAE but penalizes large
    errors more heavily. A much higher RMSE vs MAE indicates
    occasional large misses dominate the error profile."
  - 1-sigma Hit Rate: "% of actual next-day margins that fell inside
    the ±1σ prediction band. Theoretical target: 68%. Above 68% =
    bands are too wide. Below 68% = bands are dangerously narrow."
  - 2-sigma Hit Rate: "% of actuals inside the ±2σ band.
    Theoretical target: 95%. Values well above 95% indicate excessive
    conservatism in the uncertainty estimate."
  - Sample Size: "Number of trading days used to compute each window's
    metrics. 30d and 90d windows have small samples — treat those
    metrics as directional signals, not statistically robust estimates."

---

### FIX 12 — Add tooltips to Panic Spread table column headers

**File:** `docs/index.html`
**Location:** Overview tab — Panic Spread Signals table headers

**Problem:** The column headers EXPIRY, CURRENT %, PREDICTED,
PROBABILITY, SIGNAL have no tooltips. PROBABILITY in particular
needs context since it's a new column that replaces the old plain badge.

**What to do:**
- Add tooltip to each column header:
  - EXPIRY: "Contract expiry date being evaluated."
  - CURRENT %: "Today's total margin requirement for this expiry."
  - PREDICTED: "Model's point estimate for tomorrow's margin.
    Formula: 0.886 × current_margin + 43.0 × daily_vol."
  - PROBABILITY: "Logistic model probabilities of three outcomes
    tomorrow: margin cut (>0.5% decrease), flat (±0.5%), or hike
    (>0.5% increase). Trained on [N] historical observations.
    Brier score: [X] — shown in signal tooltip."
  - SIGNAL: "Dominant outcome by probability. Amber/red glow
    indicates P(hike) > 65% — historically elevated funding risk."

---

### FIX 13 — Fix x-axis label density on Prediction Model chart

**File:** `docs/index.html`
**Location:** Analytics tab — "Margin Prediction Model" chart

**Problem:** The x-axis shows repeated labels like
"27APR2026, 27APR2026, 27APR2026..." for each expiry because the chart
is plotting one data point per forward date rather than one per unique
expiry. The axis is unreadable.

**What to do:**
- Audit how x-axis labels are generated for this chart
- If the chart plots multiple data points per expiry (e.g. a range of
  forward dates), configure the x-axis to show only unique expiry
  labels, one per contract
- Use Chart.js `ticks.callback` to deduplicate: only show a label
  when the expiry value changes from the previous tick
- Alternatively, restructure the dataset so there is exactly one
  x-point per expiry (the expiry date itself), with the predicted
  value and sigma bands as single points per expiry
- The resulting x-axis should read cleanly:
  "27APR2026 | 26MAY2026 | 25JUN2026 | 28JUL2026 | 26AUG2026 |
  25SEP2026"

---

### FIX 14 — Investigate and fix Regime A scatter data

**File:** `export_json.py` + `docs/index.html`
**Location:** History tab — "Margin vs Volatility (Scatter)" chart

**Problem:** The scatter plot x-axis only spans 3.4%–5.2% daily vol.
The full NATURALGAS dataset goes back to 2010, and Regime A (pre-2019,
low-vol) should include observations where daily vol was ~1%–3.5%.
Either the Regime A data points are not being included in the scatter
export, or the chart is filtering them out.

**Additionally:** Regime B shows R²=1.00 which is almost certainly
a display rounding issue — the actual value may be 0.997 or 0.998.

**What to do in export_json.py:**
- Print or log the count of Regime A vs Regime B rows being exported
  to the scatter JSON
- Confirm Regime A rows with daily_vol_pct < 3.5% are included
- If the scatter JSON caps or filters low-vol rows, remove that filter
- For the R² display: store and emit R² to 3 decimal places (e.g. 0.997)
  not rounded to 2 (which produces 1.00)

**What to do in index.html:**
- If Regime A data is now present at low vol values (1%–3.5%), the
  x-axis should auto-extend to show the full range
- The two regression lines should now clearly show the different slopes
  for the two eras
- If the x-axis expansion makes the chart too wide, consider allowing
  horizontal scroll or reducing point size for the dense Regime A cluster
- Display R² values to 3 decimal places in the legend

---

### FIX 15 — Make σ band width vary by expiry DTE on Prediction Model chart

**File:** `export_json.py` + `docs/index.html`
**Location:** Analytics tab — Prediction Model chart

**Problem:** The ±1σ and ±2σ bands appear to be uniform width across
all expiries. In reality, far expiries should have wider bands (more
uncertainty, thinner historical data at those DTEs) and near expiries
should have tighter bands.

**What to do in export_json.py:**
- When computing rolling_sigma for each expiry, segment the residual
  history by DTE bucket:
  - 0–30d DTE: compute sigma from residuals in this bucket
  - 31–90d DTE: compute sigma from residuals in this bucket
  - 91+d DTE: compute sigma from residuals in this bucket
- Assign each expiry's sigma from its relevant DTE bucket
- The front-month (17d DTE) gets the 0–30d sigma
- The Sep expiry (168d DTE) gets the 91+d sigma, which should be larger
- Emit per-expiry sigma values in forecast_bands.json (already the
  structure — just ensure sigma values differ per expiry)

**What to do in index.html:**
- The chart already reads sigma per expiry from the JSON
- Verify visually that the band is narrower at the left (near expiry)
  and wider at the right (far expiry)
- If bands are still uniform, the JSON is emitting identical sigma
  values — go back to export_json.py and fix the bucket assignment

---

## FINAL VERIFICATION CHECKLIST

After all 15 fixes are complete, run through this checklist:

**export_json.py:**
- [ ] Runs end-to-end without error
- [ ] seasonality_boxplot.json shows sensible min/max (not 0%–100%)
- [ ] forecast_bands.json has different sigma_1 values per expiry
- [ ] regime_model.json shows R² to 3 decimal places (not 1.00)
- [ ] Regime A scatter data includes low-vol rows (daily_vol < 3.5%)

**Overview tab:**
- [ ] Hist. Pct column is color-coded (green/neutral/amber/red)
- [ ] Panic spread rows with P(hike) > 65% have amber left border + tint
- [ ] Panic spread rows with P(hike) > 80% have red left border + tint
- [ ] All column headers in Panic Spread table have tooltips
- [ ] Regime badge has visible gradient progress bar

**Term Structure tab:**
- [ ] P10–P90 cone has visible shaded fill between the boundary lines
- [ ] "All-time / Recent 5Y" toggle is present and functional
- [ ] Switching toggle changes the cone width visibly

**History tab:**
- [ ] Scatter x-axis extends to ~1% daily vol (Regime A low-vol era)
- [ ] R² values show 3 decimal places

**Seasonality tab:**
- [ ] Monthly tooltip shows sensible min/max (not 0%–100%)
- [ ] Current month (April) has brighter bar + "▲ Now" label

**Analytics tab:**
- [ ] Prediction model chart shows both ±1σ AND ±2σ filled bands
- [ ] ±2σ band is visibly wider and lighter than ±1σ
- [ ] X-axis labels are deduplicated (one label per unique expiry)
- [ ] Band width is visibly narrower at left (near) and wider at right (far)
- [ ] 1σ hit rate color logic: above target = amber or red, not green
- [ ] Each metric row label in Model Health has a tooltip
- [ ] Delta histogram has vertical line at delta=0
- [ ] Delta histogram has vertical line at today's predicted delta

**Cross-cutting:**
- [ ] No pre-existing functionality is broken
- [ ] All new elements from this fix pass have tooltips
- [ ] No hardcoded values that should be dynamic
