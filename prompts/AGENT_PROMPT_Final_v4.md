# MCX Dashboard — Final Enhancement Prompts
# Copy-paste ONE message at a time. Wait for agent to commit before sending the next.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 1 OF 5 — Glassmorphism Tooltips + Mobile
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pull the latest repo first:
```bash
cd mcx-margins && git pull origin main
```

Open `docs/index.html`. Make exactly 3 edits to this file. Do not rewrite anything else.

**Edit 1 — Append this inside the existing `<style>` tag, at the very end of it:**

```css
/* ── Glassmorphism Tooltip System ── */
.has-tooltip { cursor: help; display: inline-flex; align-items: center; gap: 5px; }
.has-tooltip::after {
  content: '?';
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--surface2); border: 1px solid var(--border);
  font-size: 9px; font-weight: 700; color: var(--text-muted); flex-shrink: 0;
}
.has-tooltip:hover::after { background: var(--accent); color: white; border-color: var(--accent); }

#tooltipOverlay {
  display: none; position: fixed; top: 50%; left: 50%;
  transform: translate(-50%, -50%); z-index: 9999;
  background: rgba(22, 27, 34, 0.85);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(56,139,253,0.35); border-radius: 16px;
  padding: 28px 32px; max-width: min(480px, 90vw);
  box-shadow: 0 0 0 1px rgba(56,139,253,0.1), 0 8px 32px rgba(0,0,0,0.6), 0 2px 8px rgba(56,139,253,0.15);
  animation: tooltipIn 0.18s cubic-bezier(0.34,1.56,0.64,1);
  pointer-events: none;
}
#tooltipOverlay.visible { display: block; }
@keyframes tooltipIn {
  from { opacity:0; transform:translate(-50%,-48%) scale(0.94); }
  to   { opacity:1; transform:translate(-50%,-50%) scale(1); }
}
#tooltipOverlay .tt-title {
  font-size: 13px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 0.07em;
  margin-bottom: 12px; padding-bottom: 10px;
  border-bottom: 1px solid rgba(56,139,253,0.2);
}
#tooltipOverlay .tt-body { font-size: 13px; color: var(--text); line-height: 1.65; }
#tooltipOverlay .tt-body strong { color: var(--accent); }
#tooltipOverlay .tt-body em { color: var(--accent-yellow); font-style: normal; }

/* ── Mobile ── */
.stats-bar { display:flex; overflow-x:auto; -webkit-overflow-scrolling:touch; gap:1px; scrollbar-width:none; }
.stats-bar::-webkit-scrollbar { display:none; }
.stat-card { min-width:120px; flex:1; }
.stat-sub { font-size:11px; margin-top:2px; font-weight:500; }
.stat-sub.up   { color: var(--accent-red); }
.stat-sub.down { color: var(--accent-green); }
.stat-sub.flat { color: var(--text-muted); }
.regime-calm     { color: #3fb950; }
.regime-elevated { color: #d29922; }
.regime-stressed { color: #fb8f44; }
.regime-crisis   { color: #f85149; }
.range-btn { background:var(--surface2); color:var(--text-muted); border:1px solid var(--border); border-radius:4px; padding:4px 10px; font-size:12px; cursor:pointer; font-family:Inter,sans-serif; }
.range-btn:hover, .active-range { background:var(--accent); color:white; border-color:var(--accent); }
@media (max-width:900px) {
  .tab-nav { overflow-x:auto; -webkit-overflow-scrolling:touch; white-space:nowrap; padding:0 8px; }
  .tab-btn { padding:12px 14px; font-size:12px; flex-shrink:0; }
  .tab-content { padding:12px; }
  .grid-2, .grid-3 { grid-template-columns:1fr; gap:12px; }
}
@media (max-width:640px) {
  .stat-value { font-size:20px; }
  .chart-container { height:240px; }
  #tooltipOverlay { padding:20px; max-width:92vw; }
  .data-table th, .data-table td { padding:8px; font-size:11px; }
}
```

**Edit 2 — Add this HTML just before `</body>`:**

