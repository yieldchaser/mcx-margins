# MCX Dashboard — Fix + 3 New Features
# Send ONE message at a time. Wait for "committed and pushed" before sending the next.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 1 OF 5 — Fix Tooltips (Root Cause + Proper Rewrite)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```bash
cd mcx-margins && git pull origin main
```

Open `docs/index.html`. The tooltip ? badge renders but clicking/hovering does nothing.

**Root cause:** The attachment code runs in a `setTimeout(500ms)` but tabs are lazy-loaded — card titles in tabs 2–6 don't exist in the DOM yet. The text-matching logic (`slice(0,12)`) also fails to match reliably.

**Fix: Replace text-matching with explicit `data-tooltip-key` attributes.**

**Edit 1 — Add `data-tooltip-key` to every card-title element in the HTML.**

Find every `<div class="card-title">` in the HTML body. Add a `data-tooltip-key` attribute matching the key in the TOOLTIPS object. Here is the complete mapping — find each card title text and add the attribute shown:

```
"CURRENT MARGIN SNAPSHOT"  → data-tooltip-key="Current Margin Snapshot"
"FORWARD CURVE — TODAY"    → data-tooltip-key="Forward Curve"
"PANIC SPREAD SIGNALS"     → data-tooltip-key="Panic Spread"
"FORWARD MARGIN CURVE"     → data-tooltip-key="Forward Margin Curve — All Active Expiries"
"VOLATILITY TERM STRUCTURE"→ data-tooltip-key="Volatility Term Structure"
"MARGIN SPREAD"            → data-tooltip-key="Margin Spread"
"INITIAL MARGIN % OVER TIME" → data-tooltip-key="Initial Margin % Over Time"
"DAILY VOLATILITY OVER TIME" → data-tooltip-key="Daily Volatility Over Time"
"MARGIN VS VOLATILITY"     → data-tooltip-key="Margin vs Volatility"
"AVERAGE MARGIN BY MONTH"  → data-tooltip-key="Average Margin by Month"
"AVERAGE MARGIN BY YEAR"   → data-tooltip-key="Average Margin by Year"
"MONTHLY MARGIN HEATMAP"   → data-tooltip-key="Monthly Margin Heatmap"
"DTE VS MARGIN"            → data-tooltip-key="DTE vs Margin"
"LAG CORRELATION"          → data-tooltip-key="Lag Correlation"
"MARGIN PREDICTION MODEL"  → data-tooltip-key="Margin Prediction Model"
"5-DAY ROLLING"            → data-tooltip-key="5-Day Rolling"
"HISTORICAL PERCENTILE"    → data-tooltip-key="Historical Percentile"
```

Example — before:
```html
<div class="card-title">Current Margin Snapshot — NaturalGas</div>
```
After:
```html
<div class="card-title has-tooltip" data-tooltip-key="Current Margin Snapshot">Current Margin Snapshot — NaturalGas</div>
```

Do this for every card-title that has a matching key above.

**Edit 2 — Replace the tooltip attachment JS entirely.**

Find the block starting with `// Attach tooltips to card titles after a short delay` and ending with the closing `}, 500);`. Delete that entire block and replace with:

```javascript
// ── Tooltip attachment — data-attribute driven, works across lazy tabs ──
function attachTooltips() {
  document.querySelectorAll('[data-tooltip-key]').forEach(el => {
    if (el._tooltipAttached) return; // don't double-attach
    el._tooltipAttached = true;
    const key = el.dataset.tooltipKey;
    el.addEventListener('mouseenter', () => showTooltip(key));
    el.addEventListener('mouseleave', hideTooltip);
    // Touch support for mobile
    el.addEventListener('touchstart', (e) => {
      e.preventDefault();
      showTooltip(key);
      setTimeout(hideTooltip, 3000);
    }, { passive: false });
  });
}

// Run on page load (catches Overview tab)
attachTooltips();

// Re-run whenever a tab is clicked (catches lazy-loaded tabs)
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    // Small delay to let tab content become visible
    setTimeout(attachTooltips, 100);
  });
});
```

