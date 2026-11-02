import re

path = 'docs/index.html'
with open(path, 'rb') as f:
    content = f.read().decode('utf-8')

# Ensure CRLF
newline = '\r\n' if '\r\n' in content else '\n'

# 1. Update CSS: .calc-chart-shell height from 280px to 330px
old_shell_css = """.calc-chart-shell {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  height: 280px;
  position: relative;
  transition: border-color 0.18s ease;
}"""

new_shell_css = """.calc-chart-shell {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  height: 330px;
  position: relative;
  transition: border-color 0.18s ease;
}
.calc-chart-matrix {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0 auto 10px auto;
  width: 100%;
  box-sizing: border-box;
}
.calc-chart-matrix__row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 3px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 2px;
  box-sizing: border-box;
}
.calc-chart-matrix .calc-chart-tab {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 5px 2px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--text-muted);
  border-radius: 4px;
  font-family: inherit;
  transition: background 0.18s ease, color 0.18s ease;
  white-space: nowrap;
}
.calc-chart-matrix .calc-chart-tab:hover {
  color: var(--text);
}
.calc-chart-matrix .calc-chart-tab[aria-pressed="true"] {
  background: var(--accent);
  color: #fff;
}
.calc-chart-matrix .calc-chart-tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}"""

# Normalize for replacement
if old_shell_css in content:
    content = content.replace(old_shell_css, new_shell_css)
    print("1. Replaced .calc-chart-shell CSS")
else:
    # Try normalizing newlines
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_shell_css.replace('\r\n', '\n')
    n_norm = new_shell_css.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("1. Replaced .calc-chart-shell CSS (normalized)")
    else:
        print("FAILED to replace .calc-chart-shell CSS")

# Add mobile media query for .calc-chart-matrix
old_media = """@media (max-width: 420px) {
  .calc-stat-grid { grid-template-columns: 1fr; }
  .calc-chart-tabs { font-size: 9px; }
  .calc-chart-tab { padding: 4px 6px; }
}"""

new_media = """@media (max-width: 480px) {
  .calc-chart-matrix__row {
    grid-template-columns: repeat(3, 1fr);
    gap: 3px;
    padding: 3px;
  }
  .calc-chart-matrix .calc-chart-tab {
    font-size: 9px;
    padding: 5px 2px;
  }
  .calc-chart-shell {
    height: 270px;
  }
}
@media (max-width: 420px) {
  .calc-stat-grid { grid-template-columns: 1fr; }
  .calc-chart-tabs { font-size: 9px; }
  .calc-chart-tab { padding: 4px 6px; }
}"""

if old_media in content:
    content = content.replace(old_media, new_media)
    print("2. Added mobile media query")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_media.replace('\r\n', '\n')
    n_norm = new_media.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("2. Added mobile media query (normalized)")
    else:
        print("FAILED to replace mobile media query")

# 2. HTML: Replace calc-chart-tabs with calc-chart-matrix
old_html = """              <div class="calc-chart-tabs" id="calcChartTabs" role="tablist" aria-label="Chart view">
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="equity" data-tooltip-key="calc-tab-equity" aria-pressed="true">Equity</button>
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="daily" data-tooltip-key="calc-tab-daily" aria-pressed="false">Daily</button>
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="drawdown" data-tooltip-key="calc-tab-drawdown" aria-pressed="false">Drawdown</button>
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="margin" data-tooltip-key="calc-tab-margin" aria-pressed="false">Util</button>
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="marginPct" data-tooltip-key="calc-tab-marginpct" aria-pressed="false">Margin</button>
                <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="shield" data-tooltip-key="calc-tab-shield" aria-pressed="false">Shield</button>
              </div>"""