```html
<div id="tooltipOverlay">
  <div class="tt-title" id="ttTitle"></div>
  <div class="tt-body" id="ttBody"></div>
</div>

<button id="backToTop" style="display:none;position:fixed;bottom:20px;right:20px;z-index:1000;background:var(--accent);color:white;border:none;border-radius:50%;width:40px;height:40px;font-size:18px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.4);" title="Back to top">↑</button>

<footer style="margin-top:40px;padding:20px 24px;border-top:1px solid var(--border);text-align:center;font-size:11px;color:var(--text-muted);">
  Data: MCX CCL (<a href="https://www.mcxccl.com/risk-management/daily-margin" target="_blank" style="color:var(--accent);">mcxccl.com</a>) · Auto-updated weekdays 8 PM IST · <a href="https://github.com/yieldchaser/mcx-margins" target="_blank" style="color:var(--accent);">GitHub</a> · Not financial advice
</footer>
```

**Edit 3 — Append this to the existing `<script>` tag (at the very end, before `</script>`):**

```javascript
// ── Tooltip Data ──
const TOOLTIPS = {
  "Current Margin Snapshot": {
    title: "Current Margin Snapshot — NATURALGAS",
    body: `The <strong>live margin table</strong> shows all active contract expiries for NATURALGAS as of today's MCX CCL update.<br><br>