**Edit 3 — Also fix the Panic Spread table deduplication.**

The panic spread table in Overview still shows multiple 26MAR2026 rows. Find the `panicBody` rendering inside `renderOverview()`. Add deduplication the same way as the snapshot table:

Find:
```javascript
panicBody.innerHTML = fwdNG.slice(0, 8).map(c => {
```

Replace with:
```javascript
const seenPanic = new Set();
const dedupedPanic = fwdNG.filter(c => {
  if (seenPanic.has(c.expiry)) return false;
  seenPanic.add(c.expiry);
  return true;
});
panicBody.innerHTML = dedupedPanic.slice(0, 8).map(c => {
```

```bash
git add docs/index.html
git commit -m "fix: tooltip attachment via data-attribute, works on all tabs + lazy load; panic table dedup"
git push
```

**Verify before moving on:** Open the live site. Click any tab, then hover a card title with the ? badge. The glassmorphism overlay must appear. If it does, proceed to Message 2.

**Stop here.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 2 OF 5 — NATGASMINI Toggle in Overview Snapshot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```bash
git pull origin main
```

Open `docs/index.html`. Make 2 edits.

**Edit 1 — Add symbol toggle buttons above the snapshot table in `#tab-overview`.**

Find the card containing `id="snapshotTable"`. Add this toggle bar inside the card, right after the opening `<div class="card"...>` and before the `<div class="card-title"`:

```html
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
  <div class="card-title has-tooltip" data-tooltip-key="Current Margin Snapshot" style="margin-bottom:0;">
    Current Margin Snapshot — <span id="snapshotSymbolLabel">NaturalGas</span>
  </div>
  <div style="display:flex;gap:6px;">
    <button class="snap-toggle active-snap" data-sym="NATURALGAS"
      style="background:var(--accent);color:white;border:none;border-radius:4px;padding:4px 12px;font-size:12px;cursor:pointer;font-family:Inter,sans-serif;font-weight:600;">
      NATURALGAS
    </button>
    <button class="snap-toggle" data-sym="NATGASMINI"
      style="background:var(--surface2);color:var(--text-muted);border:1px solid var(--border);border-radius:4px;padding:4px 12px;font-size:12px;cursor:pointer;font-family:Inter,sans-serif;">
      NATGASMINI
    </button>
  </div>
</div>
```

Remove the old standalone `<div class="card-title has-tooltip"...>Current Margin Snapshot...</div>` line since it's now inside the flex row above.

**Edit 2 — Update the snapshot rendering JS to support both symbols.**

Find `async function renderOverview()`. Replace the snapshot table population section (from `const ng = current.NATURALGAS` to the end of the `tbody.innerHTML = deduped.map(...)` block) with:

```javascript
  let activeSnapSym = 'NATURALGAS';

  function renderSnapshotTable(sym) {
    const rows = (current[sym] || []);
    document.getElementById('snapshotSymbolLabel').textContent =
      sym === 'NATURALGAS' ? 'NaturalGas' : 'NatGasMini';

    // Deduplicate
    const seen = new Set();
    const deduped = rows.filter(c => {
      if (seen.has(c.expiry)) return false;
      seen.add(c.expiry);
      return true;
    });

    document.getElementById('snapshotBody').innerHTML = deduped.map(c => `
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
  }

  // Initial render
  renderSnapshotTable(activeSnapSym);

  // Toggle buttons
  document.querySelectorAll('.snap-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.snap-toggle').forEach(b => {
        b.style.background = 'var(--surface2)';
        b.style.color = 'var(--text-muted)';
        b.style.border = '1px solid var(--border)';
      });
      btn.style.background = 'var(--accent)';
      btn.style.color = 'white';
      btn.style.border = 'none';
      activeSnapSym = btn.dataset.sym;
      renderSnapshotTable(activeSnapSym);
    });
  });
