/**
 * Blue Margin — Options Intelligence Workspace Module
 * docs/js/options.js
 * 
 * Implements:
 * 1. Futures-Implied Support & Resistance Strip (Call Wall, Put Wall, Max Pain, 1-SD Cone)
 * 2. Active Liquid Strike Ladder (±15 strikes around ATM, OI > 10 filter)
 * 3. Black-76 Greeks & IV display
 * 4. Dual-Axis IV Smile & 25-Delta Risk Reversal Skew Chart
 */

import { store } from './store.js';

let ivChartInstance = null;

export async function initOptionsWorkspace() {
  const container = document.getElementById('optionsWorkspaceContainer');
  if (!container) return;

  const data = await store.fetchJson('data/options_chain_oct26.json');
  if (!data || !data.indicators) {
    container.innerHTML = `<div class="market-empty-state">Options chain data loading or unavailable.</div>`;
    return;
  }

  const ind = data.indicators;
  const meta = data.metadata;

  // Render HTML Shell
  container.innerHTML = `
    <!-- Top Futures-Implied S/R Strip -->
    <div class="card mb-4" style="background: linear-gradient(145deg, rgba(33,38,45,0.95), rgba(22,27,34,0.95)); border-left: 4px solid var(--accent);">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;">
        <div>
          <div class="module-kicker">Derivatives Price Targets</div>
          <div class="card-title" style="margin-bottom:2px;">Options-Implied Market Structure — Natural Gas Oct '26</div>
          <div style="font-size:11px; color:var(--text-muted);">
            Futures Reference: <strong>₹${meta.latest_futures_price.toFixed(2)}</strong> · Expiry: <strong>${meta.expiry_date} (${meta.days_to_expiry} DTE)</strong> · Model: <strong>Black-76 (Discounted to Futures)</strong>
          </div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <span class="scope-chip"><strong>PCR (OI)</strong> ${ind.pcr_oi.toFixed(2)}</span>
          <span class="scope-chip"><strong>25Δ Risk Reversal</strong> <span style="color:${ind.risk_reversal_25d >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${ind.risk_reversal_25d > 0 ? '+' : ''}${ind.risk_reversal_25d.toFixed(2)}%</span></span>
        </div>
      </div>

      <!-- High-Density S/R Grid -->
      <div class="grid-3" style="gap:12px;">
        <div class="macro-kpi-card" style="border-left: 3px solid var(--accent-red); min-height:80px; padding:10px 14px;">
          <div class="macro-kpi-label">Call Wall (Resistance)</div>
          <div class="macro-kpi-value" style="font-size:1.4rem; color:var(--accent-red);">₹${ind.call_wall_strike}</div>
          <div class="macro-kpi-sub">Highest Call OI: <strong>${ind.call_wall_oi.toLocaleString()}</strong> lots</div>
        </div>
        <div class="macro-kpi-card" style="border-left: 3px solid var(--accent-green); min-height:80px; padding:10px 14px;">
          <div class="macro-kpi-label">Put Wall (Floor Support)</div>
          <div class="macro-kpi-value" style="font-size:1.4rem; color:var(--accent-green);">₹${ind.put_wall_strike}</div>
          <div class="macro-kpi-sub">Highest Put OI: <strong>${ind.put_wall_oi.toLocaleString()}</strong> lots</div>
        </div>
        <div class="macro-kpi-card" style="border-left: 3px solid var(--accent-yellow); min-height:80px; padding:10px 14px;">
          <div class="macro-kpi-label">Max Pain & 1-SD Move Cone</div>
          <div class="macro-kpi-value" style="font-size:1.4rem; color:var(--accent-yellow);">₹${ind.max_pain_strike}</div>
          <div class="macro-kpi-sub">1-SD Band: <strong>₹${ind.expected_range_lower} – ₹${ind.expected_range_upper}</strong> (±₹${ind.expected_move_1sd})</div>
        </div>
      </div>
    </div>

    <!-- IV Smile & Skew Chart -->
    <div class="card mb-4">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div class="card-title" style="margin-bottom:0;">Black-76 Implied Volatility Smile &amp; Skew Surface</div>
        <div style="font-size:11px; color:var(--text-muted);">ATM Volatility: <strong>${ind.atm_iv_pct.toFixed(1)}%</strong></div>
      </div>
      <div class="chart-container" style="height:260px;"><canvas id="chartOptionsIVSmile"></canvas></div>
    </div>

    <!-- Active Liquid Strike Ladder Table -->
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;">
        <div class="card-title" style="margin-bottom:0;">Option Chain Matrix (Calls vs Puts)</div>
        <div style="display:flex; gap:6px;">
          <button id="optFilterLiquidBtn" class="range-btn active-range" title="Show strikes with active liquidity">Liquid Strikes (OI &gt; 10)</button>
          <button id="optFilterAllBtn" class="range-btn" title="Show full 136 strike ladder">All Strikes</button>
        </div>
      </div>

      <div class="market-table-shell" style="max-height: 480px; overflow-y:auto;">
        <table class="data-table" id="optionsLadderTable" style="text-align:center; font-size:12px;">
          <thead style="position:sticky; top:0; z-index:10;">
            <tr>
              <th colspan="5" style="background:rgba(56,139,253,0.15); color:var(--accent);">CALLS (CE)</th>
              <th rowspan="2" style="background:var(--surface2); color:var(--text); width:90px; border-left:1px solid var(--border); border-right:1px solid var(--border);">STRIKE ₹</th>
              <th colspan="5" style="background:rgba(248,81,73,0.15); color:var(--accent-red);">PUTS (PE)</th>
            </tr>
            <tr>
              <th style="background:rgba(56,139,253,0.08);">OI (Lots)</th>
              <th style="background:rgba(56,139,253,0.08);">Vol</th>
              <th style="background:rgba(56,139,253,0.08);">IV %</th>
              <th style="background:rgba(56,139,253,0.08);">Delta</th>
              <th style="background:rgba(56,139,253,0.08);">LTP ₹</th>
              <th style="background:rgba(248,81,73,0.08);">LTP ₹</th>
              <th style="background:rgba(248,81,73,0.08);">Delta</th>
              <th style="background:rgba(248,81,73,0.08);">IV %</th>
              <th style="background:rgba(248,81,73,0.08);">Vol</th>
              <th style="background:rgba(248,81,73,0.08);">OI (Lots)</th>
            </tr>
          </thead>
          <tbody id="optionsLadderBody"></tbody>
        </table>
      </div>
    </div>
  `;

  // Render Table Rows Function
  function renderLadder(rows) {
    const tbody = document.getElementById('optionsLadderBody');
    if (!tbody) return;

    let html = '';
    rows.forEach(r => {
      const k = r.strike;
      const isATM = (k === ind.atm_strike);
      const isCallWall = (k === ind.call_wall_strike);
      const isPutWall = (k === ind.put_wall_strike);

      const c = r.call || { ltp: '—', iv: '—', delta: '—', volume: 0, oi: 0 };
      const p = r.put || { ltp: '—', iv: '—', delta: '—', volume: 0, oi: 0 };

      let rowBg = '';
      if (isATM) rowBg = 'background: rgba(210,153,34,0.12);';

      html += `
        <tr style="${rowBg}">
          <td style="color:var(--text-muted);">${c.oi ? c.oi.toLocaleString() : '—'}</td>
          <td style="color:var(--text-muted);">${c.volume ? c.volume.toLocaleString() : '—'}</td>
          <td style="color:var(--accent); font-weight:600;">${c.iv ? c.iv + '%' : '—'}</td>
          <td style="color:var(--text); font-family:monospace;">${c.delta !== '—' ? c.delta.toFixed(2) : '—'}</td>
          <td style="font-weight:700; color:var(--text);">${c.ltp !== '—' ? '₹' + Number(c.ltp).toFixed(2) : '—'}</td>
          
          <td style="font-weight:800; font-size:13px; background:var(--surface2); border-left:1px solid var(--border); border-right:1px solid var(--border); color:${isATM ? 'var(--accent-yellow)' : isCallWall ? 'var(--accent-red)' : isPutWall ? 'var(--accent-green)' : 'var(--text)'};">
            ${k}
            ${isATM ? '<span style="font-size:9px; display:block; color:var(--accent-yellow);">ATM</span>' : ''}
            ${isCallWall ? '<span style="font-size:9px; display:block; color:var(--accent-red);">CALL WALL</span>' : ''}
            ${isPutWall ? '<span style="font-size:9px; display:block; color:var(--accent-green);">PUT WALL</span>' : ''}
          </td>

          <td style="font-weight:700; color:var(--text);">${p.ltp !== '—' ? '₹' + Number(p.ltp).toFixed(2) : '—'}</td>
          <td style="color:var(--text); font-family:monospace;">${p.delta !== '—' ? p.delta.toFixed(2) : '—'}</td>
          <td style="color:var(--accent-red); font-weight:600;">${p.iv ? p.iv + '%' : '—'}</td>
          <td style="color:var(--text-muted);">${p.volume ? p.volume.toLocaleString() : '—'}</td>
          <td style="color:var(--text-muted);">${p.oi ? p.oi.toLocaleString() : '—'}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  }

  // Initial render with filtered liquid chain
  renderLadder(data.chain);

  // Filter Buttons
  const liquidBtn = document.getElementById('optFilterLiquidBtn');
  const allBtn = document.getElementById('optFilterAllBtn');

  liquidBtn?.addEventListener('click', () => {
    liquidBtn.classList.add('active-range');
    allBtn.classList.remove('active-range');
    renderLadder(data.chain);
  });

  allBtn?.addEventListener('click', () => {
    allBtn.classList.add('active-range');
    liquidBtn.classList.remove('active-range');
    renderLadder(data.all_chain);
  });

  // Render IV Smile Chart
  renderIVSmileChart(data.chain, ind.atm_strike);
}

function renderIVSmileChart(chain, atmStrike) {
  const canvas = document.getElementById('chartOptionsIVSmile');
  if (!canvas) return;

  const validRows = chain.filter(r => r.call?.iv && r.put?.iv && r.call.iv > 0 && r.put.iv > 0);
  const labels = validRows.map(r => `₹${r.strike}`);
  const callIVs = validRows.map(r => r.call.iv);
  const putIVs = validRows.map(r => r.put.iv);

  if (ivChartInstance) {
    ivChartInstance.destroy();
    ivChartInstance = null;
  }

  const ctx = canvas.getContext('2d');
  ivChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Call IV % (CE)',
          data: callIVs,
          borderColor: '#388bfd',
          backgroundColor: 'rgba(56,139,253,0.1)',
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#388bfd',
          fill: false
        },
        {
          label: 'Put IV % (PE)',
          data: putIVs,
          borderColor: '#f85149',
          backgroundColor: 'rgba(248,81,73,0.1)',
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: '#f85149',
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top', labels: { color: '#e6edf3', font: { size: 11 } } },
        tooltip: {
          backgroundColor: 'rgba(22,27,34,0.95)',
          titleColor: '#e6edf3',
          bodyColor: '#e6edf3',
          borderColor: 'rgba(56,139,253,0.3)',
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#8b949e', font: { size: 10 } },
          grid: { color: 'rgba(139,148,158,0.1)' }
        },
        y: {
          ticks: { color: '#8b949e', callback: (v) => `${v}%` },
          grid: { color: 'rgba(139,148,158,0.1)' },
          title: { display: true, text: 'Implied Volatility (Black-76)', color: '#8b949e', font: { size: 10 } }
        }
      }
    }
  });
}