<strong>Initial %</strong> — Base margin MCX requires to hold 1 lot. Rises sharply as DTE → 0.<br>
<strong>ELM %</strong> — Extreme Loss Margin. Locked at <em>1.25%</em> — MCX's buffer against gap-down opens.<br>
<strong>Tender %</strong> — Extra margin in the last 7 days before expiry. Can spike to 25%+ on expiry day. If you're underfunded and holding a front-month at DTE ≤ 7, expect a forced liquidation notice.<br>
<strong>Total %</strong> = Initial + ELM + Tender + any Additional margin.<br>
<strong>Ann. Vol %</strong> — MCX's annualized volatility estimate. The primary driver of Initial margin changes.`
  },
  "Forward Curve": {
    title: "Forward Curve — Margin Term Structure",
    body: `How MCX-required margin varies across all active expiries today.<br><br>
<strong>Normal (backwardation):</strong> Front month has highest margin — tender pressure + high near-term vol. Curve slopes down left to right. This is the usual shape.<br>
<strong>Unusual (contango):</strong> Far months require more margin. Rare — signals MCX is pricing in future stress (e.g., upcoming supply shocks).<br><br>
<em>The steep kink you see</em> between front and second month is tender margin burning off. Beyond 60 DTE the curve flattens to MCX's "base rate" for the current vol regime.`
  },
  "Panic Spread": {
    title: "Panic Spread Signal Model",
    body: `A predictive signal built from MCX's margin structure and volatility.<br><br>
<strong>Formula:</strong> Predicted Tomorrow = <em>0.886 × Current Margin + 43.0 × Daily Vol</em><br><br>
<strong>▲ HIKE</strong> — MCX likely to raise margin tomorrow. Pre-fund your account tonight.<br>
<strong>▼ CUT</strong> — Margin likely to ease. Capital efficiency improves.<br><br>
<em>Accuracy:</em> Captures ~93% of simultaneous margin-vol correlation. Use as a directional risk signal, not a precise number.`
  },
  "Volatility Term Structure": {
    title: "Volatility Term Structure",
    body: `MCX's annualized volatility estimate across all active expiries.<br><br>
<strong>Normal:</strong> Front-month vol > back-month vol. Near-term uncertainty dominates.<br>
<strong>Inverted:</strong> Far-month vol elevated. Unusual — signals MCX sees stress building 3–6 months out, often from supply/demand shocks.<br><br>
When this chart spikes on the left, watch for a margin hike in the next 1–2 days.`
  },
  "Margin Spread": {
    title: "NATURALGAS vs NATGASMINI Spread",
    body: `Per-expiry margin % difference between the two instruments.<br><br>
<strong>Positive (blue):</strong> NG costs more margin than NGM. NGM is the capital-efficient choice for the same directional bet.<br>
<strong>Negative (red):</strong> NGM costs more — unusual, watch for MCX intervention or liquidity imbalance.<br><br>
When the spread is wide, NGM traders enjoy a meaningful capital advantage.`
  },
  "Initial Margin % Over Time": {
    title: "Historical Margin — Front Month Daily",
    body: `Daily initial margin % for NATURALGAS front month, 2010 to present.<br><br>
<em>2010–2018:</em> Low era (6–15%). Conservative MCX parameters, low global vol.<br>
<em>2019–2021:</em> Transition — US LNG exports + India demand growth drove margins up.<br>
<em>2022–2023:</em> Historic highs (30–65%). Russia-Ukraine war + European gas crisis + extreme Henry Hub vol.<br>
<em>2024–2026:</em> Normalization (20–35%).<br><br>
Use range buttons to zoom into specific crises or calm periods.`
  },
  "Daily Volatility Over Time": {
    title: "Daily Volatility — MCX Estimate",
    body: `MCX CCL's daily volatility estimate for the front-month contract. This is the <strong>primary input</strong> to MCX's margin calculation.<br><br>
A sudden spike here is almost always a leading indicator of a margin hike within 1–2 days. Monitor this alongside the Panic Spread signal for early warning.`
  },
  "Margin vs Volatility": {
    title: "Margin vs Volatility — Scatter",
    body: `Each dot = one trading day. X = daily vol, Y = initial margin.<br><br>
<strong>Tight cluster (bottom-left)</strong> = 2010–2018 low-vol era.<br>
<strong>Extended diagonal</strong> = MCX's vol-to-margin scaling function. Near-linear — margin is almost entirely vol-driven.<br>
<strong>Outliers above trendline</strong> = days MCX charged discretionary extra margin (tender spikes, special margin events). These are rare but operationally significant — margin calls that exceeded what vol alone predicted.`
  },
  "Average Margin by Month": {
    title: "Seasonal Pattern — Monthly Averages",
    body: `Average initial margin % by calendar month across all years (2010–present).<br><br>
<strong>Green bars</strong> = below-median months — cheaper to hold positions.<br>
<strong>Red bars</strong> = above-median months — capital-intensive.<br><br>
<em>Key pattern:</em> JAN–MAR expensive (winter demand uncertainty). APR–OCT cheaper. NOV–DEC escalate again.<br><br>
<strong>Practical use:</strong> Entering a 3-month position in APR vs DEC changes your average margin cost dramatically — and therefore your capital efficiency and risk of margin calls.`
  },
  "Average Margin by Year": {
    title: "Year-over-Year Margin Evolution",
    body: `How MCX's margin regime has changed since 2010.<br><br>
<em>2010–2018:</em> 6–12% average. Range-bound NG, conservative MCX.<br>
<em>2019:</em> First jump — LNG trade expansion.<br>
<em>2022:</em> Peak (~30%+). Russia-Ukraine crisis.<br>
<em>2025–2026:</em> Watch for normalization or re-escalation.<br><br>
Higher average year = MCX in tight risk mode. Traders need proportionally more capital for the same lot size.`
  },
  "Monthly Margin Heatmap": {
    title: "Heatmap — Year × Month",
    body: `The most information-dense view in the dashboard. Each cell = average initial margin % for that month/year.<br><br>
🟢 <em>Dark green</em> = Very low (5–10%) — cheap, easy capital environment.<br>
🟡 <em>Yellow</em> = Elevated (15–25%) — normal active market.<br>
🔴 <em>Red</em> = High (30%+) — capital-intensive, margin call risk.<br><br>
<strong>Read rows</strong> for full-year stress (2022–2023 almost entirely red).<br>
<strong>Read columns</strong> for seasonal patterns (JAN column redder than AUG every year).`
  },
  "DTE vs Margin": {
    title: "Days to Expiry vs Margin — The Expiry Curve",
    body: `How MCX margin changes as a contract approaches expiry.<br><br>
<strong>Blue (Initial):</strong> Rises sharply in the final 30 days. MCX discourages speculative holdover into physical delivery.<br>
<strong>Red (Tender):</strong> Activates only at DTE ≤ 7. Can jump from 0% to 25% overnight — the most dangerous margin event for underfunded accounts.<br><br>
<em>Practical rule:</em> Exit or roll front-month positions at DTE ≥ 15. At DTE ≤ 7, total margin can exceed 50% of contract value.`
  },
  "Lag Correlation": {
    title: "Lag Correlation: Margin vs Volatility",
    body: `How strongly margin correlates with vol at different time lags.<br><br>
<strong>Lag 0 (~0.93):</strong> Today's margin is tightly linked to today's vol — MCX uses same-day vol as primary input.<br>
<strong>Lag 10 (~0.71):</strong> Still meaningful but weakening.<br>
<strong>Lag 20+ (~0.29):</strong> Weak — 3-week-old vol has little predictive power.<br><br>
<em>Key insight:</em> MCX is reactive, not predictive. Hikes feel sudden even when vol has been building for days — because MCX waits for it to materialize.`
  },
  "Margin Prediction Model": {
    title: "Panic Spread — Full Forward Curve",
    body: `Applies the prediction model to every active expiry simultaneously.<br><br>
<strong>Blue solid</strong> = Today's actual margin per expiry.<br>
<strong>Orange dashed</strong> = Predicted margin for tomorrow.<br><br>
Dashed above solid = expect hike for those expiries.<br>
Dashed below solid = expect cut or stability.<br><br>
<em>How to use:</em> If your expiry shows predicted significantly above current, pre-fund your margin account 24 hours in advance. MCX updates margins after market close.`
  },
  "5-Day Rolling": {
    title: "Margin Momentum — Spot vs 5-Day Average",
    body: `<strong>Blue line</strong> = Daily front-month initial margin %.<br>
<strong>Yellow dashed</strong> = 5-day rolling average (smoothed trend).<br><br>
When blue is <em>above</em> yellow and rising: MCX is actively tightening. Expect continued hikes unless vol drops sharply.<br>
When blue is <em>below</em> yellow: Margins are easing. Capital efficiency improving.<br><br>
<strong>Rule of thumb:</strong> If spot is more than 3 percentage points above the 5-day average, pre-fund your account before the next MCX update cycle.`
  },
  "Historical Percentile": {
    title: "Historical Percentile Rank Over Time",
    body: `Where does each day's margin sit relative to all historical readings since 2010?<br><br>
<strong>P90+</strong> (red) = Top 10% of all-time highs. Extreme stress. Capital requirements at historic levels.<br>
<strong>P50–P90</strong> (yellow) = Elevated above historical average.<br>
<strong>P0–P25</strong> (green) = Near historically cheap levels. Best time to build positions from a capital-efficiency standpoint.<br><br>
The 2022–2023 band is almost entirely red. Current 2026 levels are mid-range (~P50–P65).`
  },
  "Regime": {
    title: "Current Margin Regime",
    body: `A real-time classification of the MCX margin environment.<br><br>
🟢 <strong>CALM</strong> — Below 20%, stable. Cheap to hold NG positions.<br>
🟡 <strong>NORMAL</strong> — 20–35%. Standard active market conditions. Monitor weekly.<br>
🟠 <strong>STRESSED</strong> — 35–50%. Elevated vol. MCX may hike further. Reduce speculative exposure.<br>
🔴 <strong>CRISIS</strong> — Above 50%. Extreme conditions (Feb 2026 spike). Serious margin call risk for underfunded accounts. Consider exiting or cutting size significantly.`
  }
};

