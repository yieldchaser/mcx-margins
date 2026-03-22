# Agent Prompt: MCX Margin Intelligence Dashboard — Part-Wise Build

## CRITICAL RULE — READ BEFORE STARTING

**Build in exactly 6 numbered parts. Complete and commit each part before starting the next. Never try to write the full `index.html` in one shot — it will exceed your output limit and waste credits.**

Every part ends with: write the file(s), verify they work, `git add` + `git commit` + `git push`, then stop and report what was done.

---

## Context

The repo `yieldchaser/mcx-margins` already has:
- `data/margins.db` — SQLite database with MCX daily margin data for NATURALGAS and NATGASMINI, scraped from MCX CCL, going back to 2010
- `export_json.py` — already written, already run, already committed. All 10 JSON files are live in `docs/data/`
- `docs/data/meta.json`, `current.json`, `history_ng.json`, `history_ngm.json`, `seasonal_month.json`, `seasonal_year.json`, `seasonal_heatmap.json`, `dte_curve.json`, `forward_curve.json`, `volatility_correlation.json`

**Your only job is to build `docs/index.html` in 6 parts.**

---

## Design System (memorize this — use it in every part)

```css
/* CSS variables — define once in :root, reference everywhere */
--bg: #0d1117;
--surface: #161b22;
--surface2: #21262d;
--border: #30363d;
--text: #e6edf3;
--text-muted: #8b949e;
--accent: #388bfd;        /* NATURALGAS / primary */
--accent-orange: #fb8f44; /* NATGASMINI */
--accent-green: #3fb950;
--accent-red: #f85149;
--accent-yellow: #d29922;
--accent-purple: #a371f7; /* volatility */
```

**Font:** Inter from Google Fonts (weights 400, 500, 600, 700)
**Chart library:** Chart.js 4.4.0 from `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`
**Layout:** CSS Grid + Flexbox only. No Tailwind. No frameworks.
**One file only:** Everything — HTML structure, all CSS, all JS — goes into `docs/index.html`. No separate files.

---

## Data schema reminder (what the JSON files contain)

- **`meta.json`**: `{ last_updated, total_records, date_range: {from, to} }`
- **`current.json`**: `{ as_of, NATURALGAS: [{expiry, dte, initial_margin_pct, total_margin_pct, elm_pct, tender_margin_pct, additional_long_margin_pct, additional_short_margin_pct, delivery_margin_pct, daily_volatility, annualized_volatility}], NATGASMINI: [...] }`
- **`history_ng.json`** / **`history_ngm.json`**: `[{date, expiry, dte, initial_margin_pct, total_margin_pct, elm_pct, tender_margin_pct, daily_volatility, annualized_volatility}]` — one row per date, front-month contract only
- **`seasonal_month.json`**: `[{month, month_num, avg_initial_margin, avg_total_margin, count, min, max}]` — 12 rows (JAN–DEC)
- **`seasonal_year.json`**: `[{year, avg_initial_margin, avg_total_margin, count, min, max}]` — 2010–2026
- **`seasonal_heatmap.json`**: `{ years: [...], months: ["JAN"..."DEC"], data: {"2010": {"JAN": 11.2, ...}, ...} }`
- **`dte_curve.json`**: `[{dte_bin, dte_mid, avg_initial_margin, avg_tender_margin, count}]`
- **`forward_curve.json`**: `{ as_of, NATURALGAS: [{expiry, dte, initial_margin_pct, total_margin_pct, daily_volatility, annualized_volatility}], NATGASMINI: [...] }`
- **`volatility_correlation.json`**: `{ lags: [0,5,10,15,20,30], NATURALGAS: {"0": 0.93, "5": 0.86, ...}, timeseries: [{date, margin_pct, vol_daily, vol_annual}] }`

---

## PART 1 — Shell + Header + Tab Navigation

**What to build:** The skeleton of the entire SPA. No charts yet. No real data yet. Just the structure that every subsequent part plugs into.

### Exact file to create: `docs/index.html`

Write the complete file with:

**1a. `<head>` section:**
```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCX Natural Gas Margin Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<!-- Chart.js loaded here in Part 2 -->
<style>/* All CSS here */</style>
```