new_html = """              <div class="calc-chart-matrix" id="calcChartTabs" role="tablist" aria-label="Chart view">
                <!-- Row 1: Performance & Returns -->
                <div class="calc-chart-matrix__row" role="group" aria-label="Performance & Returns">
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="equity" data-tooltip-key="calc-tab-equity" aria-pressed="true">Equity</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="daily" data-tooltip-key="calc-tab-daily" aria-pressed="false">Daily ₹</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="drawdown" data-tooltip-key="calc-tab-drawdown" aria-pressed="false">DD ₹</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="drawdownPct" data-tooltip-key="calc-tab-drawdownpct" aria-pressed="false">DD %</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="dailyRetPct" data-tooltip-key="calc-tab-dailyretpct" aria-pressed="false">Daily %</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="cumROI" data-tooltip-key="calc-tab-cumroi" aria-pressed="false">ROI %</button>
                </div>
                <!-- Row 2: Capital, Margin & Solvency Risk -->
                <div class="calc-chart-matrix__row" role="group" aria-label="Capital, Margin & Solvency Risk">
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="ledger" data-tooltip-key="calc-tab-ledger" aria-pressed="false">Ledger ₹</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="freeCash" data-tooltip-key="calc-tab-freecash" aria-pressed="false">Free Cash</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="marginReq" data-tooltip-key="calc-tab-marginreq" aria-pressed="false">Margin ₹</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="margin" data-tooltip-key="calc-tab-margin" aria-pressed="false">Util %</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="marginPct" data-tooltip-key="calc-tab-marginpct" aria-pressed="false">Rate %</button>
                  <button type="button" class="calc-chart-tab has-tooltip" role="tab" data-view="shield" data-tooltip-key="calc-tab-shield" aria-pressed="false">Shield %</button>
                </div>
              </div>"""

if old_html in content:
    content = content.replace(old_html, new_html)
    print("3. Replaced HTML tabs with calc-chart-matrix")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_html.replace('\r\n', '\n')
    n_norm = new_html.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("3. Replaced HTML tabs with calc-chart-matrix (normalized)")
    else:
        print("FAILED to replace HTML tabs")

# 3. JS Kickers & Event Listeners
old_js_tabs = """  // Chart view tabs (Equity / Daily P/L / Drawdown / Margin Util / Margin % / Free Cash)
  window._calcView = 'equity';
  const chartTabKickers = {
    equity: 'M2M Equity Curve',
    daily: 'Daily P/L',
    drawdown: 'Drawdown',
    margin: 'Margin Utilization %',
    marginPct: 'Contract Margin %',
    shield: 'Risk & Liquidation Shield %'
  };
  document.querySelectorAll('#calcChartTabs .calc-chart-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#calcChartTabs .calc-chart-tab').forEach(t => t.setAttribute('aria-pressed', 'false'));
      tab.setAttribute('aria-pressed', 'true');
      window._calcView = tab.dataset.view;
      const k = document.getElementById('calcChartKicker');
      if (k) k.textContent = chartTabKickers[window._calcView] || 'M2M Equity Curve';
      window.updateCalc();
    });
  });"""

new_js_tabs = """  // Chart view tabs (12-View Expanded Suite)
  window._calcView = 'equity';
  const chartTabKickers = {
    equity: 'M2M Cumulative Equity Curve (₹)',
    daily: 'Daily Mark-to-Market P/L (₹)',
    drawdown: 'Peak-to-Trough Cash Drawdown (₹)',
    drawdownPct: 'Portfolio Drawdown Percentage (%)',
    dailyRetPct: 'Daily Return on Capital (%)',
    cumROI: 'Cumulative Return on Initial Capital (%)',
    ledger: 'Account Ledger Capital Balance (₹)',
    freeCash: 'Unencumbered Free Cash Cushion (₹)',
    marginReq: 'Exchange Required Overnight Margin (₹)',
    margin: 'Margin Utilization Ratio (%)',
    marginPct: 'MCX Contract Total Margin Rate (%)',
    shield: 'Risk & Liquidation Shield Cushion (%)'
  };
  document.querySelectorAll('#calcChartTabs .calc-chart-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#calcChartTabs .calc-chart-tab').forEach(t => t.setAttribute('aria-pressed', 'false'));
      tab.setAttribute('aria-pressed', 'true');
      window._calcView = tab.dataset.view;
      const k = document.getElementById('calcChartKicker');
      if (k) k.textContent = chartTabKickers[window._calcView] || 'M2M Cumulative Equity Curve (₹)';
      window.updateCalc();
    });
  });"""

if old_js_tabs in content:
    content = content.replace(old_js_tabs, new_js_tabs)
    print("4. Replaced JS Kickers & Event Listeners")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_js_tabs.replace('\r\n', '\n')
    n_norm = new_js_tabs.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("4. Replaced JS Kickers & Event Listeners (normalized)")
    else:
        print("FAILED to replace JS Kickers")

# Reset button kicker text
old_reset = """    window._calcView = 'equity';
    const k = document.getElementById('calcChartKicker');
    if (k) k.textContent = 'M2M Equity Curve';"""