const ttOverlay = document.getElementById('tooltipOverlay');
let ttHideTimer;

function showTooltip(key) {
  const tt = TOOLTIPS[key];
  if (!tt) return;
  clearTimeout(ttHideTimer);
  document.getElementById('ttTitle').textContent = tt.title;
  document.getElementById('ttBody').innerHTML = tt.body;
  ttOverlay.classList.add('visible');
}
function hideTooltip() {
  ttHideTimer = setTimeout(() => ttOverlay.classList.remove('visible'), 150);
}

// Attach tooltips to card titles after a short delay (so all tabs have rendered)
setTimeout(() => {
  document.querySelectorAll('.card-title').forEach(el => {
    const text = el.textContent.trim();
    const key = Object.keys(TOOLTIPS).find(k => text.toLowerCase().includes(k.toLowerCase().slice(0,12)));
    if (key) {
      el.classList.add('has-tooltip');
      el.addEventListener('mouseenter', () => showTooltip(key));
      el.addEventListener('mouseleave', hideTooltip);
    }
  });
  // Also attach to stat labels
  document.querySelectorAll('.stat-label[data-tooltip-key]').forEach(el => {
    const key = el.dataset.tooltipKey;
    el.classList.add('has-tooltip');
    el.addEventListener('mouseenter', () => showTooltip(key));
    el.addEventListener('mouseleave', hideTooltip);
  });
}, 500);