```

```bash
git add docs/index.html
git commit -m "feat: NATGASMINI toggle in Overview snapshot table"
git push
```

**Stop here.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 3 OF 5 — Henry Hub Price Overlay on History Chart
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```bash
git pull origin main
```

This adds Henry Hub front-month price (NGW00 from Yahoo Finance) overlaid on the History margin chart. Price fetched live from Yahoo Finance's public API — no API key needed.

Open `docs/index.html`. Make 2 edits.

**Edit 1 — Add price toggle checkbox to the History tab controls.**

Find the History tab controls bar (the card with `id="histSymbol"` select and range buttons). Add this checkbox after the range buttons div:

```html
<div style="display:flex;align-items:center;gap:6px;margin-left:8px;">
  <input type="checkbox" id="showPrice" style="accent-color:var(--accent-green);width:14px;height:14px;cursor:pointer;">
  <label for="showPrice" style="font-size:12px;color:var(--text-muted);cursor:pointer;">
    Overlay Henry Hub Price (NGW00)
  </label>
</div>
```

**Edit 2 — Update `renderHistory()` to fetch and overlay price data.**

Find `async function renderHistory(months)`. Replace the entire function with:

```javascript
async function renderHistory(months) {
  const sym = document.getElementById('histSymbol').value;
  const showPrice = document.getElementById('showPrice')?.checked;
  const raw = await loadJSON(sym === 'ng' ? 'history_ng' : 'history_ngm');
  const data = filterByMonths(raw, months);

  const labels = data.map(d => d.date);
  const margins = data.map(d => d.initial_margin_pct);
  const vols = data.map(d => d.daily_volatility != null ? (d.daily_volatility * 100) : null);

  const lineDefaults = { tension: 0.1, pointRadius: 0, borderWidth: 1.5 };

  // Fetch Henry Hub price if checkbox is on
  let priceDataset = null;
  if (showPrice) {
    try {
      // Yahoo Finance public endpoint — no key needed
      const period1 = Math.floor((months
        ? new Date(Date.now() - months * 30 * 86400000)
        : new Date('2010-01-01')).getTime() / 1000);
      const period2 = Math.floor(Date.now() / 1000);
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/NGW00.CME?period1=${period1}&period2=${period2}&interval=1d&events=history`;

      const resp = await fetch(url);
      const json = await resp.json();
      const result = json?.chart?.result?.[0];
      if (result) {
        const timestamps = result.timestamp;
        const closes = result.indicators.quote[0].close;

        // Build a date→price lookup
        const priceMap = {};
        timestamps.forEach((ts, i) => {
          const d = new Date(ts * 1000).toISOString().slice(0, 10);
          if (closes[i] != null) priceMap[d] = closes[i];
        });

        // Align to our margin dates
        const aligned = labels.map(d => priceMap[d] ?? null);

        priceDataset = {
          label: 'Henry Hub Price ($/MMBtu)',
          data: aligned,
          borderColor: '#3fb950',
          backgroundColor: 'transparent',
          tension: 0.2,
          pointRadius: 0,
          borderWidth: 1.5,
          borderDash: [4, 2],
          yAxisID: 'yPrice'
        };
      }
    } catch(e) {
      console.warn('Henry Hub fetch failed:', e);
    }
  }

  // Build datasets array
  const marginDatasets = [
    {
      label: 'Initial Margin %',
      data: margins,
      borderColor: '#388bfd',
      backgroundColor: 'rgba(56,139,253,0.1)',
      fill: true,
      yAxisID: 'y',
      ...lineDefaults
    }
  ];
  if (priceDataset) marginDatasets.push(priceDataset);

  // Scales
  const scales = {
    x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } },
    y: { title: { display: true, text: 'Margin %' }, position: 'left' }
  };
  if (priceDataset) {
    scales.yPrice = {
      title: { display: true, text: 'Henry Hub ($/MMBtu)' },
      position: 'right',
      grid: { drawOnChartArea: false }
    };
  }

  if (histChartMargin) histChartMargin.destroy();
  histChartMargin = new Chart(document.getElementById('chartHistMargin'), {
    type: 'line',
    data: { labels, datasets: marginDatasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: !!priceDataset, position: 'top' },
        tooltip: { mode: 'index', intersect: false }
      },
      scales
    }
  });

  // Volatility chart (unchanged)
  if (histChartVol) histChartVol.destroy();
  histChartVol = new Chart(document.getElementById('chartHistVol'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Daily Volatility %',
        data: vols,
        borderColor: '#a371f7',
        backgroundColor: 'rgba(163,113,247,0.08)',
        fill: true,
        ...lineDefaults
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: { x: { ticks: { maxTicksLimit: 12, font: { size: 10 } } }, y: { title: { display: true, text: 'Daily Vol %' } } }
    }
  });

  // Scatter (unchanged)
  const scatterData = data
    .filter(d => d.daily_volatility != null && d.initial_margin_pct != null)
    .map(d => ({ x: parseFloat((d.daily_volatility * 100).toFixed(3)), y: d.initial_margin_pct, date: d.date }));

  if (histChartScatter) histChartScatter.destroy();
  histChartScatter = new Chart(document.getElementById('chartScatter'), {
    type: 'scatter',
    data: { datasets: [{ label: 'Margin vs Vol', data: scatterData, backgroundColor: 'rgba(56,139,253,0.4)', pointRadius: 3 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: ctx => `${ctx.raw.date}: Vol=${ctx.raw.x.toFixed(2)}%, Margin=${ctx.raw.y.toFixed(2)}%` } } },
      scales: {
        x: { title: { display: true, text: 'Daily Volatility %' } },
        y: { title: { display: true, text: 'Initial Margin %' } }
      }
    }
  });
}

// Re-render when price checkbox changes
document.getElementById('showPrice')?.addEventListener('change', () => renderHistory(currentHistMonths));
```

Also add a tooltip entry for this feature. Find the TOOLTIPS object and add:

```javascript
  "Henry Hub": {
    title: "Henry Hub Price Overlay (NGW00)",
    body: `Overlays the <strong>Henry Hub natural gas front-month futures price</strong> (NGW00 from CME via Yahoo Finance) on the margin history chart.<br><br>
The green dashed line uses the <em>right Y-axis</em> ($/MMBtu). The blue margin line uses the left Y-axis (%).<br><br>
<strong>Why this matters:</strong> MCX NATURALGAS margin is heavily driven by Henry Hub price movements — when HH price spikes or crashes, MCX vol spikes and margins follow within 1–2 days. Viewing both on the same chart makes the cause-and-effect relationship immediately visible.<br><br>
<em>Data:</em> Fetched live from Yahoo Finance public API. Requires internet. May show slight gaps on Indian market holidays.`
  },
```

And add `data-tooltip-key="Henry Hub"` to the price checkbox label in the HTML:
```html
<label for="showPrice" class="has-tooltip" data-tooltip-key="Henry Hub" style="font-size:12px;color:var(--text-muted);cursor:pointer;">
  Overlay Henry Hub Price (NGW00)
</label>
```

```bash
git add docs/index.html
git commit -m "feat: Henry Hub price overlay on History chart, dual Y-axis, live from Yahoo Finance"
git push
```

**Stop here.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 4 OF 5 — Email Alert on Margin Change
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```bash
git pull origin main
```

This adds a GitHub Actions job that emails `upadhyayprateek574@gmail.com` whenever the front-month NATURALGAS margin changes by more than 2 percentage points vs the previous day.

Uses **Gmail SMTP via Python** — no third-party service needed. Requires one GitHub secret.

**Step 1 — Add the GitHub secret.**

Go to: `https://github.com/yieldchaser/mcx-margins/settings/secrets/actions`
Click "New repository secret":
- Name: `ALERT_EMAIL_PASSWORD`
- Value: A Gmail **App Password** (NOT your regular Gmail password)

To generate a Gmail App Password:
1. Go to myaccount.google.com → Security → 2-Step Verification (must be enabled)
2. Search "App passwords" → Create one → Select "Mail" + "Other (custom name)" → name it "MCX Alerts"
3. Copy the 16-character password → paste as the secret value

**Step 2 — Create `alert.py` in the repo root.**

```python
#!/usr/bin/env python3
"""Send email alert if front-month NATURALGAS margin changed by > THRESHOLD pct points."""

import sqlite3
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import date

THRESHOLD = 2.0  # percentage points
DB_PATH = Path("data/margins.db")
ALERT_TO = "upadhyayprateek574@gmail.com"
ALERT_FROM = "upadhyayprateek574@gmail.com"
SYMBOL = "NATURALGAS"


def get_front_month_margins():
    """Return (today_date, today_margin, prev_date, prev_margin) for front month."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get two most recent distinct dates
    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date DESC LIMIT 2",
        (SYMBOL,)
    )
    dates = [r[0] for r in cur.fetchall()]
    if len(dates) < 2:
        conn.close()
        return None

    results = []
    for d in dates:
        # Front month = smallest non-negative DTE
        cur.execute("""
            SELECT m.initial_margin_pct, m.expiry, m.total_margin_pct,
                   m.daily_volatility, m.annualized_volatility
            FROM margins m
            WHERE m.date = ? AND m.symbol = ?
            ORDER BY m.expiry ASC
            LIMIT 1
        """, (d, SYMBOL))
        row = cur.fetchone()
        if row:
            results.append((d, row[0], row[1], row[2], row[3], row[4]))

    conn.close()
    return results if len(results) == 2 else None


def send_email(subject, body_html):
    password = os.environ.get("ALERT_EMAIL_PASSWORD")
    if not password:
        print("No ALERT_EMAIL_PASSWORD set — skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ALERT_FROM
    msg["To"] = ALERT_TO
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_FROM, password)
            server.sendmail(ALERT_FROM, ALERT_TO, msg.as_string())
        print(f"Alert email sent: {subject}")
    except Exception as e:
        print(f"Email failed: {e}")
        sys.exit(1)


def main():
    data = get_front_month_margins()
    if not data:
        print("Not enough data to compare.")
        return

    today_date, today_margin, today_expiry, today_vol, today_ann_vol = data[0][0], data[0][1], data[0][2], data[0][3], data[0][4]
    prev_date, prev_margin = data[1][0], data[1][1]

    change = today_margin - prev_margin
    abs_change = abs(change)

    print(f"Today ({today_date}): {today_margin:.2f}% | Prev ({prev_date}): {prev_margin:.2f}% | Change: {change:+.2f}%")

    if abs_change < THRESHOLD:
        print(f"Change {abs_change:.2f}% below threshold {THRESHOLD}% — no alert.")
        return

    direction = "HIKED ▲" if change > 0 else "CUT ▼"
    color = "#f85149" if change > 0 else "#3fb950"
    action_advice = (
        "Consider pre-funding your margin account. MCX may continue hiking if volatility remains elevated."
        if change > 0 else
        "Capital efficiency improving. Favorable conditions for new or expanded positions."
    )

    subject = f"MCX Margin Alert: NATURALGAS {direction} {abs_change:.2f}pp — {today_date}"

    body_html = f"""
    <html><body style="font-family:Inter,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;">
      <div style="max-width:520px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
        <div style="background:{color};padding:16px 24px;">
          <h2 style="margin:0;color:white;font-size:18px;">🔥 MCX Margin Alert</h2>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">NATURALGAS Front Month · {today_date}</p>
        </div>
        <div style="padding:24px;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#8b949e;">Contract</td><td style="padding:8px 0;font-weight:600;">{today_expiry}</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Today's Margin</td><td style="padding:8px 0;font-weight:700;font-size:18px;color:{color};">{today_margin:.2f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Previous ({prev_date})</td><td style="padding:8px 0;">{prev_margin:.2f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Change</td><td style="padding:8px 0;font-weight:700;color:{color};">{change:+.2f} pp  {direction}</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Daily Vol</td><td style="padding:8px 0;">{(today_vol or 0)*100:.3f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Ann. Vol</td><td style="padding:8px 0;">{(today_ann_vol or 0)*100:.1f}%</td></tr>
          </table>
          <div style="margin-top:16px;padding:12px 16px;background:#21262d;border-radius:8px;font-size:13px;color:#8b949e;">
            💡 {action_advice}
          </div>
          <div style="margin-top:20px;text-align:center;">
            <a href="https://yieldchaser.github.io/mcx-margins/" style="display:inline-block;background:#388bfd;color:white;text-decoration:none;padding:10px 24px;border-radius:6px;font-weight:600;font-size:13px;">
              Open Dashboard →
            </a>
          </div>
        </div>
        <div style="padding:12px 24px;border-top:1px solid #30363d;font-size:11px;color:#8b949e;text-align:center;">
          MCX CCL data · Not financial advice · <a href="https://github.com/yieldchaser/mcx-margins" style="color:#388bfd;">GitHub</a>
        </div>
      </div>
    </body></html>
    """

    send_email(subject, body_html)


if __name__ == "__main__":
    main()
```

**Step 3 — Update `.github/workflows/daily_margin.yml`.**

Find the existing workflow file. After the `python export_json.py` step, add:

```yaml
      - name: Check margin change and send alert
        env:
          ALERT_EMAIL_PASSWORD: ${{ secrets.ALERT_EMAIL_PASSWORD }}
        run: python alert.py
```

The complete workflow step order should be:
1. `python main.py $(date +%Y-%m-%d)` — scrape today's margin
2. `python export_json.py` — export JSON
3. `python alert.py` — check change, send email if needed  ← NEW
4. `git add data/ docs/data/ && git commit && git push` — commit everything

```bash
git add alert.py .github/workflows/daily_margin.yml
git commit -m "feat: email alert when NATURALGAS margin changes >2pp — Gmail SMTP via GitHub Actions"
git push
```

**Stop here.**


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## MESSAGE 5 OF 5 — Final Verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```bash
git pull origin main
python export_json.py
git add docs/data/
git diff --staged --quiet || git commit -m "data: refresh JSON"
git push
```

Wait ~2 minutes for GitHub Pages to deploy, then open `https://yieldchaser.github.io/mcx-margins/`

**Tooltips**
- [ ] Overview tab: hover "Current Margin Snapshot" card title → glassmorphism overlay appears
- [ ] Click "Term Structure" tab → hover "Forward Margin Curve" → overlay appears
- [ ] Click "Seasonality" → hover "Monthly Margin Heatmap" → overlay appears
- [ ] Overlay disappears when mouse leaves the title
- [ ] Panic spread table shows unique expiries only (6 rows max, no 26MAR2026 duplicates)

**NATGASMINI Toggle**
- [ ] Overview snapshot shows "NATURALGAS" and "NATGASMINI" buttons
- [ ] Clicking NATGASMINI switches the table to NGM data
- [ ] Clicking NATURALGAS switches back

**Henry Hub Price**
- [ ] History tab shows "Overlay Henry Hub Price (NGW00)" checkbox
- [ ] Checking it redraws the margin chart with a green dashed price line on the right Y-axis
- [ ] Hovering the chart shows tooltip with both margin % and price values
- [ ] Unchecking it redraws without the price line

**Email Alert (manual test)**
- [ ] Temporarily change THRESHOLD in `alert.py` to `0.0` and run locally:
  ```bash
  ALERT_EMAIL_PASSWORD=your_app_password python alert.py
  ```
- [ ] An email should arrive at upadhyayprateek574@gmail.com within ~1 minute
- [ ] Email shows the contract, today's margin, change, and "Open Dashboard →" button
- [ ] Restore THRESHOLD to `2.0` and commit

**Done.** The system now:
- Scrapes MCX CCL every weekday at 8 PM IST
- Exports JSON and updates the live dashboard automatically
- Emails you when margin changes significantly
- Shows Henry Hub price context on the History chart
- Supports both NATURALGAS and NATGASMINI in the Overview snapshot
- Has working glassmorphism tooltips on every chart and section