new_reset = """    window._calcView = 'equity';
    const k = document.getElementById('calcChartKicker');
    if (k) k.textContent = 'M2M Cumulative Equity Curve (₹)';"""

if old_reset in content:
    content = content.replace(old_reset, new_reset)
    print("5. Replaced Reset button kicker text")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_reset.replace('\r\n', '\n')
    n_norm = new_reset.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("5. Replaced Reset button kicker text (normalized)")
    else:
        print("FAILED to replace Reset button kicker text")

# 4. Calculation Loop in updateCalc()
old_calc_loop = """  // ── Walk window: cumulative P/L, daily P/L, drawdown, margin path, margin call detection ──
  // isM2M: real-world mode — daily M2M settlement adjusts the available ledger balance each day
  const isM2M = !!document.getElementById('calcM2MEnabled')?.checked;
  const cumPL = [], dailyPL = [], drawdownPath = [], marginPath = [], marginUtilPath = [], marginPctPath = [], shieldPath = [], labels = [];
  let prevPL = 0, runningHigh = 0, maxDD = 0, peakMargin = 0;
  let marginCallDate = null, marginCallReq = 0, marginCallAvail = 0;
  let minShield = Infinity, minShieldDate = '';

  windowDays.forEach(date => {
    const pRow = pByDate[date] || findNearest(date, pByDate);
    const mRow = mByDate[date] || findNearest(date, mByDate);
    const p = pRow?.close;
    const mPct = mRow?.total_margin_pct;
    if (p == null) return;

    const pl = _calcDir === 'long' ? (p - entryPrice) * lots * lotSize : (entryPrice - p) * lots * lotSize;
    const dailyChange = pl - prevPL;
    cumPL.push(pl);
    dailyPL.push(dailyChange);
    labels.push(date);
    prevPL = pl;

    if (pl > runningHigh) runningHigh = pl;
    const dd = runningHigh - pl;
    if (dd > maxDD) maxDD = dd;
    drawdownPath.push(-dd);

    marginPctPath.push(mPct != null ? mPct : null);

    let dailyShield = null;
    if (lots > 0 && p != null && mPct != null) {
      const positionSize_t = lots * lotSize * p;
      const availableCapital_t = isM2M ? Math.max(0, capital + pl) : capital;
      const internalMarginPct_t = positionSize_t > 0 ? (availableCapital_t / positionSize_t) * 100 : 0;
      dailyShield = internalMarginPct_t - mPct;
      if (dailyShield < minShield) {
        minShield = dailyShield;
        minShieldDate = date;
      }
    }
    shieldPath.push(dailyShield);

    if (mPct != null && lots > 0) {
      const curMargin = ((p * lotSize * mPct * lots) / 100) * spreadMarginFactor;
      // Dynamic M2M: available capital = initial capital +/- cumulative P/L settled to date.
      // Math.max(0,...) clamps to zero — a real broker would have squared off before a negative balance.
      const availableCapital = isM2M ? Math.max(0, capital + pl) : capital;
      marginPath.push(curMargin);
      const util = availableCapital > 0 ? (curMargin / availableCapital) * 100 : 999;
      marginUtilPath.push(util);
      if (curMargin > peakMargin) peakMargin = curMargin;
      if (!marginCallDate && curMargin > availableCapital) {
        marginCallDate = date;
        marginCallReq = curMargin;
        marginCallAvail = availableCapital; // snapshot live ledger balance at breach
      }
    } else {
      marginPath.push(null);
      marginUtilPath.push(null);
    }
  });"""