// Back to top
const bttBtn = document.getElementById('backToTop');
window.addEventListener('scroll', () => {
  bttBtn.style.display = window.scrollY > 300 ? 'flex' : 'none';
  bttBtn.style.alignItems = 'center';
  bttBtn.style.justifyContent = 'center';
});
bttBtn.addEventListener('click', () => window.scrollTo({top:0, behavior:'smooth'}));

// Keyboard tab navigation
const allTabBtns = Array.from(document.querySelectorAll('.tab-btn'));
document.addEventListener('keydown', e => {
  if (['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)) return;
  const active = allTabBtns.findIndex(b => b.classList.contains('active'));
  if (e.key === 'ArrowRight' && active < allTabBtns.length - 1) allTabBtns[active+1].click();
  if (e.key === 'ArrowLeft'  && active > 0) allTabBtns[active-1].click();
});
```

After making these 3 edits, run:
```bash
git add docs/index.html
git commit -m "enhance: glassmorphism tooltips, mobile layout, back-to-top, keyboard nav, footer"
git push
```

**Stop here. Do not proceed to Message 2.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 2 OF 5 — KPI Bar Upgrade
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pull latest: `git pull origin main`

Open `docs/index.html`. Make exactly 2 edits.

**Edit 1 — Find the `.stats-bar` div in the HTML body. Replace the entire `<div class="stats-bar">...</div>` block with:**

```html
<div class="stats-bar" id="statsBar">
  <div class="stat-card">
    <div class="stat-label">FRONT MARGIN %</div>
    <div class="stat-value" id="kpiFrontMargin">—</div>
    <div class="stat-sub" id="kpiMarginChange">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">ELM %</div>
    <div class="stat-value" id="kpiElm">—</div>
    <div class="stat-sub flat" style="color:var(--text-muted);font-size:10px;">Constant</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">DAILY VOL</div>
    <div class="stat-value" id="kpiDailyVol">—</div>
    <div class="stat-sub" id="kpiVolChange">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">ANN. VOLATILITY</div>
    <div class="stat-value" id="kpiAnnVol">—</div>
    <div class="stat-sub" id="kpiPercentile">—</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">DAYS TO EXPIRY</div>
    <div class="stat-value" id="kpiDTE">—</div>
    <div class="stat-sub flat" style="color:var(--text-muted);font-size:10px;">Front month</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">REGIME</div>
    <div class="stat-value" id="kpiRegime" style="font-size:18px;">—</div>
    <div class="stat-sub" id="kpiRegimeSub">—</div>
  </div>
</div>
```

**Edit 2 — Find the existing `(async () => {` IIFE that populates the KPIs. Replace the entire IIFE with:**

```javascript
(async () => {
  try {
    const [meta, current, histNG] = await Promise.all([
      loadJSON('meta'), loadJSON('current'), loadJSON('history_ng')
    ]);
    setStaleness(meta.last_updated);

    const ng = current.NATURALGAS || [];
    const front = ng.filter(c => c.dte >= 0).sort((a,b) => a.dte - b.dte)[0] || ng[0];
    if (!front) return;

    document.getElementById('kpiFrontMargin').textContent = front.initial_margin_pct.toFixed(2) + '%';
    document.getElementById('kpiElm').textContent = front.elm_pct.toFixed(2) + '%';
    document.getElementById('kpiDailyVol').textContent = (front.daily_volatility * 100).toFixed(2) + '%';
    document.getElementById('kpiAnnVol').textContent = (front.annualized_volatility * 100).toFixed(1) + '%';
    document.getElementById('kpiDTE').textContent = front.dte + 'd';

    // Day-over-day change
    if (histNG && histNG.length >= 2) {
      const sorted = [...histNG].sort((a,b) => new Date(b.date) - new Date(a.date));
      const mChange = sorted[0].initial_margin_pct - sorted[1].initial_margin_pct;
      const vChange = ((sorted[0].daily_volatility || 0) - (sorted[1].daily_volatility || 0)) * 100;
      const mEl = document.getElementById('kpiMarginChange');
      const vEl = document.getElementById('kpiVolChange');

      if (Math.abs(mChange) < 0.01) { mEl.textContent = '→ flat'; mEl.className = 'stat-sub flat'; }
      else if (mChange > 0) { mEl.textContent = `▲ +${mChange.toFixed(2)}% vs prev`; mEl.className = 'stat-sub up'; }
      else { mEl.textContent = `▼ ${mChange.toFixed(2)}% vs prev`; mEl.className = 'stat-sub down'; }

      if (Math.abs(vChange) < 0.005) { vEl.textContent = '→ flat'; vEl.className = 'stat-sub flat'; }
      else if (vChange > 0) { vEl.textContent = `▲ +${vChange.toFixed(3)}% vs prev`; vEl.className = 'stat-sub up'; }
      else { vEl.textContent = `▼ ${vChange.toFixed(3)}% vs prev`; vEl.className = 'stat-sub down'; }

      // Historical percentile rank
      const allM = histNG.map(d => d.initial_margin_pct).filter(Boolean).sort((a,b) => a-b);
      const pct = Math.round((allM.filter(v => v <= front.initial_margin_pct).length / allM.length) * 100);
      const pEl = document.getElementById('kpiPercentile');
      pEl.textContent = `Hist. P${pct}`;
      pEl.className = `stat-sub ${pct >= 75 ? 'up' : pct <= 25 ? 'down' : 'flat'}`;
    }

    // Regime
    const m = front.initial_margin_pct;
    const rEl = document.getElementById('kpiRegime');
    const rsEl = document.getElementById('kpiRegimeSub');
    if (m < 20)      { rEl.textContent='🟢 CALM';    rEl.className='stat-value regime-calm';     rsEl.textContent='Low cost';    rsEl.className='stat-sub down'; }
    else if (m < 35) { rEl.textContent='🟡 NORMAL';  rEl.className='stat-value regime-elevated'; rsEl.textContent='Monitor';     rsEl.className='stat-sub flat'; }
    else if (m < 50) { rEl.textContent='🟠 STRESSED';rEl.className='stat-value regime-stressed'; rsEl.textContent='High margin'; rsEl.className='stat-sub up'; }
    else             { rEl.textContent='🔴 CRISIS';  rEl.className='stat-value regime-crisis';   rsEl.textContent='Extreme';     rsEl.className='stat-sub up'; }

  } catch(e) { console.error('KPI load failed:', e); }
})();
```

```bash
git add docs/index.html
git commit -m "enhance: KPI bar — day-over-day change, percentile rank, regime badge"
git push
```

**Stop here. Do not proceed to Message 3.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 3 OF 5 — Snapshot Fix + Analytics Charts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pull latest: `git pull origin main`

Open `docs/index.html`. Make exactly 3 edits.

**Edit 1 — Fix the snapshot table deduplication.**

Inside `renderOverview()`, find where the snapshot table rows are built (the `ng.map(c => ...)` that fills `snapshotBody`). Add deduplication before it:

Replace the line that starts with `const tbody = document.getElementById('snapshotBody');` and everything up to (and including) the `tbody.innerHTML = ...` assignment, with:

```javascript
// Deduplicate — one row per unique expiry
const seen = new Set();
const deduped = ng.filter(c => { if (seen.has(c.expiry)) return false; seen.add(c.expiry); return true; });

const tbody = document.getElementById('snapshotBody');
tbody.innerHTML = deduped.map(c => `
  <tr>
    <td><strong>${c.expiry}</strong></td>
    <td>${dteBadge(c.dte)}</td>
    <td>${c.initial_margin_pct.toFixed(2)}%</td>
    <td>${c.elm_pct.toFixed(2)}%</td>
    <td>${c.tender_margin_pct > 0
      ? `<strong style="color:var(--accent-red)">${c.tender_margin_pct.toFixed(2)}%</strong>`
      : '0.00%'}</td>
    <td><strong>${c.total_margin_pct.toFixed(2)}%</strong></td>
    <td>${c.additional_long_margin_pct.toFixed(2)}%</td>
    <td>${c.additional_short_margin_pct.toFixed(2)}%</td>
    <td>${(c.annualized_volatility * 100).toFixed(1)}%</td>
  </tr>
`).join('');
```

**Edit 2 — Add two new charts to the Analytics tab HTML.**

Find the closing `</div>` of the last card in `#tab-analytics` (after the panic spread card). Append this HTML after it:

```html
<div class="grid-2" style="margin-top:16px;">
  <div class="card">
    <div class="card-title">5-Day Rolling Average vs Spot Margin</div>
    <div class="chart-container"><canvas id="chartMomentum"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Historical Percentile Rank Over Time</div>
    <div class="chart-container"><canvas id="chartPercentile"></canvas></div>
    <p style="font-size:11px;color:var(--text-muted);margin-top:8px;">P90+ = top 10% of all-time highs. P10- = historically cheap levels.</p>
  </div>
</div>
```

**Edit 3 — Add the chart rendering JS.**

Find `renderAnalytics()`. Add this block at the very end of that function (before its closing `}`):

```javascript
  // Momentum + Rolling Average (last 90 days)
  const histNG = await loadJSON('history_ng');
  const sortedHist = [...histNG].sort((a,b) => new Date(a.date)-new Date(b.date));
  const recent = sortedHist.slice(-90);
  const spotData = recent.map(d => d.initial_margin_pct);
  const rolling5 = spotData.map((_,i) => {
    const w = spotData.slice(Math.max(0,i-4), i+1);
    return w.reduce((s,v)=>s+v,0)/w.length;
  });

  new Chart(document.getElementById('chartMomentum'), {
    type: 'line',
    data: {
      labels: recent.map(d => d.date),
      datasets: [
        { label: 'Daily Margin %', data: spotData, borderColor:'#388bfd', backgroundColor:'rgba(56,139,253,0.08)', tension:0.1, pointRadius:0, borderWidth:1.5, fill:true },
        { label: '5-Day Avg', data: rolling5, borderColor:'#d29922', tension:0.3, pointRadius:0, borderWidth:2, borderDash:[4,3] }
      ]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{position:'top'}, tooltip:{mode:'index',intersect:false} },
      scales:{ x:{ticks:{maxTicksLimit:10,font:{size:10}}}, y:{title:{display:true,text:'Margin %'}} }
    }
  });

  // Percentile Rank Over Time (last 365 days)
  const allM = sortedHist.map(d=>d.initial_margin_pct).filter(Boolean);
  const last365 = sortedHist.slice(-365);
  const pctData = last365.map(d => {
    const rank = allM.filter(x=>x<=d.initial_margin_pct).length;
    return Math.round((rank/allM.length)*100);
  });

  new Chart(document.getElementById('chartPercentile'), {
    type: 'line',
    data: {
      labels: last365.map(d=>d.date),
      datasets: [{
        label: 'Percentile Rank',
        data: pctData,
        segment: { borderColor: ctx => { const v=pctData[ctx.p1DataIndex]; return v>=75?'#f85149':v>=50?'#d29922':'#3fb950'; } },
        backgroundColor:'rgba(56,139,253,0.05)',
        tension:0.2, pointRadius:0, borderWidth:2, fill:true
      }]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{display:false},
        tooltip:{ callbacks:{ label: ctx => { const v=ctx.raw; return `P${v} — ${v>=90?'EXTREME':v>=75?'HIGH':v>=50?'ELEVATED':v>=25?'NORMAL':'LOW'}`; } } }
      },
      scales:{
        x:{ticks:{maxTicksLimit:10,font:{size:10}}},
        y:{min:0,max:100,title:{display:true,text:'Percentile'},ticks:{callback:v=>`P${v}`}}
      }
    }
  });
```

```bash
git add docs/index.html
git commit -m "enhance: snapshot deduplication, momentum chart, percentile rank over time"
git push
```

**Stop here. Do not proceed to Message 4.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 4 OF 5 — Heatmap Fix
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pull latest: `git pull origin main`

Open `docs/index.html`. Make exactly 2 edits.

**Edit 1 — Fix the heatmap container div.**

Find:
```html
<div id="heatmapContainer" style="overflow-x:auto;margin-top:8px;"></div>
```

Replace with:
```html
<div id="heatmapContainer" style="overflow-x:auto;overflow-y:auto;max-height:500px;margin-top:8px;border:1px solid var(--border);border-radius:6px;position:relative;"></div>
```

**Edit 2 — Replace the entire heatmap table-building block inside `renderSeasonality()`.**

Find the block that starts with `let html = \`<table` and ends with `document.getElementById('heatmapContainer').innerHTML = html;`

Replace the entire block with:

```javascript
  let html = `<table style="border-collapse:collapse;font-size:11px;width:100%;min-width:700px;table-layout:fixed;">`;

  // Sticky header row
  html += `<thead><tr>
    <th style="position:sticky;top:0;left:0;z-index:3;background:var(--surface2);padding:6px 8px;font-size:10px;color:var(--text-muted);text-align:center;border-right:1px solid var(--border);border-bottom:1px solid var(--border);width:44px;min-width:44px;">YEAR</th>`;
  months.forEach(m => {
    html += `<th style="position:sticky;top:0;z-index:2;background:var(--surface2);padding:6px 4px;text-align:center;font-size:10px;color:var(--text-muted);font-weight:600;border-bottom:1px solid var(--border);white-space:nowrap;">${m}</th>`;
  });
  html += `</tr></thead><tbody>`;

  // Data rows
  years.forEach(y => {
    html += `<tr><td style="position:sticky;left:0;z-index:1;background:var(--surface2);padding:5px 8px;font-weight:700;font-size:10px;color:var(--text-muted);text-align:center;border-right:1px solid var(--border);white-space:nowrap;">${y}</td>`;
    months.forEach(m => {
      const v = data[y]?.[m];
      const bg = marginToColor(v, minV, maxV);
      const brightness = v == null ? 0 : (v - minV) / (maxV - minV);
      const textColor = v == null ? 'transparent' : (brightness > 0.3 && brightness < 0.72) ? '#111' : '#fff';
      html += `<td title="${y} ${m}: ${v != null ? v.toFixed(1)+'%' : 'No data'}" style="padding:5px 2px;background:${bg};text-align:center;color:${textColor};font-weight:600;font-size:10px;white-space:nowrap;">${v != null ? v.toFixed(1) : ''}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  document.getElementById('heatmapContainer').innerHTML = html;
```

```bash
git add docs/index.html
git commit -m "fix: heatmap sticky year column + month header, both axes scrollable, all years visible"
git push
```

**Stop here. Do not proceed to Message 5.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 5 OF 5 — Final Verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pull latest: `git pull origin main`

Run export to refresh JSON data:
```bash
python export_json.py
git add docs/data/
git diff --staged --quiet || git commit -m "data: refresh JSON after enhancement pass"
git push
```

Then open `https://yieldchaser.github.io/mcx-margins/` (wait ~2 min for Pages to deploy) and verify:

**Tooltips**
- [ ] Hover any card title → glassmorphism overlay appears center-screen with detailed text
- [ ] Remove mouse → overlay disappears after ~150ms

**KPI bar**
- [ ] Front Margin shows ▲/▼ change vs previous day in red/green
- [ ] Ann. Vol shows "Hist. P__" percentile rank
- [ ] Regime shows one of: 🟢 CALM / 🟡 NORMAL / 🟠 STRESSED / 🔴 CRISIS

**Overview**
- [ ] Snapshot table shows unique expiries only (no duplicate 26MAR2026 rows)
- [ ] Tender % cells highlighted red when > 0

**Analytics**
- [ ] 5-Day Rolling Avg chart shows blue spot line + yellow dashed average
- [ ] Percentile rank chart shows color-coded line, green/yellow/red by regime

**Seasonality**
- [ ] Heatmap shows all years 2010–2026 with vertical scroll
- [ ] All 12 months visible with horizontal scroll
- [ ] Year column stays pinned left when scrolling right
- [ ] Month header stays pinned top when scrolling down
- [ ] Native tooltip on each cell (e.g. "2025 JAN: 60.2%")

**Mobile** (Chrome DevTools → iPhone SE)
- [ ] Stats bar scrolls horizontally, no overflow
- [ ] Tabs scroll horizontally
- [ ] Charts render at reduced height without clipping
- [ ] Back-to-top button appears after scrolling down

**Keyboard**
- [ ] Arrow Left/Right switches tabs (when not in an input field)

If all checks pass, the enhancement pass is complete. No further action needed.
