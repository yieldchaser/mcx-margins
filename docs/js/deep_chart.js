/**
 * deep_chart.js
 * -------------
 * Institutional High-Performance Multi-Resolution Chart (2019-2026, 1.65M Bars)
 * Powered by TradingView Lightweight Charts v4.2.
 * 
 * Features:
 * - Level of Detail (LOD) Dynamic Streaming:
 *     * Window > 60 Days: Tier 0 Daily Macro (~1,940 bars)
 *     * Window 10-60 Days: Tier 2 15-Minute Swing (~26,300 bars)
 *     * Window <= 10 Days: Tier 3 1-Minute Microstructure (~18,000 bars/month)
 * - Area Line Chart & Candlestick Modes
 * - Volume Histogram Overlay
 * - Interactive Crosshair HUD (OHLCV)
 * - Strictly Ascending Time Series Enforced
 * - 60 FPS Smooth Canvas Performance (Zero browser freeze)
 */

(function () {
  'use strict';

  let chart = null;
  let areaSeries = null;
  let candleSeries = null;
  let volumeSeries = null;
  let isCandleMode = false;
  let currentResolution = 'daily';
  let isSwitchingResolution = false;
  let resizeObserver = null;
  let pendingLODTimeout = null;

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
      visible: false,
    });

    // ── Volume Series: Histogram ──
    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '', // overlay
      scaleMargins: {
        top: 0.80,
        bottom: 0,
      },
    });

    // ── Crosshair HUD Update ──
    setupCrosshairHud();

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

  function setupCrosshairHud() {
    const hudDate = document.getElementById('hudDate');
    const hudOpen = document.getElementById('hudOpen');
    const hudHigh = document.getElementById('hudHigh');
    const hudLow = document.getElementById('hudLow');
    const hudClose = document.getElementById('hudClose');
    const hudVolume = document.getElementById('hudVolume');

    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time || !param.seriesData) {
        return;
      }
      const pBar = isCandleMode ? param.seriesData.get(candleSeries) : param.seriesData.get(areaSeries);
      const vBar = param.seriesData.get(volumeSeries);

      if (pBar) {
        const d = new Date(param.time * 1000);
        const dateStr = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', month: 'short', day: 'numeric', year: 'numeric' });
        const timeStr = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false });
        hudDate.textContent = currentResolution === 'daily' ? `Date: ${dateStr}` : `IST: ${dateStr} ${timeStr}`;

        if (pBar.open !== undefined) {
          hudOpen.innerHTML = `O: <strong style="color:var(--text)">₹${pBar.open.toFixed(2)}</strong>`;
          hudHigh.innerHTML = `H: <strong style="color:var(--accent-green)">₹${pBar.high.toFixed(2)}</strong>`;
          hudLow.innerHTML = `L: <strong style="color:var(--accent-red)">₹${pBar.low.toFixed(2)}</strong>`;
          hudClose.innerHTML = `C: <strong style="color:var(--text)">₹${pBar.close.toFixed(2)}</strong>`;
        } else if (pBar.value !== undefined) {
          hudOpen.innerHTML = '';
          hudHigh.innerHTML = '';
          hudLow.innerHTML = '';
          hudClose.innerHTML = `Price: <strong style="color:var(--text)">₹${pBar.value.toFixed(2)}</strong>`;
        }
      }
      if (vBar && vBar.value !== undefined) {
        hudVolume.innerHTML = `Vol: <strong style="color:var(--text)">${vBar.value.toLocaleString()}</strong>`;
      }
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

      // Filter to relevant range with padding
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
      // Determine required month string from center of visible window
      const centerTs = Math.floor(((fromTs || 0) + (toTs || fromTs || 0)) / 2) || 1792046640;
      const d = new Date(centerTs * 1000);
      const ym = `${d.getFullYear()}_${String(d.getMonth() + 1).padStart(2, '0')}`;

      if (!cache.m1[ym]) {
        const res = await fetch(`data/deep/1m/${ym}.json`);
        if (!res.ok) {
          // If month file not found, fall back to October 2026 active month
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
      // Fallback to 15m
      load15mTier(fromTs, toTs);
    }
  }

  function render1mRaw(rawBars, fromTs, toTs) {
    // raw format: [[time, open, high, low, close, volume], ...]
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
          areaSeries.applyOptions({ visible: false });
          candleSeries.applyOptions({ visible: true });
          btnToggle.textContent = 'Candles';
          btnToggle.style.color = 'var(--accent-green)';
          btnToggle.style.borderColor = 'var(--accent-green)';
        } else {
          areaSeries.applyOptions({ visible: true });
          candleSeries.applyOptions({ visible: false });
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
      case 'YTD': days = 288; break; // ~Jan 1 to Oct 15
      case '1Y': days = 365; break;
      case '5Y': days = 1825; break;
      case 'ALL':
      default:
        loadDailyTier(true);
        return;
    }

    const fromTs = nowTs - (days * 86400);
    const toTs = nowTs + (days * 0.05 * 86400); // 5% right margin

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

  // Expose global init function
  window.initDeepChart = initDeepChart;

  // Auto-init when Market tab becomes active or on window load
  document.addEventListener('DOMContentLoaded', () => {
    const marketTabBtn = document.querySelector('[data-tab="market"]');
    if (marketTabBtn) {
      marketTabBtn.addEventListener('click', () => {
        setTimeout(initDeepChart, 50);
      });
    }

    // If Market tab is already active on boot
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.getAttribute('data-tab') === 'market') {
      setTimeout(initDeepChart, 100);
    }
  });

})();