new_calc_loop = """  // ── Walk window: cumulative P/L, daily P/L, drawdown, margin path, margin call detection ──
  // isM2M: real-world mode — daily M2M settlement adjusts the available ledger balance each day
  const isM2M = !!document.getElementById('calcM2MEnabled')?.checked;
  const cumPL = [], dailyPL = [], drawdownPath = [], drawdownPctPath = [], dailyRetPctPath = [], cumROIPath = [];
  const capitalPath = [], freeCashPath = [], reqMarginPath = [], marginPath = [], marginUtilPath = [], marginPctPath = [], shieldPath = [], labels = [];
  let prevPL = 0, runningHigh = 0, maxDD = 0, peakMargin = 0;
  let prevCapital = capital;
  let marginCallDate = null, marginCallReq = 0, marginCallAvail = 0;
  let minShield = Infinity, minShieldDate = '';

  windowDays.forEach((date, idx) => {
    const pRow = pByDate[date] || findNearest(date, pByDate);
    const mRow = mByDate[date] || findNearest(date, mByDate);
    const p = pRow?.close;
    const mPct = mRow?.total_margin_pct;
    if (p == null) return;

    const pl = _calcDir === 'long' ? (p - entryPrice) * lots * lotSize : (entryPrice - p) * lots * lotSize;
    const dailyChange = pl - prevPL;
    cumPL.push(pl);
    dailyPL.push(dailyChange);
    labels.push(date);
    prevPL = pl;

    if (pl > runningHigh) runningHigh = pl;
    const dd = runningHigh - pl;
    if (dd > maxDD) maxDD = dd;
    drawdownPath.push(-dd);

    // Peak-to-Trough Drawdown % of Peak Portfolio
    const peakPortfolio_t = Math.max(capital, capital + runningHigh);
    const ddPct_t = peakPortfolio_t > 0 ? -((dd / peakPortfolio_t) * 100) : 0;
    drawdownPctPath.push(ddPct_t);

    // Daily Return % on Prior Day Capital (t=0 guarded at 0%)
    const dailyRetPct = (idx === 0 || prevCapital <= 0) ? 0 : (dailyChange / prevCapital) * 100;
    dailyRetPctPath.push(dailyRetPct);

    // Cumulative ROI % on Initial Capital
    const cumROI = capital > 0 ? (pl / capital) * 100 : 0;
    cumROIPath.push(cumROI);

    // Dynamic Ledger Capital
    const capVal = isM2M ? Math.max(0, capital + pl) : (capital + pl);
    capitalPath.push(capVal);
    prevCapital = capVal;

    marginPctPath.push(mPct != null ? mPct : null);

    let dailyShield = null;
    if (lots > 0 && p != null && mPct != null) {
      const positionSize_t = lots * lotSize * p;
      const internalMarginPct_t = positionSize_t > 0 ? (capVal / positionSize_t) * 100 : 0;
      dailyShield = internalMarginPct_t - mPct;
      if (dailyShield < minShield) {
        minShield = dailyShield;
        minShieldDate = date;
      }
    }
    shieldPath.push(dailyShield);

    if (mPct != null && lots > 0) {
      const curMargin = ((p * lotSize * mPct * lots) / 100) * spreadMarginFactor;
      marginPath.push(curMargin);
      reqMarginPath.push(curMargin);
      freeCashPath.push(capVal - curMargin);

      const util = capVal > 0 ? (curMargin / capVal) * 100 : 999;
      marginUtilPath.push(util);
      if (curMargin > peakMargin) peakMargin = curMargin;
      if (!marginCallDate && curMargin > capVal) {
        marginCallDate = date;
        marginCallReq = curMargin;
        marginCallAvail = capVal; // snapshot live ledger balance at breach
      }
    } else {
      marginPath.push(null);
      reqMarginPath.push(0);
      freeCashPath.push(capVal);
      marginUtilPath.push(null);
    }
  });"""

if old_calc_loop in content:
    content = content.replace(old_calc_loop, new_calc_loop)
    print("6. Replaced calculation loop in updateCalc()")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_calc_loop.replace('\r\n', '\n')
    n_norm = new_calc_loop.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("6. Replaced calculation loop in updateCalc() (normalized)")
    else:
        print("FAILED to replace calculation loop")

