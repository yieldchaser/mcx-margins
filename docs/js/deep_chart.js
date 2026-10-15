/**
 * deep_chart.js
 * -------------
 * Institutional High-Performance Multi-Resolution Chart (2019-2026, 1.65M Bars)
 * & Intraday Time-of-Day Seasonality Engine.
 * 
 * Features:
 * 1. Deep Multi-Resolution Zoom:
 *    - Level of Detail (LOD) Dynamic Streaming (Daily -> 15m -> 1m)
 *    - Strictly Ascending Time Series Enforced
 *    - Fixed Dual-Price Scale Bug: Volume series hides right-scale price badges
 *    - Dynamic Glassmorphism Floating Tooltip following cursor on canvas
 * 2. Intraday Time-of-Day (TOD) Volatility & Volume Profile:
 *    - 15-Minute granularity across 1,618,198 one-minute candles (2019-2026)
 *    - US DST-Aware: Summer (EDT) vs Winter (EST) vs Thursday EIA Shock Windows
 *    - Dual-axis Volume Histogram + Garman-Klass Volatility % Line
 *    - Rich Contextual Tooltips matching institutional design system
 */

(function () {
  'use strict';

  // ─────────────────────────────────────────────────────────────
  // PART 1: Multi-Resolution Deep Zoom Chart (TradingView LW)
  // ─────────────────────────────────────────────────────────────
  let chart = null;
  let areaSeries = null;
  let candleSeries = null;
  let volumeSeries = null;
  let isCandleMode = false;
  let currentResolution = 'daily';
  let isSwitchingResolution = false;
  let resizeObserver = null;
  let pendingLODTimeout = null;
  let floatingTooltip = null;

  // In-memory data caches
  const cache = {
    daily: null,
    h1: null,
    m15: null,
    m1: {}, // ym -> bars
  };

  function initDeepChart() {
    const container = document.getElementById('deepLightweightChartContainer');
    if (!container) return;
    if (chart) {
      chart.applyOptions({ width: container.clientWidth });
      return;
    }

    if (typeof LightweightCharts === 'undefined') {
      console.warn('LightweightCharts not loaded yet, retrying...');
      setTimeout(initDeepChart, 100);
      return;
    }

    // Create TradingView Lightweight Chart
    chart = LightweightCharts.createChart(container, {
      width: container.clientWidth || 800,
      height: 460,
      layout: {
        background: { type: 'solid', color: '#161b22' },
        textColor: '#8b949e',
        fontSize: 12,
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(48, 54, 61, 0.45)', style: 1 },
        horzLines: { color: 'rgba(48, 54, 61, 0.45)', style: 1 },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
          color: '#58a6ff',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1f6feb',
        },
        horzLine: {
          color: '#58a6ff',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1f6feb',
        },
      },
      rightPriceScale: {
        borderColor: '#30363d',
        scaleMargins: {
          top: 0.08,
          bottom: 0.22, // Leaves room for volume histogram
        },
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      localization: {
        priceFormatter: p => '₹' + p.toFixed(2),
        timeFormatter: ts => {
          const d = new Date(ts * 1000);
          return d.toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
          });
        }
      }
    });

    // ── Price Series: Area Line ──
    areaSeries = chart.addAreaSeries({
      lineColor: '#388bfd',
      topColor: 'rgba(56, 139, 253, 0.32)',
      bottomColor: 'rgba(56, 139, 253, 0.01)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 2, minMove: 0.1 },
      lastValueVisible: true,
      priceLineVisible: true,
      visible: true,
    });

    // ── Price Series: Candlestick ──
    candleSeries = chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
      priceFormat: { type: 'price', precision: 2, minMove: 0.1 },
      lastValueVisible: false,
      priceLineVisible: false,
      visible: false,
    });

    // ── Volume Series: Histogram ──
    // CRITICAL: lastValueVisible=false and priceLineVisible=false ensure volume number NEVER posts on the price scale!
    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '', // overlay
      lastValueVisible: false, // HIDES volume number from price scale (Fixes dual-price bug)
      priceLineVisible: false, // HIDES horizontal volume line
      scaleMargins: {
        top: 0.80,
        bottom: 0,
      },
    });

    // ── Create Dynamic Floating Tooltip Element ──
    createFloatingTooltip(container);

    // ── Crosshair HUD & Dynamic Tooltip Update ──
    setupCrosshairHud(container);

    // ── Visible Range Change Listener for Dynamic LOD ──
    chart.timeScale().subscribeVisibleTimeRangeChange(onTimeRangeChanged);

    // ── Window & Container Resize Observer ──
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(entries => {
        if (!entries || entries.length === 0 || !entries[0].contentRect) return;
        const newWidth = entries[0].contentRect.width;
        if (newWidth > 100 && chart) {
          chart.applyOptions({ width: newWidth });
        }
      });
      resizeObserver.observe(container);
    }

    // ── Wire UI Buttons ──
    setupUIControls();

    // ── Initial Load: Daily Tier 0 ──
    loadDailyTier(true);
  }

  function createFloatingTooltip(container) {
    if (document.getElementById('deepChartFloatingTooltip')) {
      floatingTooltip = document.getElementById('deepChartFloatingTooltip');
      return;
    }
    floatingTooltip = document.createElement('div');
    floatingTooltip.id = 'deepChartFloatingTooltip';
    floatingTooltip.style.position = 'absolute';
    floatingTooltip.style.display = 'none';
    floatingTooltip.style.padding = '8px 12px';
    floatingTooltip.style.boxSizing = 'border-box';
    floatingTooltip.style.fontSize = '12px';
    floatingTooltip.style.textAlign = 'left';
    floatingTooltip.style.zIndex = '100';
    floatingTooltip.style.top = '12px';
    floatingTooltip.style.left = '12px';
    floatingTooltip.style.pointerEvents = 'none';
    floatingTooltip.style.border = '1px solid var(--border)';
    floatingTooltip.style.borderRadius = '6px';
    floatingTooltip.style.background = 'rgba(22, 27, 34, 0.95)';
    floatingTooltip.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';
    floatingTooltip.style.backdropFilter = 'blur(6px)';
    floatingTooltip.style.color = '#e6edf3';
    floatingTooltip.style.fontFamily = 'Inter, monospace';
    floatingTooltip.style.lineHeight = '1.45';
    container.appendChild(floatingTooltip);
  }

  function setupCrosshairHud(container) {
    const hudDate = document.getElementById('hudDate');
    const hudOpen = document.getElementById('hudOpen');
    const hudHigh = document.getElementById('hudHigh');
    const hudLow = document.getElementById('hudLow');
    const hudClose = document.getElementById('hudClose');
    const hudVolume = document.getElementById('hudVolume');

    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time || !param.seriesData || !param.point ||
          param.point.x < 0 || param.point.x > container.clientWidth ||
          param.point.y < 0 || param.point.y > container.clientHeight) {
        if (floatingTooltip) floatingTooltip.style.display = 'none';
        return;
      }

      const pBar = isCandleMode ? param.seriesData.get(candleSeries) : param.seriesData.get(areaSeries);
      const vBar = param.seriesData.get(volumeSeries);

      if (pBar) {
        const d = new Date(param.time * 1000);
        const dateStr = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', month: 'short', day: 'numeric', year: 'numeric' });
        const timeStr = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false });
        const timeDisplay = currentResolution === 'daily' ? dateStr : `${dateStr} ${timeStr} IST`;

        // 1. Update Header HUD
        if (hudDate) hudDate.textContent = currentResolution === 'daily' ? `Date: ${dateStr}` : `IST: ${dateStr} ${timeStr}`;
        if (pBar.open !== undefined) {
          if (hudOpen) hudOpen.innerHTML = `O: <strong style="color:var(--text)">₹${pBar.open.toFixed(2)}</strong>`;
          if (hudHigh) hudHigh.innerHTML = `H: <strong style="color:var(--accent-green)">₹${pBar.high.toFixed(2)}</strong>`;
          if (hudLow) hudLow.innerHTML = `L: <strong style="color:var(--accent-red)">₹${pBar.low.toFixed(2)}</strong>`;
          if (hudClose) hudClose.innerHTML = `C: <strong style="color:var(--text)">₹${pBar.close.toFixed(2)}</strong>`;
        } else if (pBar.value !== undefined) {
          if (hudOpen) hudOpen.innerHTML = '';
          if (hudHigh) hudHigh.innerHTML = '';
          if (hudLow) hudLow.innerHTML = '';
          if (hudClose) hudClose.innerHTML = `Price: <strong style="color:var(--text)">₹${pBar.value.toFixed(2)}</strong>`;
        }
        if (vBar && vBar.value !== undefined && hudVolume) {
          hudVolume.innerHTML = `Vol: <strong style="color:var(--text)">${vBar.value.toLocaleString()}</strong>`;
        }

        // 2. Update Dynamic Floating Tooltip
        if (floatingTooltip) {
          floatingTooltip.style.display = 'block';

          let ohlcHtml = '';
          if (pBar.open !== undefined) {
            const ret = ((pBar.close - pBar.open) / pBar.open) * 100;
            const retColor = ret >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
            ohlcHtml = `
              <div style="display:flex; justify-content:space-between; gap:16px; margin-top:4px;">
                <span style="color:var(--text-muted);">Open:</span> <strong>₹${pBar.open.toFixed(2)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:16px;">
                <span style="color:var(--text-muted);">High:</span> <strong style="color:var(--accent-green);">₹${pBar.high.toFixed(2)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:16px;">
                <span style="color:var(--text-muted);">Low:</span> <strong style="color:var(--accent-red);">₹${pBar.low.toFixed(2)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:16px;">
                <span style="color:var(--text-muted);">Close:</span> <strong>₹${pBar.close.toFixed(2)}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; gap:16px;">
                <span style="color:var(--text-muted);">Bar Return:</span> <strong style="color:${retColor};">${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%</strong>
              </div>
            `;
          } else if (pBar.value !== undefined) {
            ohlcHtml = `
              <div style="display:flex; justify-content:space-between; gap:16px; margin-top:4px;">
                <span style="color:var(--text-muted);">Price:</span> <strong style="color:var(--accent); font-size:14px;">₹${pBar.value.toFixed(2)}</strong>
              </div>
            `;
          }

          const volHtml = (vBar && vBar.value !== undefined)
            ? `<div style="display:flex; justify-content:space-between; gap:16px; border-top:1px solid var(--border); margin-top:4px; padding-top:4px;">
                <span style="color:var(--text-muted);">Volume:</span> <strong>${vBar.value.toLocaleString()} lots</strong>
               </div>`
            : '';

          floatingTooltip.innerHTML = `
            <div style="font-weight:700; color:var(--text); border-bottom:1px solid var(--border); padding-bottom:3px; margin-bottom:4px; display:flex; justify-content:space-between; gap:12px;">
              <span>${timeDisplay}</span>
              <span style="font-size:10px; color:var(--accent); font-weight:600;">${currentResolution.toUpperCase()}</span>
            </div>
            ${ohlcHtml}
            ${volHtml}
          `;

          // Position smoothly within container boundaries
          const w = 195;
          const h = 150;
          let left = param.point.x + 18;
          if (left + w > container.clientWidth) {
            left = param.point.x - w - 18;
          }
          let top = param.point.y + 18;
          if (top + h > container.clientHeight) {
            top = param.point.y - h - 18;
          }
          floatingTooltip.style.left = Math.max(8, left) + 'px';
          floatingTooltip.style.top = Math.max(8, top) + 'px';
        }
      }
    });

    container.addEventListener('mouseleave', () => {
      if (floatingTooltip) floatingTooltip.style.display = 'none';
    });
  }

  async function loadDailyTier(fit) {
    updateBadges('Loading Daily...', '--');
    try {
      if (!cache.daily) {
        const res = await fetch('data/deep/ng_daily.json');
        if (!res.ok) throw new Error('Failed to load ng_daily.json');
        cache.daily = await res.json();
      }

      const areaData = [];
      const candleData = [];
      const volumeData = [];

      for (let i = 0; i < cache.daily.length; i++) {
        const b = cache.daily[i];
        areaData.push({ time: b.time, value: b.close });
        candleData.push({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close });
        volumeData.push({
          time: b.time,
          value: b.volume,
          color: b.close >= b.open ? 'rgba(63, 185, 80, 0.45)' : 'rgba(248, 81, 73, 0.45)'
        });
      }

      areaSeries.setData(areaData);
      candleSeries.setData(candleData);
      volumeSeries.setData(volumeData);

      currentResolution = 'daily';
      updateBadges('Daily (Macro)', `${cache.daily.length.toLocaleString()} bars`);

      if (fit) {
        chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error('Error loading daily tier:', err);
      updateBadges('Error', 'Failed to load');
    }
  }

  async function load15mTier(fromTs, toTs) {
    updateBadges('Loading 15m...', '--');
    try {
      if (!cache.m15) {
        const res = await fetch('data/deep/ng_15m.json');
        if (!res.ok) throw new Error('Failed to load ng_15m.json');
        cache.m15 = await res.json();
      }

      const pad = 15 * 86400; // 15 days padding
      const minT = (fromTs || 0) - pad;
      const maxT = (toTs || Infinity) + pad;

      const filtered = cache.m15.filter(b => b.time >= minT && b.time <= maxT);
      const dataToUse = filtered.length >= 20 ? filtered : cache.m15.slice(-3000);

      const areaData = [];
      const candleData = [];
      const volumeData = [];

      for (let i = 0; i < dataToUse.length; i++) {
        const b = dataToUse[i];
        areaData.push({ time: b.time, value: b.close });
        candleData.push({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close });
        volumeData.push({
          time: b.time,
          value: b.volume,
          color: b.close >= b.open ? 'rgba(63, 185, 80, 0.45)' : 'rgba(248, 81, 73, 0.45)'
        });
      }

      areaSeries.setData(areaData);
      candleSeries.setData(candleData);
      volumeSeries.setData(volumeData);

      currentResolution = '15m';
      updateBadges('15-Minute (Swing)', `${dataToUse.length.toLocaleString()} bars`);
    } catch (err) {
      console.error('Error loading 15m tier:', err);
    }
  }

  async function load1mTier(fromTs, toTs) {
    updateBadges('Loading 1-Minute...', '--');
    try {
      const centerTs = Math.floor(((fromTs || 0) + (toTs || fromTs || 0)) / 2) || 1792046640;
      const d = new Date(centerTs * 1000);
      const ym = `${d.getFullYear()}_${String(d.getMonth() + 1).padStart(2, '0')}`;

      if (!cache.m1[ym]) {
        const res = await fetch(`data/deep/1m/${ym}.json`);
        if (!res.ok) {
          console.warn(`Month ${ym}.json not found, falling back to 2026_10.json`);
          const fallbackRes = await fetch('data/deep/1m/2026_10.json');
          if (!fallbackRes.ok) throw new Error('1m fallback failed');
          cache.m1['2026_10'] = await fallbackRes.json();
          render1mRaw(cache.m1['2026_10'], fromTs, toTs);
          return;
        }
        cache.m1[ym] = await res.json();
      }

      render1mRaw(cache.m1[ym], fromTs, toTs);
    } catch (err) {
      console.error('Error loading 1m tier:', err);
      load15mTier(fromTs, toTs);
    }
  }

  function render1mRaw(rawBars, fromTs, toTs) {
    const pad = 2 * 86400; // 2 days padding
    const minT = (fromTs || 0) - pad;
    const maxT = (toTs || Infinity) + pad;

    const filtered = rawBars.filter(b => b[0] >= minT && b[0] <= maxT);
    const dataToUse = filtered.length >= 10 ? filtered : rawBars.slice(-1500);

    const areaData = [];
    const candleData = [];
    const volumeData = [];

    for (let i = 0; i < dataToUse.length; i++) {
      const b = dataToUse[i];
      areaData.push({ time: b[0], value: b[4] });
      candleData.push({ time: b[0], open: b[1], high: b[2], low: b[3], close: b[4] });
      volumeData.push({
        time: b[0],
        value: b[5],
        color: b[4] >= b[1] ? 'rgba(63, 185, 80, 0.45)' : 'rgba(248, 81, 73, 0.45)'
      });
    }

    areaSeries.setData(areaData);
    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    currentResolution = '1m';
    updateBadges('1-Minute (Microstructure)', `${dataToUse.length.toLocaleString()} bars`);
  }

  function onTimeRangeChanged(range) {
    if (!range || !range.from || !range.to || isSwitchingResolution) return;

    if (pendingLODTimeout) {
      clearTimeout(pendingLODTimeout);
    }

    pendingLODTimeout = setTimeout(() => {
      const spanDays = (range.to - range.from) / 86400;

      if (spanDays > 60 && currentResolution !== 'daily') {
        isSwitchingResolution = true;
        loadDailyTier(false).finally(() => { isSwitchingResolution = false; });
      } else if (spanDays <= 60 && spanDays > 10 && currentResolution !== '15m') {
        isSwitchingResolution = true;
        load15mTier(range.from, range.to).finally(() => { isSwitchingResolution = false; });
      } else if (spanDays <= 10 && currentResolution !== '1m') {
        isSwitchingResolution = true;
        load1mTier(range.from, range.to).finally(() => { isSwitchingResolution = false; });
      }
    }, 200);
  }

  function updateBadges(resText, countText) {
    const resBadge = document.getElementById('lodResolutionBadge');
    const countBadge = document.getElementById('lodCandleCountBadge');
    if (resBadge) resBadge.innerHTML = `<strong>Resolution:</strong> ${resText}`;
    if (countBadge) countBadge.innerHTML = `<strong>Loaded:</strong> ${countText}`;
  }

  function setupUIControls() {
    // Timeframe Buttons
    const tfButtons = document.querySelectorAll('.deep-tf-btn[data-tf]');
    tfButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        tfButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tf = btn.getAttribute('data-tf');
        applyTimeframe(tf);
      });
    });

    // Toggle Candlesticks / Line
    const btnToggle = document.getElementById('btnToggleChartType');
    if (btnToggle) {
      btnToggle.addEventListener('click', () => {
        isCandleMode = !isCandleMode;
        if (isCandleMode) {
          areaSeries.applyOptions({ visible: false, lastValueVisible: false, priceLineVisible: false });
          candleSeries.applyOptions({ visible: true, lastValueVisible: true, priceLineVisible: true });
          btnToggle.textContent = 'Candles';
          btnToggle.style.color = 'var(--accent-green)';
          btnToggle.style.borderColor = 'var(--accent-green)';
        } else {
          areaSeries.applyOptions({ visible: true, lastValueVisible: true, priceLineVisible: true });
          candleSeries.applyOptions({ visible: false, lastValueVisible: false, priceLineVisible: false });
          btnToggle.textContent = 'Line';
          btnToggle.style.color = '';
          btnToggle.style.borderColor = '';
        }
      });
    }

    // Reset Zoom
    const btnReset = document.getElementById('btnResetDeepZoom');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        tfButtons.forEach(b => b.classList.remove('active'));
        const allBtn = document.querySelector('.deep-tf-btn[data-tf="ALL"]');
        if (allBtn) allBtn.classList.add('active');
        loadDailyTier(true);
      });
    }
  }

  function applyTimeframe(tf) {
    if (!chart) return;
    const latestBar = cache.daily?.[cache.daily.length - 1];
    const nowTs = latestBar ? latestBar.time : Math.floor(Date.now() / 1000);
    let days = 0;

    switch (tf) {
      case '1D': days = 1; break;
      case '1W': days = 7; break;
      case '1M': days = 30; break;
      case '3M': days = 90; break;
      case 'YTD': days = 288; break;
      case '1Y': days = 365; break;
      case '5Y': days = 1825; break;
      case 'ALL':
      default:
        loadDailyTier(true);
        return;
    }

    const fromTs = nowTs - (days * 86400);
    const toTs = nowTs + (days * 0.05 * 86400);

    if (days <= 10) {
      load1mTier(fromTs, toTs).then(() => {
        chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
      });
    } else if (days <= 60) {
      load15mTier(fromTs, toTs).then(() => {
        chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
      });
    } else {
      loadDailyTier(false).then(() => {
        chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
      });
    }
  }

  // ─────────────────────────────────────────────────────────────
  // PART 2: Intraday Time-of-Day (TOD) Volatility & Volume Profile
  // ─────────────────────────────────────────────────────────────
  let todChartInstance = null;
  let todData = null;

  async function initTODSeasonality() {
    const canvas = document.getElementById('chartTODSeasonality');
    if (!canvas) return;

    try {
      if (!todData) {
        const res = await fetch('data/tod_seasonality.json');
        if (!res.ok) throw new Error('Failed to load tod_seasonality.json');
        todData = await res.json();
      }

      const buttons = document.querySelectorAll('[data-tod-profile]');
      buttons.forEach(btn => {
        btn.addEventListener('click', () => {
          buttons.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const profileKey = btn.getAttribute('data-tod-profile');
          renderTODChart(todData.profiles[profileKey] || todData.profiles.combined, profileKey);
        });
      });

      renderTODChart(todData.profiles.combined, 'combined');
    } catch (err) {
      console.error('Error initializing TOD Seasonality:', err);
    }
  }

  function getNextInterval(t) {
    const [h, m] = t.split(':').map(Number);
    let nm = m + 15;
    let nh = h;
    if (nm >= 60) {
      nm -= 60;
      nh += 1;
    }
    return `${String(nh).padStart(2, '0')}:${String(nm).padStart(2, '0')}`;
  }

  function renderTODChart(profile, key) {
    const canvas = document.getElementById('chartTODSeasonality');
    if (!canvas || !profile) return;

    if (todChartInstance) {
      todChartInstance.destroy();
      todChartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    todChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: profile.intervals,
        datasets: [
          {
            type: 'bar',
            label: 'Average Traded Volume (Lots / 15m)',
            data: profile.avg_volume,
            backgroundColor: 'rgba(56, 139, 253, 0.45)',
            borderColor: '#388bfd',
            borderWidth: 1,
            borderRadius: 2,
            yAxisID: 'y',
            order: 2
          },
          {
            type: 'line',
            label: 'Garman-Klass Volatility % (Annualized)',
            data: profile.gk_vol_pct,
            borderColor: '#fb8f44',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 1,
            tension: 0.25,
            yAxisID: 'y1',
            order: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: '#e6edf3', font: { family: 'Inter', size: 11 } }
          },
          tooltip: {
            backgroundColor: 'rgba(22, 27, 34, 0.95)',
            titleColor: '#e6edf3',
            bodyColor: '#e6edf3',
            borderColor: 'rgba(56, 139, 253, 0.3)',
            borderWidth: 1,
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              title: items => {
                const interval = profile.intervals[items[0].dataIndex];
                return `Interval: ${interval} – ${getNextInterval(interval)} IST`;
              },
              label: (ctx) => {
                if (ctx.datasetIndex === 0) {
                  const med = profile.median_volume ? ` (Median: ${profile.median_volume[ctx.dataIndex].toLocaleString()})` : '';
                  return `Volume: ${ctx.raw.toLocaleString()} lots${med}`;
                }
                const rng = profile.avg_range_pct ? ` · Avg Range: ${profile.avg_range_pct[ctx.dataIndex].toFixed(2)}%` : '';
                return `GK Volatility: ${ctx.raw.toFixed(1)}% annualized${rng}`;
              },
              afterBody: (items) => {
                const idx = items[0].dataIndex;
                const interval = profile.intervals[idx];
                if (interval === '09:00') return ['Context: MCX Morning Opening Gap & Overnight NYMEX Catch-up.'];
                if (interval >= '14:30' && interval <= '15:30') return ['Context: European Market Opening acceleration.'];
                if (interval >= '18:30' && interval <= '21:30') return ['Context: US NYMEX Pit trading & Primary Session Liquidity.'];
                if (interval === '20:00' && key === 'summer_edt') return ['Context: US EIA Storage Report Release Window (Summer EDT).'];
                if (interval === '21:00' && key === 'winter_est') return ['Context: US EIA Storage Report Release Window (Winter EST).'];
                if (interval >= '23:00') return ['Context: Pre-close intraday squaring & delivery margin cutoffs.'];
                return [];
              }
            }
          }
        },
        scales: {
          x: {
            ticks: { color: '#8b949e', font: { family: 'Inter', size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: 'rgba(139, 148, 158, 0.08)' }
          },
          y: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: 'Traded Volume (Lots / 15m)', color: '#8b949e', font: { family: 'Inter', size: 10 } },
            ticks: { color: '#8b949e', font: { family: 'Inter', size: 9 } },
            grid: { color: 'rgba(139, 148, 158, 0.08)' }
          },
          y1: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: 'Garman-Klass Volatility %', color: '#fb8f44', font: { family: 'Inter', size: 10 } },
            ticks: { color: '#fb8f44', font: { family: 'Inter', size: 9 }, callback: (v) => `${v}%` },
            grid: { drawOnChartArea: false }
          }
        }
      }
    });

    const insight = document.getElementById('todInsightText');
    if (insight) {
      if (key === 'summer_edt') {
        insight.innerHTML = `☀️ <strong>US Summer (EDT):</strong> NYMEX Pit opens at <strong>18:30 IST</strong>. Thursday US EIA Storage release occurs at <strong>20:00 IST</strong>. Prime liquidity and volatility surge during 18:30–20:30 IST.`;
      } else if (key === 'winter_est') {
        insight.innerHTML = `❄️ <strong>US Winter (EST):</strong> NYMEX Pit opens at <strong>19:30 IST</strong>. Thursday US EIA Storage release shifts to <strong>21:00 IST</strong>. Peak liquidity occurs 19:30–21:30 IST.`;
      } else if (key === 'thursday_eia') {
        insight.innerHTML = `⚡ <strong>Thursday Inventory Day:</strong> Volatility explodes up to <strong>2.8x baseline</strong> during the 20:00–21:00 IST release window, driving immediate intraday margin and VaR spikes.`;
      } else if (key === 'regular_weekdays') {
        insight.innerHTML = `📅 <strong>Regular Weekdays (Mon-Wed, Fri):</strong> Baseline organic volume curve showing steady afternoon pickup and peak liquidity between 18:30 and 22:00 IST without Thursday report distortion.`;
      } else {
        insight.innerHTML = `💡 <strong>Combined 8-Year Profile:</strong> Morning open (09:00 IST) features elevated overnight gap volatility, followed by session peak liquidity during US pit hours (18:30–21:30 IST).`;
      }
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Exports & Initialization
  // ─────────────────────────────────────────────────────────────
  window.initDeepChart = initDeepChart;
  window.initTODSeasonality = initTODSeasonality;

  function initMarketVisuals() {
    initDeepChart();
    initTODSeasonality();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const marketTabBtn = document.querySelector('[data-tab="market"]');
    if (marketTabBtn) {
      marketTabBtn.addEventListener('click', () => {
        setTimeout(initMarketVisuals, 60);
      });
    }

    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.getAttribute('data-tab') === 'market') {
      setTimeout(initMarketVisuals, 100);
    }
  });

})();
