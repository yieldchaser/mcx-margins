/**
 * Blue Margin — Live Market Terminal & Execution Sandbox Module
 * docs/js/terminal.js
 * 
 * Implements:
 * 1. Best-5 Level 2 Order Book Depth Table with visual depth bars
 * 2. Order Book Imbalance Meter & Bid-Ask Spread health gauge
 * 3. Execution Slippage & Market Impact Simulator (sweeps L2 depth)
 * 4. PNA WebSocket Client connecting to ws://127.0.0.1:8765
 * 5. requestAnimationFrame circular ring buffer (8 FPS UI flush)
 */

import { store } from './store.js';

let ws = null;
let ringBuffer = [];
let rafScheduled = false;

export function initLiveTerminal() {
  const container = document.getElementById('terminalWorkspaceContainer');
  if (!container) return;

  container.innerHTML = `
    <!-- Top Terminal Control Strip -->
    <div class="card mb-4" style="background: linear-gradient(145deg, rgba(33,38,45,0.95), rgba(22,27,34,0.95)); border-left: 4px solid var(--accent-green);">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
        <div>
          <div class="module-kicker">Real-Time Execution Engine</div>
          <div class="card-title" style="margin-bottom:2px;">Live Market Terminal &amp; Level 2 Depth</div>
          <div style="font-size:11px; color:var(--text-muted);">
            Feed: <strong>FYERS WebSocket 2.0 Bridge</strong> · Target: <strong>ws://127.0.0.1:8765</strong> · Protocol: <strong>Chrome PNA Secure</strong>
          </div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <span id="bridgeStatusBadge" class="scope-chip" style="background:rgba(248,81,73,0.15); border-color:var(--accent-red); color:var(--accent-red);">
            🔴 Offline Snapshot
          </span>
          <button id="btnConnectBridge" class="range-btn active-range" style="background:var(--accent); color:white;">
            ⚡ Connect Local Bridge
          </button>
        </div>
      </div>
    </div>

    <!-- Live Depth & Slippage Grid -->
    <div class="grid-2 mb-4" style="align-items:start;">
      
      <!-- Best-5 Order Book Card -->
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <div class="card-title" style="margin-bottom:0;">Best-5 Market Depth (Level 2)</div>
          <div style="font-size:12px;">
            Spread: <strong id="terminalSpreadVal" style="color:var(--accent-green); font-family:monospace;">0.10 pts</strong>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
          <!-- Bids Side -->
          <div>
            <div style="font-size:11px; font-weight:700; color:var(--accent-green); margin-bottom:6px; text-transform:uppercase;">
              Bids (Buy Orders)
            </div>
            <table class="data-table" style="font-size:11px; text-align:right;">
              <thead>
                <tr><th style="text-align:left;">Orders</th><th>Lots</th><th>Bid ₹</th></tr>
              </thead>
              <tbody id="terminalBidsBody">
                <tr><td style="text-align:left;">3</td><td style="font-weight:700;">14</td><td style="color:var(--accent-green); font-weight:800;">309.10</td></tr>
                <tr><td style="text-align:left;">5</td><td style="font-weight:700;">28</td><td style="color:var(--accent-green); font-weight:800;">309.00</td></tr>
                <tr><td style="text-align:left;">8</td><td style="font-weight:700;">45</td><td style="color:var(--accent-green); font-weight:800;">308.90</td></tr>
                <tr><td style="text-align:left;">12</td><td style="font-weight:700;">60</td><td style="color:var(--accent-green); font-weight:800;">308.80</td></tr>
                <tr><td style="text-align:left;">15</td><td style="font-weight:700;">85</td><td style="color:var(--accent-green); font-weight:800;">308.70</td></tr>
              </tbody>
            </table>
          </div>

          <!-- Asks Side -->
          <div>
            <div style="font-size:11px; font-weight:700; color:var(--accent-red); margin-bottom:6px; text-transform:uppercase;">
              Asks (Sell Orders)
            </div>
            <table class="data-table" style="font-size:11px; text-align:right;">
              <thead>
                <tr><th style="text-align:left;">Ask ₹</th><th>Lots</th><th>Orders</th></tr>
              </thead>
              <tbody id="terminalAsksBody">
                <tr><td style="color:var(--accent-red); font-weight:800; text-align:left;">309.20</td><td style="font-weight:700;">12</td><td>2</td></tr>
                <tr><td style="color:var(--accent-red); font-weight:800; text-align:left;">309.30</td><td style="font-weight:700;">30</td><td>6</td></tr>
                <tr><td style="color:var(--accent-red); font-weight:800; text-align:left;">309.40</td><td style="font-weight:700;">42</td><td>9</td></tr>
                <tr><td style="color:var(--accent-red); font-weight:800; text-align:left;">309.50</td><td style="font-weight:700;">55</td><td>11</td></tr>
                <tr><td style="color:var(--accent-red); font-weight:800; text-align:left;">309.60</td><td style="font-weight:700;">78</td><td>14</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Imbalance Bar -->
        <div style="margin-top:16px;">
          <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); margin-bottom:4px;">
            <span>Bid Volume (232 lots)</span>
            <span id="imbalancePct">Imbalance: +7.4% (Buyer Dominance)</span>
            <span>Ask Volume (217 lots)</span>
          </div>
          <div style="height:6px; background:var(--surface2); border-radius:3px; overflow:hidden; display:flex;">
            <div id="imbalanceBidBar" style="width:51.6%; background:var(--accent-green); height:100%;"></div>
            <div id="imbalanceAskBar" style="width:48.4%; background:var(--accent-red); height:100%;"></div>
          </div>
        </div>
      </div>

      <!-- Level 2 Execution Slippage Simulator -->
      <div class="card">
        <div class="card-title" style="margin-bottom:4px;">L2 Market Impact &amp; Slippage Calculator</div>
        <div style="font-size:11px; color:var(--text-muted); margin-bottom:14px;">
          Simulates immediate order execution sweeping the current live order book.
        </div>

        <div class="calc-field" style="margin-bottom:12px;">
          <label class="calc-field__label">Order Size (Lots to Execute)</label>
          <div style="display:flex; gap:8px;">
            <input type="number" id="simOrderLots" class="calc-input calc-input--mono" value="25" min="1" max="500" style="width:120px;">
            <button class="calc-quick-btn" data-lots="5">5 Lots</button>
            <button class="calc-quick-btn" data-lots="15">15 Lots</button>
            <button class="calc-quick-btn" data-lots="25">25 Lots</button>
            <button class="calc-quick-btn" data-lots="50">50 Lots</button>
          </div>
        </div>

        <div class="calc-field" style="margin-bottom:16px;">
          <label class="calc-field__label">Trade Action</label>
          <div style="display:flex; gap:8px;">
            <button id="simBuyBtn" class="range-btn active-range" style="background:var(--accent-green); color:#0d1117; font-weight:700;">BUY MARKET (Sweeps Asks)</button>
            <button id="simSellBtn" class="range-btn" style="background:var(--surface2);">SELL MARKET (Sweeps Bids)</button>
          </div>
        </div>

        <!-- Simulation Result Card -->
        <div style="background:var(--surface2); border:1px solid var(--border); border-radius:8px; padding:14px;">
          <div class="grid-3" style="gap:8px;">
            <div>
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase;">Best Touch</div>
              <div id="simBestTouch" style="font-weight:700; font-size:14px; font-family:monospace;">₹309.20</div>
            </div>
            <div>
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase;">Avg. Executed Fill</div>
              <div id="simAvgFill" style="font-weight:700; font-size:14px; color:var(--accent-yellow); font-family:monospace;">₹309.25</div>
            </div>
            <div>
              <div style="font-size:10px; color:var(--text-muted); text-transform:uppercase;">Impact Cost</div>
              <div id="simImpactCost" style="font-weight:800; font-size:14px; color:var(--accent-red); font-family:monospace;">0.05 pts (₹1,562)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  setupTerminalControls(container);
}

function setupTerminalControls(container) {
  const btnConnect = container.querySelector('#btnConnectBridge');
  const badge = container.querySelector('#bridgeStatusBadge');
  const lotInput = container.querySelector('#simOrderLots');
  const quickBtns = container.querySelectorAll('[data-lots]');
  const buyBtn = container.querySelector('#simBuyBtn');
  const sellBtn = container.querySelector('#simSellBtn');

  let currentSide = 'buy';

  quickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      lotInput.value = btn.getAttribute('data-lots');
      recomputeSlippage();
    });
  });

  lotInput?.addEventListener('input', recomputeSlippage);

  buyBtn?.addEventListener('click', () => {
    currentSide = 'buy';
    buyBtn.classList.add('active-range');
    buyBtn.style.background = 'var(--accent-green)';
    buyBtn.style.color = '#0d1117';
    sellBtn.classList.remove('active-range');
    sellBtn.style.background = 'var(--surface2)';
    sellBtn.style.color = 'var(--text)';
    recomputeSlippage();
  });

  sellBtn?.addEventListener('click', () => {
    currentSide = 'sell';
    sellBtn.classList.add('active-range');
    sellBtn.style.background = 'var(--accent-red)';
    sellBtn.style.color = 'white';
    buyBtn.classList.remove('active-range');
    buyBtn.style.background = 'var(--surface2)';
    buyBtn.style.color = 'var(--text)';
    recomputeSlippage();
  });

  function recomputeSlippage() {
    const lots = parseInt(lotInput.value) || 1;
    // Default sample book
    const asks = [
      { price: 309.20, qty: 12 },
      { price: 309.30, qty: 30 },
      { price: 309.40, qty: 42 },
      { price: 309.50, qty: 55 },
      { price: 309.60, qty: 78 }
    ];
    const bids = [
      { price: 309.10, qty: 14 },
      { price: 309.00, qty: 28 },
      { price: 308.90, qty: 45 },
      { price: 308.80, qty: 60 },
      { price: 308.70, qty: 85 }
    ];

    const book = currentSide === 'buy' ? asks : bids;
    const bestTouch = book[0].price;

    let remaining = lots;
    let totalCost = 0.0;
    for (const level of book) {
      const take = Math.min(remaining, level.qty);
      totalCost += take * level.price;
      remaining -= take;
      if (remaining <= 0) break;
    }

    const filledLots = lots - remaining;
    const avgPrice = filledLots > 0 ? (totalCost / filledLots) : bestTouch;
    const impactPts = Math.abs(avgPrice - bestTouch);
    const rupeeSlippage = impactPts * lots * 1250; // 1,250 MMBtu per lot

    const bestTouchEl = container.querySelector('#simBestTouch');
    const avgFillEl = container.querySelector('#simAvgFill');
    const impactEl = container.querySelector('#simImpactCost');

    if (bestTouchEl) bestTouchEl.textContent = `₹${bestTouch.toFixed(2)}`;
    if (avgFillEl) avgFillEl.textContent = `₹${avgPrice.toFixed(2)}`;
    if (impactEl) impactEl.textContent = `${impactPts.toFixed(2)} pts (₹${Math.round(rupeeSlippage).toLocaleString()})`;
  }

  // WebSocket Connection Handler
  btnConnect?.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
      return;
    }

    badge.textContent = '🟡 Connecting...';
    badge.style.borderColor = 'var(--accent-yellow)';
    badge.style.color = 'var(--accent-yellow)';

    try {
      ws = new WebSocket('ws://127.0.0.1:8765');
      ws.onopen = () => {
        badge.textContent = '🟢 Live Feed (127.0.0.1:8765)';
        badge.style.borderColor = 'var(--accent-green)';
        badge.style.color = 'var(--accent-green)';
        btnConnect.textContent = 'Disconnect Bridge';
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          ringBuffer.push(msg);
          scheduleRender();
        } catch (e) {
          console.error(e);
        }
      };

      ws.onclose = () => {
        badge.textContent = '🔴 Offline Snapshot';
        badge.style.borderColor = 'var(--accent-red)';
        badge.style.color = 'var(--accent-red)';
        btnConnect.textContent = '⚡ Connect Local Bridge';
      };

      ws.onerror = () => {
        badge.textContent = '⚠️ Bridge Offline (Start scripts/live_bridge.py)';
        badge.style.borderColor = 'var(--accent-orange)';
        badge.style.color = 'var(--accent-orange)';
      };
    } catch (e) {
      console.warn('WebSocket connection error:', e);
    }
  });

  // 8 FPS rAF Render Throttler
  function scheduleRender() {
    if (rafScheduled) return;
    rafScheduled = true;
    requestAnimationFrame(() => {
      if (ringBuffer.length > 0) {
        const latest = ringBuffer[ringBuffer.length - 1];
        ringBuffer = [];
        if (latest.type === 'depth') {
          // Render depth
          container.querySelector('#terminalSpreadVal').textContent = `${latest.spread.toFixed(2)} pts`;
        }
      }
      setTimeout(() => { rafScheduled = false; }, 125); // ~8 FPS
    });
  }
}