# 5. Chart Dispatcher
old_dispatcher = """  let series, color, gradientTop, label, yFmt;
  const moneyFmt = (v) => {
    if (v == null) return '';
    if (Math.abs(v) >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (Math.abs(v) >= 1000) return (v / 1000).toFixed(0) + 'K';
    return Math.round(v).toString();
  };
  const pctFmt = (v) => v == null ? '' : v.toFixed(1) + '%';

  if (view === 'daily') {
    series = dailyPL;
    color = totalPL >= 0 ? '#3fb950' : '#f85149';
    gradientTop = _hexRgba(color, 0.30);
    label = 'Daily P/L';
    yFmt = moneyFmt;
  } else if (view === 'drawdown') {
    series = drawdownPath;
    color = '#f85149';
    gradientTop = _hexRgba('#f85149', 0.32);
    label = 'Drawdown';
    yFmt = moneyFmt;
  } else if (view === 'margin') {
    series = marginUtilPath;
    color = '#fb8f44';
    gradientTop = _hexRgba('#fb8f44', 0.32);
    label = 'Margin Utilization %';
    yFmt = pctFmt;
  } else if (view === 'marginPct') {
    series = marginPctPath;
    color = '#a371f7'; // Standardized Purple for Total Margin %
    gradientTop = _hexRgba('#a371f7', 0.32);
    label = 'Total Margin %';
    yFmt = pctFmt;
  } else if (view === 'shield') {
    series = shieldPath;
    color = '#58a6ff'; // Light Blue/Cyan accent
    gradientTop = _hexRgba('#58a6ff', 0.28);
    label = 'Risk & Liquidation Shield %';
    yFmt = pctFmt;
  } else {
    series = cumPL;
    color = totalPL >= 0 ? '#3fb950' : '#f85149';
    gradientTop = _hexRgba(color, 0.28);
    label = 'M2M Equity';
    yFmt = moneyFmt;
  }

  const cssText = (typeof getComputedStyle === 'function')
    ? (getComputedStyle(document.body).getPropertyValue('--text') || '#e6edf3').trim()
    : '#e6edf3';
  const cssMuted = (typeof getComputedStyle === 'function')
    ? (getComputedStyle(document.body).getPropertyValue('--text-muted') || '#8b949e').trim()
    : '#8b949e';

  const grad = ctx.createLinearGradient(0, 0, 0, 280);
  grad.addColorStop(0, gradientTop);
  grad.addColorStop(1, 'transparent');

  const mcPlugin = (marginCallDate && (view === 'equity' || view === 'margin' || view === 'marginPct' || view === 'shield')) ? {"""

new_dispatcher = """  let series, color, gradientTop, label, yFmt;
  const moneyFmt = (v) => {
    if (v == null || !Number.isFinite(v)) return '';
    if (Math.abs(v) >= 100000) return (v / 100000).toFixed(1) + 'L';
    if (Math.abs(v) >= 1000) return (v / 1000).toFixed(0) + 'K';
    return Math.round(v).toString();
  };
  const pctFmt = (v) => (v == null || !Number.isFinite(v)) ? '' : v.toFixed(1) + '%';

  const isPct = ['drawdownPct', 'dailyRetPct', 'cumROI', 'margin', 'marginPct', 'shield'].includes(view);
  yFmt = isPct ? pctFmt : moneyFmt;

  switch (view) {
    // ── Row 1: Performance & Returns ──
    case 'daily':
      series = dailyPL;
      color = totalPL >= 0 ? '#3fb950' : '#f85149';
      gradientTop = _hexRgba(color, 0.30);
      label = 'Daily P/L';
      break;
    case 'drawdown':
      series = drawdownPath;
      color = '#f85149';
      gradientTop = _hexRgba('#f85149', 0.32);
      label = 'Drawdown ₹';
      break;
    case 'drawdownPct':
      series = drawdownPctPath;
      color = '#f85149';
      gradientTop = _hexRgba('#f85149', 0.32);
      label = 'Drawdown %';
      break;
    case 'dailyRetPct':
      series = dailyRetPctPath;
      color = totalPL >= 0 ? '#3fb950' : '#f85149';
      gradientTop = _hexRgba(color, 0.25);
      label = 'Daily Return %';
      break;
    case 'cumROI':
      series = cumROIPath;
      color = totalPL >= 0 ? '#3fb950' : '#f85149';
      gradientTop = _hexRgba(color, 0.28);
      label = 'Cumulative ROI %';
      break;

    // ── Row 2: Capital, Margin & Solvency Risk ──
    case 'ledger':
      series = capitalPath;
      color = '#58a6ff';
      gradientTop = _hexRgba('#58a6ff', 0.28);
      label = 'Ledger Balance';
      break;
    case 'freeCash':
      series = freeCashPath;
      const minFreeCash = freeCashPath.length ? Math.min(...freeCashPath.filter(Number.isFinite)) : 0;
      color = minFreeCash < 0 ? '#f85149' : '#2ea043';
      gradientTop = _hexRgba(color, 0.28);
      label = 'Free Cash Cushion';
      break;
    case 'marginReq':
      series = reqMarginPath;
      color = '#db61a2';
      gradientTop = _hexRgba('#db61a2', 0.28);
      label = 'Required Margin ₹';
      break;
    case 'margin':
      series = marginUtilPath;
      color = '#fb8f44';
      gradientTop = _hexRgba('#fb8f44', 0.32);
      label = 'Margin Utilization %';
      break;
    case 'marginPct':
      series = marginPctPath;
      color = '#a371f7';
      gradientTop = _hexRgba('#a371f7', 0.32);
      label = 'Total Margin %';
      break;
    case 'shield':
      series = shieldPath;
      color = '#58a6ff';
      gradientTop = _hexRgba('#58a6ff', 0.28);
      label = 'Risk & Liquidation Shield %';
      break;

    case 'equity':
    default:
      series = cumPL;
      color = totalPL >= 0 ? '#3fb950' : '#f85149';
      gradientTop = _hexRgba(color, 0.28);
      label = 'M2M Equity';
      break;
  }

  const cssText = (typeof getComputedStyle === 'function')
    ? (getComputedStyle(document.body).getPropertyValue('--text') || '#e6edf3').trim()
    : '#e6edf3';
  const cssMuted = (typeof getComputedStyle === 'function')
    ? (getComputedStyle(document.body).getPropertyValue('--text-muted') || '#8b949e').trim()
    : '#8b949e';

  const grad = ctx.createLinearGradient(0, 0, 0, 330);
  grad.addColorStop(0, gradientTop);
  grad.addColorStop(1, 'transparent');

  const mcViews = ['equity', 'ledger', 'freeCash', 'marginReq', 'margin', 'marginPct', 'shield'];
  const mcPlugin = (marginCallDate && mcViews.includes(view)) ? {"""