**1b. Full CSS (write all of it now — don't add later):**
- `:root` with all color variables above
- `* { box-sizing: border-box; margin: 0; padding: 0; }` reset
- `body`: background `var(--bg)`, color `var(--text)`, font Inter, min-height 100vh
- `.header`: sticky top, height 56px, dark surface, flexbox, border-bottom
  - `.header-left`: logo (small flame emoji 🔥 + "MCX Margins" in bold)
  - `.header-right`: last-updated badge + staleness dot (colored circle, JS will set color)
- `.stats-bar`: full-width row of 5 KPI cards below header, background `var(--surface)`, border-bottom. Each card: label on top (small muted text), value below (large bold). Cards: "Front Margin %", "ELM %", "Daily Vol", "Ann. Vol %", "Days to Expiry"
- `.tab-nav`: horizontal tab bar, border-bottom. 6 tabs: Overview | Term Structure | History | Seasonality | Analytics | Data Explorer. Active tab: white text + `var(--accent)` bottom border 2px. Inactive: muted text.
- `.tab-content`: each tab panel is `display:none` except active which is `display:block`. Padding 24px.
- `.card`: `background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px;`
- `.card-title`: font-size 13px, text-transform uppercase, letter-spacing 0.08em, color `var(--text-muted)`, margin-bottom 16px
- `.grid-2`: `display: grid; grid-template-columns: 1fr 1fr; gap: 16px;`
- `.grid-3`: three columns
- `.chart-container`: `position: relative; height: 320px;`
- `.badge-hike`: background `var(--accent-red)`, color white, border-radius 4px, padding 2px 8px, font-size 12px, font-weight 600
- `.badge-cut`: same but `var(--accent-green)`
- `.badge-safe`: background `#1c3a1e`, color `var(--accent-green)`, same shape
- `.badge-warn`: background `#3d2e00`, color `var(--accent-yellow)`
- `.badge-danger`: background `#3d1010`, color `var(--accent-red)`
- `.data-table`: full width, border-collapse collapse. `th`: background `var(--surface2)`, padding 10px 12px, text-align left, font-size 12px, text-transform uppercase, color `var(--text-muted)`. `td`: padding 10px 12px, font-size 13px, border-bottom 1px solid `var(--border)`. Alternating row: `tr:nth-child(even) td { background: var(--surface2); }`
- Responsive: `@media (max-width: 768px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } .tab-nav { overflow-x: auto; } }`

**1c. HTML body structure:**
```html
<body>
  <header class="header">
    <div class="header-left">🔥 <span>MCX Margins</span></div>
    <div class="header-right">
      <span class="staleness-dot" id="stalenessDot"></span>
      <span id="lastUpdated">Loading...</span>
    </div>
  </header>

  <div class="stats-bar">
    <div class="stat-card"><div class="stat-label">Front Margin %</div><div class="stat-value" id="kpiFrontMargin">—</div></div>
    <div class="stat-card"><div class="stat-label">ELM %</div><div class="stat-value" id="kpiElm">—</div></div>
    <div class="stat-card"><div class="stat-label">Daily Volatility</div><div class="stat-value" id="kpiDailyVol">—</div></div>
    <div class="stat-card"><div class="stat-label">Ann. Volatility</div><div class="stat-value" id="kpiAnnVol">—</div></div>
    <div class="stat-card"><div class="stat-label">Days to Expiry</div><div class="stat-value" id="kpiDTE">—</div></div>
  </div>

  <nav class="tab-nav">
    <button class="tab-btn active" data-tab="overview">Overview</button>
    <button class="tab-btn" data-tab="termstructure">Term Structure</button>
    <button class="tab-btn" data-tab="history">History</button>
    <button class="tab-btn" data-tab="seasonality">Seasonality</button>
    <button class="tab-btn" data-tab="analytics">Analytics</button>
    <button class="tab-btn" data-tab="explorer">Data Explorer</button>
  </nav>

  <main>
    <div id="tab-overview" class="tab-content active">
      <!-- Part 2 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading Overview...</p>
    </div>
    <div id="tab-termstructure" class="tab-content">
      <!-- Part 3 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading Term Structure...</p>
    </div>
    <div id="tab-history" class="tab-content">
      <!-- Part 4 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading History...</p>
    </div>
    <div id="tab-seasonality" class="tab-content">
      <!-- Part 5 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading Seasonality...</p>
    </div>
    <div id="tab-analytics" class="tab-content">
      <!-- Part 6 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading Analytics...</p>
    </div>
    <div id="tab-explorer" class="tab-content">
      <!-- Part 6 fills this -->
      <p style="color:var(--text-muted);padding:40px;text-align:center;">Loading Data Explorer...</p>
    </div>
  </main>

  <script>
  // ── PART 1 JS: Tab navigation + meta load + KPI population ──

  // 1. Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });

  // 2. Global data cache
  const DATA = {};
  async function loadJSON(name) {
    if (DATA[name]) return DATA[name];
    const r = await fetch(`data/${name}.json`);
    DATA[name] = await r.json();
    return DATA[name];
  }

  // 3. Staleness badge
  function setStaleness(dateStr) {
    const dot = document.getElementById('stalenessDot');
    const label = document.getElementById('lastUpdated');
    label.textContent = 'Updated: ' + dateStr;
    const days = (Date.now() - new Date(dateStr)) / 86400000;
    if (days < 1) { dot.style.background = '#3fb950'; dot.title = 'Live'; }
    else if (days < 5) { dot.style.background = '#d29922'; dot.title = 'Delayed'; }
    else { dot.style.background = '#f85149'; dot.title = 'Stale'; }
  }

  // 4. On page load — fetch meta + current
  (async () => {
    try {
      const [meta, current] = await Promise.all([loadJSON('meta'), loadJSON('current')]);
      setStaleness(meta.last_updated);

      // Populate KPIs from NATURALGAS front month (first item, lowest DTE > 0)
      const ng = current.NATURALGAS || [];
      const front = ng.find(c => c.dte >= 0) || ng[0];
      if (front) {
        document.getElementById('kpiFrontMargin').textContent = front.initial_margin_pct.toFixed(2) + '%';
        document.getElementById('kpiElm').textContent = front.elm_pct.toFixed(2) + '%';
        document.getElementById('kpiDailyVol').textContent = (front.daily_volatility * 100).toFixed(2) + '%';
        document.getElementById('kpiAnnVol').textContent = (front.annualized_volatility * 100).toFixed(1) + '%';
        document.getElementById('kpiDTE').textContent = front.dte + 'd';
      }
    } catch(e) {
      console.error('Failed to load meta/current:', e);
    }
  })();
  </script>
</body>
```

**Part 1 commit message:** `feat: dashboard shell — header, tabs, stats bar, CSS design system`

**Verify before committing:** Open `docs/index.html` in a browser (double-click or `python -m http.server 8080` from the `docs/` folder). You should see: dark page, header with 🔥, stats bar with 5 KPI cards, 6 clickable tabs that switch panels, "Loading..." placeholders in each tab.

---

## PART 2 — Overview Tab

**Start by:** Read Part 1's `docs/index.html` from disk. You will **replace** the `<div id="tab-overview">` placeholder content and **add** to the `<script>` block. Do not rewrite the file from scratch — use targeted edits.

**What to add to the Overview tab HTML** (replace the placeholder `<p>` inside `#tab-overview`):

```html
<!-- Section: Current Snapshot Table -->
<div class="card" style="margin-bottom:16px;">
  <div class="card-title">Current Margin Snapshot — NATURALGAS</div>
  <div style="overflow-x:auto;">
    <table class="data-table" id="snapshotTable">
      <thead><tr>
        <th>Contract</th><th>DTE</th><th>Initial %</th><th>ELM %</th>
        <th>Tender %</th><th>Total %</th><th>Add. Long %</th><th>Add. Short %</th><th>Ann. Vol %</th>
      </tr></thead>
      <tbody id="snapshotBody"></tbody>
    </table>
  </div>
</div>

<!-- Section: Mini forward curve chart -->
<div class="grid-2" style="margin-bottom:16px;">
  <div class="card">
    <div class="card-title">Forward Curve — Today</div>
    <div class="chart-container"><canvas id="miniForwardCurve"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Panic Spread Signals</div>
    <div style="overflow-x:auto;">
      <table class="data-table" id="panicTable">
        <thead><tr>
          <th>Expiry</th><th>Current %</th><th>Predicted</th><th>Signal</th>
        </tr></thead>
        <tbody id="panicBody"></tbody>
      </table>
    </div>
  </div>
</div>
```

**What to add to JS** (append inside the existing `<script>` tag, after the existing code):

```javascript
// ── PART 2 JS: Overview tab ──

Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = 'Inter';

const PANIC_COEFF_MARGIN = 0.886;
const PANIC_COEFF_VOL = 43.0;

function dteBadge(dte) {
  if (dte <= 30) return `<span class="badge-danger">${dte}d</span>`;
  if (dte <= 60) return `<span class="badge-warn">${dte}d</span>`;
  return `<span class="badge-safe">${dte}d</span>`;
}

async function renderOverview() {
  const [current, fwd] = await Promise.all([loadJSON('current'), loadJSON('forward_curve')]);

  // 1. Snapshot table — NATURALGAS
  const ng = current.NATURALGAS || [];
  const tbody = document.getElementById('snapshotBody');
  tbody.innerHTML = ng.map(c => `
    <tr>
      <td><strong>${c.expiry}</strong></td>
      <td>${dteBadge(c.dte)}</td>
      <td>${c.initial_margin_pct.toFixed(2)}%</td>
      <td>${c.elm_pct.toFixed(2)}%</td>
      <td>${c.tender_margin_pct.toFixed(2)}%</td>
      <td><strong>${c.total_margin_pct.toFixed(2)}%</strong></td>
      <td>${c.additional_long_margin_pct.toFixed(2)}%</td>
      <td>${c.additional_short_margin_pct.toFixed(2)}%</td>
      <td>${(c.annualized_volatility * 100).toFixed(1)}%</td>
    </tr>
  `).join('');

  // 2. Mini forward curve chart
  const fwdNG = fwd.NATURALGAS || [];
  const fwdNGM = fwd.NATGASMINI || [];
  new Chart(document.getElementById('miniForwardCurve'), {
    type: 'line',
    data: {
      labels: fwdNG.map(c => c.expiry),
      datasets: [
        {
          label: 'NATURALGAS',
          data: fwdNG.map(c => c.total_margin_pct),
          borderColor: '#388bfd', backgroundColor: 'rgba(56,139,253,0.08)',
          tension: 0.3, pointRadius: 3, fill: true
        },
        {
          label: 'NATGASMINI',
          data: (() => {
            // align NATGASMINI to same expiry labels via dte
            return fwdNG.map(ng => {
              const match = fwdNGM.find(m => m.expiry === ng.expiry);
              return match ? match.total_margin_pct : null;
            });
          })(),
          borderColor: '#fb8f44', backgroundColor: 'rgba(251,143,68,0.08)',
          tension: 0.3, pointRadius: 3, fill: true
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' }, tooltip: { mode: 'index' } },
      scales: {
        x: { ticks: { maxRotation: 45, font: { size: 10 } } },
        y: { title: { display: true, text: 'Total Margin %' } }
      }
    }
  });

  // 3. Panic spread signals table
  const panicBody = document.getElementById('panicBody');
  panicBody.innerHTML = fwdNG.slice(0, 8).map(c => {
    const predicted = PANIC_COEFF_MARGIN * c.total_margin_pct + PANIC_COEFF_VOL * c.daily_volatility;
    const diff = predicted - c.total_margin_pct;
    const signal = diff > 0
      ? `<span class="badge-hike">▲ HIKE</span>`
      : `<span class="badge-cut">▼ CUT</span>`;
    return `<tr>
      <td>${c.expiry}</td>
      <td>${c.total_margin_pct.toFixed(2)}%</td>
      <td>${predicted.toFixed(2)}%</td>
      <td>${signal}</td>
    </tr>`;
  }).join('');
}

// Load Chart.js then render overview
const chartScript = document.createElement('script');
chartScript.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
chartScript.onload = () => renderOverview();
document.head.appendChild(chartScript);
```

**Part 2 commit message:** `feat: dashboard Part 2 — Overview tab (snapshot table + forward curve + panic signals)`

**Verify:** Overview tab should show a dark table of ~59 NATURALGAS expiries with DTE color badges, a dual-line mini chart, and a panic signal table with HIKE/CUT badges.

---

## PART 3 — Term Structure Tab

**Start by:** Read current `docs/index.html` from disk. Edit only — replace `#tab-termstructure` placeholder and append to `<script>`.

**HTML to inject into `#tab-termstructure`:**

```html
<div class="card" style="margin-bottom:16px;">
  <div class="card-title">Forward Margin Curve — All Active Expiries</div>
  <div class="chart-container" style="height:380px;"><canvas id="chartFwdFull"></canvas></div>
</div>
<div class="grid-2">
  <div class="card">
    <div class="card-title">Volatility Term Structure</div>
    <div class="chart-container"><canvas id="chartVolCurve"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Margin Spread: NATURALGAS vs NATGASMINI</div>
    <div class="chart-container"><canvas id="chartSpread"></canvas></div>
  </div>
</div>
```

**JS to append:**

```javascript
// ── PART 3 JS: Term Structure tab ──

async function renderTermStructure() {
  const fwd = await loadJSON('forward_curve');
  const ng = fwd.NATURALGAS || [];
  const ngm = fwd.NATGASMINI || [];

  // Full forward curve
  new Chart(document.getElementById('chartFwdFull'), {
    type: 'line',
    data: {
      labels: ng.map(c => `${c.expiry}\n(${c.dte}d)`),
      datasets: [
        {
          label: 'NATURALGAS Total Margin %',
          data: ng.map(c => c.total_margin_pct),
          borderColor: '#388bfd', backgroundColor: 'rgba(56,139,253,0.1)',
          tension: 0.3, pointRadius: 4, fill: true
        },
        {
          label: 'NATGASMINI Total Margin %',
          data: ng.map(c => {
            const m = ngm.find(x => x.expiry === c.expiry);
            return m ? m.total_margin_pct : null;
          }),
          borderColor: '#fb8f44', backgroundColor: 'rgba(251,143,68,0.1)',
          tension: 0.3, pointRadius: 4, fill: true
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const c = ng[ctx.dataIndex];
              if (!c) return '';
              return `DTE: ${c.dte} | Vol: ${(c.daily_volatility * 100).toFixed(2)}%`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { font: { size: 10 }, maxRotation: 60 } },
        y: { title: { display: true, text: 'Total Margin %' } }
      }
    }
  });

  // Volatility term structure
  new Chart(document.getElementById('chartVolCurve'), {
    type: 'line',
    data: {
      labels: ng.map(c => c.expiry),
      datasets: [{
        label: 'Ann. Volatility %',
        data: ng.map(c => c.annualized_volatility ? (c.annualized_volatility * 100) : null),
        borderColor: '#a371f7', backgroundColor: 'rgba(163,113,247,0.1)',
        tension: 0.3, pointRadius: 3, fill: true
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { title: { display: true, text: 'Ann. Vol %' } }
      }
    }
  });

  // Spread chart (NG margin - NGM margin)
  const spreadLabels = ng.map(c => c.expiry);
  const spreadData = ng.map(c => {
    const m = ngm.find(x => x.expiry === c.expiry);
    return m ? parseFloat((c.total_margin_pct - m.total_margin_pct).toFixed(3)) : null;
  });
  new Chart(document.getElementById('chartSpread'), {
    type: 'bar',
    data: {
      labels: spreadLabels,
      datasets: [{
        label: 'NG − NGM Margin Spread %',
        data: spreadData,
        backgroundColor: spreadData.map(v => v >= 0 ? 'rgba(56,139,253,0.7)' : 'rgba(248,81,73,0.7)'),
        borderRadius: 3
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { title: { display: true, text: 'Spread (%)' } }
      }
    }
  });
}

// Lazy load on tab click
document.querySelector('[data-tab="termstructure"]').addEventListener('click', () => {
  if (!document.getElementById('chartFwdFull')._chartRendered) {
    renderTermStructure();
    document.getElementById('chartFwdFull')._chartRendered = true;
  }
}, { once: true });
```

**Part 3 commit message:** `feat: dashboard Part 3 — Term Structure tab (forward curve, vol curve, spread)`

---

## PART 4 — History Tab

**Start by:** Read current `docs/index.html` from disk. Edit only.

**HTML to inject into `#tab-history`:**

```html
<!-- Controls -->
<div class="card" style="margin-bottom:16px;padding:14px 20px;">
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <div>
      <label style="font-size:12px;color:var(--text-muted);margin-right:6px;">Symbol</label>
      <select id="histSymbol" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:13px;">
        <option value="ng">NATURALGAS</option>
        <option value="ngm">NATGASMINI</option>
      </select>
    </div>
    <div style="display:flex;gap:6px;">
      <button class="range-btn active-range" data-months="1">1M</button>
      <button class="range-btn" data-months="3">3M</button>
      <button class="range-btn" data-months="6">6M</button>
      <button class="range-btn" data-months="12">1Y</button>
      <button class="range-btn" data-months="36">3Y</button>
      <button class="range-btn" data-months="0">All</button>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:16px;">
  <div class="card-title">Initial Margin % Over Time (Front Month)</div>
  <div class="chart-container" style="height:340px;"><canvas id="chartHistMargin"></canvas></div>
</div>
<div class="grid-2">
  <div class="card">
    <div class="card-title">Daily Volatility Over Time</div>
    <div class="chart-container"><canvas id="chartHistVol"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Margin vs Volatility (Scatter)</div>
    <div class="chart-container"><canvas id="chartScatter"></canvas></div>
  </div>
</div>

<style>
  .range-btn {
    background: var(--surface2); color: var(--text-muted);
    border: 1px solid var(--border); border-radius: 4px;
    padding: 4px 10px; font-size: 12px; cursor: pointer; font-family: Inter, sans-serif;
  }
  .range-btn:hover, .active-range { background: var(--accent); color: white; border-color: var(--accent); }
</style>
```

**JS to append:**

```javascript
// ── PART 4 JS: History tab ──

let histChartMargin = null, histChartVol = null, histChartScatter = null;

function filterByMonths(data, months) {
  if (!months) return data;
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return data.filter(d => new Date(d.date) >= cutoff);
}

async function renderHistory(months) {
  const sym = document.getElementById('histSymbol').value;
  const raw = await loadJSON(sym === 'ng' ? 'history_ng' : 'history_ngm');
  const data = filterByMonths(raw, months);

  const labels = data.map(d => d.date);
  const margins = data.map(d => d.initial_margin_pct);
  const vols = data.map(d => d.daily_volatility != null ? (d.daily_volatility * 100) : null);

  const lineDefaults = { tension: 0.1, pointRadius: 0, borderWidth: 1.5 };

  if (histChartMargin) histChartMargin.destroy();
  histChartMargin = new Chart(document.getElementById('chartHistMargin'), {
    type: 'line',
    data: { labels, datasets: [{ label: 'Initial Margin %', data: margins, borderColor: '#388bfd', backgroundColor: 'rgba(56,139,253,0.1)', fill: true, ...lineDefaults }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { title: { display: true, text: 'Margin %' } } }
    }
  });

  if (histChartVol) histChartVol.destroy();
  histChartVol = new Chart(document.getElementById('chartHistVol'), {
    type: 'line',
    data: { labels, datasets: [{ label: 'Daily Volatility %', data: vols, borderColor: '#a371f7', backgroundColor: 'rgba(163,113,247,0.08)', fill: true, ...lineDefaults }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { title: { display: true, text: 'Daily Vol %' } } }
    }
  });

  // Scatter
  const scatterData = data
    .filter(d => d.daily_volatility != null && d.initial_margin_pct != null)
    .map(d => ({ x: parseFloat((d.daily_volatility * 100).toFixed(3)), y: d.initial_margin_pct, date: d.date }));

  if (histChartScatter) histChartScatter.destroy();
  histChartScatter = new Chart(document.getElementById('chartScatter'), {
    type: 'scatter',
    data: { datasets: [{ label: 'Margin vs Vol', data: scatterData, backgroundColor: 'rgba(56,139,253,0.4)', pointRadius: 3 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        tooltip: { callbacks: { label: ctx => `${ctx.raw.date}: Vol=${ctx.raw.x.toFixed(2)}%, Margin=${ctx.raw.y.toFixed(2)}%` } }
      },
      scales: {
        x: { title: { display: true, text: 'Daily Volatility %' } },
        y: { title: { display: true, text: 'Initial Margin %' } }
      }
    }
  });
}

// Range buttons
let currentHistMonths = 1;
document.querySelectorAll('.range-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active-range'));
    btn.classList.add('active-range');
    currentHistMonths = parseInt(btn.dataset.months);
    renderHistory(currentHistMonths);
  });
});
document.getElementById('histSymbol').addEventListener('change', () => renderHistory(currentHistMonths));

document.querySelector('[data-tab="history"]').addEventListener('click', () => {
  renderHistory(currentHistMonths);
}, { once: true });
```

**Part 4 commit message:** `feat: dashboard Part 4 — History tab (time series, volatility, scatter)`

---

## PART 5 — Seasonality Tab

**Start by:** Read current `docs/index.html` from disk. Edit only.

**HTML to inject into `#tab-seasonality`:**

```html
<div class="grid-2" style="margin-bottom:16px;">
  <div class="card">
    <div class="card-title">Average Margin by Month (NATURALGAS, All Years)</div>
    <div class="chart-container"><canvas id="chartSeasonMonth"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Average Margin by Year (2010–2026)</div>
    <div class="chart-container"><canvas id="chartSeasonYear"></canvas></div>
  </div>
</div>

<div class="card">
  <div class="card-title">Monthly Margin Heatmap — Year × Month (NATURALGAS)</div>
  <div id="heatmapContainer" style="overflow-x:auto;margin-top:8px;"></div>
  <div style="display:flex;gap:24px;margin-top:12px;font-size:12px;color:var(--text-muted);align-items:center;">
    <div style="display:flex;align-items:center;gap:6px;">
      <div style="width:80px;height:12px;background:linear-gradient(to right,#0d4a1a,#d29922,#7f1d1d);border-radius:2px;"></div>
      <span>Low → Mid → High Margin</span>
    </div>
    <span>Blank = no data for that month</span>
  </div>
</div>
```

**JS to append:**

```javascript
// ── PART 5 JS: Seasonality tab ──

function marginToColor(val, min, max) {
  if (val == null) return 'var(--surface2)';
  const t = Math.max(0, Math.min(1, (val - min) / (max - min)));
  // green (low) → yellow (mid) → red (high)
  if (t < 0.5) {
    const s = t * 2;
    const r = Math.round(13 + s * (210 - 13));
    const g = Math.round(74 + s * (161 - 74));
    const b = Math.round(26 + s * (22 - 26));
    return `rgb(${r},${g},${b})`;
  } else {
    const s = (t - 0.5) * 2;
    const r = Math.round(210 + s * (127 - 210));
    const g = Math.round(161 + s * (29 - 161));
    const b = Math.round(22 + s * (29 - 22));
    return `rgb(${r},${g},${b})`;
  }
}

async function renderSeasonality() {
  const [monthly, yearly, heatmap] = await Promise.all([
    loadJSON('seasonal_month'), loadJSON('seasonal_year'), loadJSON('seasonal_heatmap')
  ]);

  // Monthly bar chart
  const medianMargin = monthly.reduce((s,r)=>s+r.avg_initial_margin,0)/monthly.length;
  new Chart(document.getElementById('chartSeasonMonth'), {
    type: 'bar',
    data: {
      labels: monthly.map(r => r.month),
      datasets: [{
        label: 'Avg Initial Margin %',
        data: monthly.map(r => r.avg_initial_margin),
        backgroundColor: monthly.map(r => r.avg_initial_margin >= medianMargin ? 'rgba(248,81,73,0.7)' : 'rgba(63,185,80,0.7)'),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { afterLabel: ctx => `Range: ${monthly[ctx.dataIndex].min.toFixed(1)}% – ${monthly[ctx.dataIndex].max.toFixed(1)}%\nSamples: ${monthly[ctx.dataIndex].count}` } }
      },
      scales: { y: { title: { display: true, text: 'Avg Margin %' } } }
    }
  });

  // Yearly bar chart
  const medianYear = yearly.reduce((s,r)=>s+r.avg_initial_margin,0)/yearly.length;
  new Chart(document.getElementById('chartSeasonYear'), {
    type: 'bar',
    data: {
      labels: yearly.map(r => r.year),
      datasets: [{
        label: 'Avg Initial Margin %',
        data: yearly.map(r => r.avg_initial_margin),
        backgroundColor: yearly.map(r => r.avg_initial_margin >= medianYear ? 'rgba(248,81,73,0.7)' : 'rgba(63,185,80,0.7)'),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxRotation: 45, font: { size: 10 } } },
        y: { title: { display: true, text: 'Avg Margin %' } }
      }
    }
  });

  // Heatmap — CSS grid table
  const { years, months, data } = heatmap;
  let allVals = [];
  years.forEach(y => months.forEach(m => { const v = data[y]?.[m]; if (v != null) allVals.push(v); }));
  const minV = Math.min(...allVals), maxV = Math.max(...allVals);

  let html = `<table style="border-collapse:collapse;font-size:11px;width:100%;">`;
  html += `<tr><th style="padding:4px 8px;background:var(--surface2);position:sticky;left:0;z-index:1;"></th>`;
  months.forEach(m => { html += `<th style="padding:4px 6px;background:var(--surface2);text-align:center;font-size:10px;color:var(--text-muted);">${m}</th>`; });
  html += `</tr>`;
  years.forEach(y => {
    html += `<tr><td style="padding:4px 8px;background:var(--surface2);position:sticky;left:0;z-index:1;font-weight:600;color:var(--text-muted);font-size:10px;">${y}</td>`;
    months.forEach(m => {
      const v = data[y]?.[m];
      const bg = marginToColor(v, minV, maxV);
      const textColor = v == null ? 'transparent' : (v > (minV + maxV) / 2 ? '#fff' : '#0d1117');
      html += `<td style="padding:5px 4px;background:${bg};text-align:center;color:${textColor};font-weight:500;">${v != null ? v.toFixed(1) : ''}</td>`;
    });
    html += `</tr>`;
  });
  html += `</table>`;
  document.getElementById('heatmapContainer').innerHTML = html;
}

document.querySelector('[data-tab="seasonality"]').addEventListener('click', () => {
  renderSeasonality();
}, { once: true });
```

**Part 5 commit message:** `feat: dashboard Part 5 — Seasonality tab (monthly/yearly bars + heatmap)`

---

## PART 6 — Analytics Tab + Data Explorer Tab + Final Wiring

**Start by:** Read current `docs/index.html` from disk. Edit only. This is the last part — no more parts after this.

**HTML to inject into `#tab-analytics`:**

```html
<div class="grid-2" style="margin-bottom:16px;">
  <div class="card">
    <div class="card-title">DTE vs Margin — How Margin Changes as Expiry Approaches</div>
    <div class="chart-container"><canvas id="chartDTE"></canvas></div>
  </div>
  <div class="card">
    <div class="card-title">Lag Correlation: Margin % vs Daily Volatility</div>
    <div class="chart-container"><canvas id="chartLagCorr"></canvas></div>
    <p style="font-size:11px;color:var(--text-muted);margin-top:10px;">
      Correlation is strongest at lag=0 (simultaneous). Relationship weakens beyond 10 days — MCX responds to current vol, not future conditions.
    </p>
  </div>
</div>

<div class="card">
  <div class="card-title">Margin Prediction Model — Panic Spread (Full Forward Curve)</div>
  <div class="chart-container" style="height:340px;"><canvas id="chartPanicFull"></canvas></div>
  <p style="font-size:11px;color:var(--text-muted);margin-top:10px;">
    Predicted = 0.886 × Current Margin + 43.0 × Daily Vol. Red zone = predicted hike. Green zone = predicted cut.
  </p>
</div>
```

**HTML to inject into `#tab-explorer`:**

```html
<div class="card" style="margin-bottom:16px;padding:14px 20px;">
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <select id="expSymbol" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:13px;">
      <option value="ng">NATURALGAS</option>
      <option value="ngm">NATGASMINI</option>
    </select>
    <button id="exportCSV" style="background:var(--accent);color:white;border:none;border-radius:4px;padding:6px 14px;font-size:13px;cursor:pointer;font-family:Inter,sans-serif;">⬇ Download CSV</button>
    <span style="font-size:12px;color:var(--text-muted);" id="explorerCount"></span>
  </div>
</div>
<div class="card">
  <div style="overflow-x:auto;">
    <table class="data-table" id="explorerTable">
      <thead><tr>
        <th>Date</th><th>Expiry</th><th>DTE</th><th>Initial %</th><th>ELM %</th>
        <th>Tender %</th><th>Total %</th><th>Daily Vol</th><th>Ann. Vol %</th>
      </tr></thead>
      <tbody id="explorerBody"></tbody>
    </table>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;font-size:13px;">
    <button id="prevPage" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 12px;cursor:pointer;">← Prev</button>
    <span id="pageInfo" style="color:var(--text-muted);"></span>
    <button id="nextPage" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:4px;padding:4px 12px;cursor:pointer;">Next →</button>
  </div>
</div>
```

**JS to append:**

```javascript
// ── PART 6 JS: Analytics + Data Explorer ──

async function renderAnalytics() {
  const [dte, volCorr, fwd] = await Promise.all([
    loadJSON('dte_curve'), loadJSON('volatility_correlation'), loadJSON('forward_curve')
  ]);

  // DTE Curve
  new Chart(document.getElementById('chartDTE'), {
    type: 'line',
    data: {
      labels: dte.map(d => d.dte_bin),
      datasets: [
        { label: 'Avg Initial Margin %', data: dte.map(d => d.avg_initial_margin), borderColor: '#388bfd', backgroundColor: 'rgba(56,139,253,0.1)', tension: 0.3, pointRadius: 5, fill: true },
        { label: 'Avg Tender Margin %', data: dte.map(d => d.avg_tender_margin), borderColor: '#f85149', backgroundColor: 'rgba(248,81,73,0.1)', tension: 0.3, pointRadius: 5, fill: true }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: { callbacks: { afterLabel: ctx => `Samples: ${dte[ctx.dataIndex].count}` } }
      },
      scales: { y: { title: { display: true, text: 'Margin %' } } }
    }
  });

  // Lag Correlation
  const lags = volCorr.lags.map(String);
  const corrValues = lags.map(l => volCorr.NATURALGAS[l]);
  new Chart(document.getElementById('chartLagCorr'), {
    type: 'bar',
    data: {
      labels: lags.map(l => `Lag ${l}d`),
      datasets: [{
        label: 'Correlation Coefficient',
        data: corrValues,
        backgroundColor: corrValues.map(v => v >= 0.8 ? 'rgba(63,185,80,0.7)' : v >= 0.5 ? 'rgba(210,153,34,0.7)' : 'rgba(251,143,68,0.7)'),
        borderRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 1, title: { display: true, text: 'Correlation' } } }
    }
  });

  // Panic spread full chart
  const ng = fwd.NATURALGAS || [];
  const currentMargins = ng.map(c => c.total_margin_pct);
  const predicted = ng.map(c => parseFloat((0.886 * c.total_margin_pct + 43.0 * c.daily_volatility).toFixed(3)));
  new Chart(document.getElementById('chartPanicFull'), {
    type: 'line',
    data: {
      labels: ng.map(c => c.expiry),
      datasets: [
        { label: 'Current Margin %', data: currentMargins, borderColor: '#388bfd', pointRadius: 4, tension: 0.3 },
        { label: 'Predicted Tomorrow %', data: predicted, borderColor: '#fb8f44', borderDash: [6, 3], pointRadius: 4, tension: 0.3 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' }, tooltip: { mode: 'index' } },
      scales: {
        x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
        y: { title: { display: true, text: 'Margin %' } }
      }
    }
  });
}

// Data Explorer
let explorerData = [], explorerPage = 0;
const PAGE_SIZE = 50;

async function renderExplorer() {
  const sym = document.getElementById('expSymbol').value;
  const raw = await loadJSON(sym === 'ng' ? 'history_ng' : 'history_ngm');
  explorerData = [...raw].reverse(); // most recent first
  explorerPage = 0;
  renderExplorerPage();
}

function renderExplorerPage() {
  const start = explorerPage * PAGE_SIZE;
  const slice = explorerData.slice(start, start + PAGE_SIZE);
  document.getElementById('explorerCount').textContent = `${explorerData.length} rows total`;
  document.getElementById('pageInfo').textContent = `Page ${explorerPage + 1} of ${Math.ceil(explorerData.length / PAGE_SIZE)}`;
  document.getElementById('explorerBody').innerHTML = slice.map(d => `
    <tr>
      <td>${d.date}</td>
      <td>${d.expiry}</td>
      <td>${d.dte}</td>
      <td>${d.initial_margin_pct?.toFixed(2) ?? '—'}%</td>
      <td>${d.elm_pct?.toFixed(2) ?? '—'}%</td>
      <td>${d.tender_margin_pct?.toFixed(2) ?? '—'}%</td>
      <td>${d.total_margin_pct?.toFixed(2) ?? '—'}%</td>
      <td>${d.daily_volatility != null ? (d.daily_volatility * 100).toFixed(3) + '%' : '—'}</td>
      <td>${d.annualized_volatility != null ? (d.annualized_volatility * 100).toFixed(1) + '%' : '—'}</td>
    </tr>
  `).join('');
}

document.getElementById('prevPage')?.addEventListener('click', () => {
  if (explorerPage > 0) { explorerPage--; renderExplorerPage(); }
});
document.getElementById('nextPage')?.addEventListener('click', () => {
  if ((explorerPage + 1) * PAGE_SIZE < explorerData.length) { explorerPage++; renderExplorerPage(); }
});
document.getElementById('expSymbol')?.addEventListener('change', renderExplorer);

document.getElementById('exportCSV')?.addEventListener('click', () => {
  const headers = ['date','expiry','dte','initial_margin_pct','elm_pct','tender_margin_pct','total_margin_pct','daily_volatility','annualized_volatility'];
  const csv = [headers.join(','), ...explorerData.map(d => headers.map(h => d[h] ?? '').join(','))].join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv,' + encodeURIComponent(csv);
  a.download = `mcx_margins_${document.getElementById('expSymbol').value}.csv`;
  a.click();
});

document.querySelector('[data-tab="analytics"]').addEventListener('click', () => {
  renderAnalytics();
}, { once: true });

document.querySelector('[data-tab="explorer"]').addEventListener('click', () => {
  renderExplorer();
}, { once: true });
```

**Final step in Part 6 — update GitHub Actions workflow:**

Edit `.github/workflows/daily_margin.yml`. After the `python main.py $(date +%Y-%m-%d)` step, add:

```yaml
- name: Export dashboard JSON
  run: python export_json.py

- name: Commit DB + dashboard data
  run: |
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git config user.name "github-actions[bot]"
    git add data/ docs/data/
    git diff --staged --quiet || git commit -m "data: daily margin update $(date +%Y-%m-%d)"
    git push
```

Remove the old commit step if one exists (don't commit twice).

**Part 6 commit message:** `feat: dashboard Part 6 — Analytics, Data Explorer, GitHub Actions wiring`

---

## Final Checklist (run after Part 6)

```bash
# From repo root
python export_json.py                    # must print "All JSON files exported successfully"
cd docs && python -m http.server 8080    # open http://localhost:8080
```

Verify in browser:
- [ ] Header shows 🔥 + last updated date + colored staleness dot
- [ ] Stats bar shows real margin/vol numbers (not dashes)
- [ ] All 6 tabs clickable without page reload
- [ ] Overview: snapshot table + chart + panic signals populated
- [ ] Term Structure: 3 charts with real data
- [ ] History: controls work, charts change on range button click
- [ ] Seasonality: heatmap renders with color gradient (green → red)
- [ ] Analytics: DTE curve, lag correlation, panic model all rendered
- [ ] Data Explorer: table shows rows, pagination works, CSV downloads
- [ ] Zero JS console errors

**Then push everything:**
```bash
git add . && git commit -m "feat: complete MCX margin dashboard — 6-part build" && git push
```

**GitHub Pages:** In repo Settings > Pages, set Source = "Deploy from branch: main" and folder = `/docs`. The site will go live at `https://yieldchaser.github.io/mcx-margins/` within ~2 minutes.