if old_dispatcher in content:
    content = content.replace(old_dispatcher, new_dispatcher)
    print("7. Replaced Chart Dispatcher")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_dispatcher.replace('\r\n', '\n')
    n_norm = new_dispatcher.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("7. Replaced Chart Dispatcher (normalized)")
    else:
        print("FAILED to replace Chart Dispatcher")

# Tooltip label in chart options
old_tt_label = """            label: (item) => `${label}: ${(view === 'margin' || view === 'marginPct' || view === 'shield') ? pctFmt(item.raw) : '₹' + fmtNum(item.raw, 0)}`,"""

new_tt_label = """            label: (item) => {
              const val = item.raw;
              if (val == null || !Number.isFinite(val)) return `${label}: —`;
              if (isPct) {
                const sign = (view === 'dailyRetPct' || view === 'cumROI') && val > 0 ? '+' : '';
                return `${label}: ${sign}${pctFmt(val)}`;
              }
              return `${label}: ₹${fmtNum(val, 0)}`;
            },"""

if old_tt_label in content:
    content = content.replace(old_tt_label, new_tt_label)
    print("8. Replaced Tooltip label in chart options")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_tt_label.replace('\r\n', '\n')
    n_norm = new_tt_label.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("8. Replaced Tooltip label in chart options (normalized)")
    else:
        print("FAILED to replace Tooltip label in chart options")

# 6. Global Tooltip Dictionary
old_tooltips = """  "calc-tab-equity": {
    title: "M2M Equity",
    body: `Shows your net ledger capital over the backtest window (Initial Capital ± cumulative Mark-to-Market P/L).`
  },
  "calc-tab-daily": {
    title: "Daily P/L",
    body: `Shows the single-day P/L fluctuations (daily changes in mark-to-market).`
  },
  "calc-tab-drawdown": {
    title: "Drawdown",
    body: `Shows the peak-to-trough paper loss from the highest ledger capital reached during the trade.`
  },
  "calc-tab-margin": {
    title: "Margin Utilization",
    body: `Shows the percentage of your ledger capital locked up in exchange required margin on each day (Required Margin ÷ Ledger Capital × 100).`
  },
  "calc-tab-marginpct": {
    title: "Contract Margin %",
    body: `Shows the historical daily exchange total margin rate percentage required for this contract.`
  },
  "calc-tab-shield": {
    title: "Risk & Liquidation Shield %",
    body: `Shows your dynamic percentage safety cushion on each day (Internal Margin % − Exchange Required Margin %).<br><br>• <strong>What 0% means:</strong> Your free buffer is exhausted and ledger capital equals the exchange required margin. It does <em>not</em> mean your account is at ₹0.<br>• <strong>Liquidation:</strong> At 0% or below, the broker's RMS auto-squares off the position to protect your remaining margin capital from deeper losses.<br>• <strong>Buffer:</strong> Indicates how much adverse % price move you can endure before forced exit.`
  },"""

new_tooltips = """  "calc-tab-equity": {
    title: "M2M Cumulative Equity Curve (₹)",
    body: `Shows your net cumulative Mark-to-Market (M2M) trading profit or loss over time settled at official MCX daily closing prices.`
  },
  "calc-tab-daily": {
    title: "Daily Mark-to-Market P/L (₹)",
    body: `Shows the discrete single-session rupee profit or loss credited to or debited from your ledger at the end of each MCX trading session.`
  },
  "calc-tab-drawdown": {
    title: "Peak-to-Trough Cash Drawdown (₹)",
    body: `Shows the rupee retracement from your portfolio's highest historical high-water mark. Highlights the worst interim equity dip endured during the position's lifecycle.`
  },
  "calc-tab-drawdownpct": {
    title: "Portfolio Drawdown Percentage (%)",
    body: `Measures the percentage paper loss from the trade's peak portfolio capital: <code>−(Peak Rupee − Current Rupee) ÷ Peak Rupee × 100%</code>. Crucial for assessing tail-risk and recovery hurdles.`
  },
  "calc-tab-dailyretpct": {
    title: "Daily Return on Capital (%)",
    body: `Calculates each day's percentage return relative to the prior session's ending ledger capital: <code>Daily P/L ÷ Previous Day's Capital × 100%</code>. Reveals volatility clustering and outlier session returns.`
  },
  "calc-tab-cumroi": {
    title: "Cumulative Return on Initial Capital (%)",
    body: `Shows the total percentage growth or contraction of your initial cash outlay over the backtest horizon: <code>Cumulative P/L ÷ Starting Capital × 100%</code>.`
  },
  "calc-tab-ledger": {
    title: "Account Ledger Capital Balance (₹)",
    body: `Tracks your live broker cash ledger balance after absorbing daily M2M cash flows. Clamped at ₹0 in M2M mode to reflect realistic broker liquidation prior to balance deficit.`
  },
  "calc-tab-freecash": {
    title: "Unencumbered Free Cash Cushion (₹)",
    body: `Your liquid cash reserve remaining after meeting exchange margin requirements: <code>Ledger Capital − Required Margin</code>. Negative values indicate an immediate margin shortfall requiring capital infusion.`
  },
  "calc-tab-marginreq": {
    title: "Exchange Required Overnight Margin (₹)",
    body: `Total rupee collateral mandated by MCX Clearing Corporation (MCXCCL) to hold open lots overnight: <code>Contract Notional × Total Margin % × Spread Factor</code>.`
  },
  "calc-tab-margin": {
    title: "Margin Utilization Ratio (%)",
    body: `The percentage of your ledger capital tied up in required margin: <code>Required Margin ÷ Ledger Capital × 100%</code>. Ratios exceeding 80% indicate severe capital strain; 100% triggers RMS auto-squareoff.`
  },
  "calc-tab-marginpct": {
    title: "MCX Contract Total Margin Rate (%)",
    body: `The exchange-stipulated minimum margin percentage applicable on each session, combining Initial SPAN Margin, Extreme Loss Margin (ELM), and dynamic Volatility/Pre-Expiry margins.`
  },
  "calc-tab-shield": {
    title: "Risk & Liquidation Shield Cushion (%)",
    body: `Dynamic percentage safety cushion on each day: <code>Internal Margin % − Exchange Required Margin %</code>.<br><br>• <strong>0% Shield:</strong> Unencumbered free cash is exhausted; ledger balance equals required margin (not account wipeout).<br>• <strong>Liquidation:</strong> At ≤ 0%, broker RMS auto-squares off positions to protect remaining margin collateral.<br>• <strong>Buffer:</strong> Indicates the adverse percentage price swing the position can endure before forced liquidation.`
  },"""

if old_tooltips in content:
    content = content.replace(old_tooltips, new_tooltips)
    print("9. Replaced Tooltip definitions")
else:
    c_norm = content.replace('\r\n', '\n')
    o_norm = old_tooltips.replace('\r\n', '\n')
    n_norm = new_tooltips.replace('\r\n', '\n')
    if o_norm in c_norm:
        c_norm = c_norm.replace(o_norm, n_norm)
        content = c_norm.replace('\n', '\r\n')
        print("9. Replaced Tooltip definitions (normalized)")
    else:
        print("FAILED to replace Tooltip definitions")

with open(path, 'wb') as f:
    f.write(content.encode('utf-8'))

print("Completed updating docs/index.html")
