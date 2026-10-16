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

  let activeContractMode = 'continuous'; // 'continuous' or standalone contract tag (e.g. 'NG_26OCT')
  const contractCache = {}; // tag -> { '15m': bars, '1m': bars }

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
        mode: LightweightCharts.CrosshairMode.Magnet,
        vertLine: {
          color: '#58a6ff',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1f6feb',
          visible: true,
          labelVisible: true,
        },
        horzLine: {
          visible: false, // Prevents spurious horizontal line across chart at cursor Y
          labelVisible: false, // Prevents cursor Y coordinate (e.g. ₹694.94) from displaying on Y-axis
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
        fixRightEdge: true, // CLAMP RIGHT EDGE: strictly prevents scrolling into blank future space
        rightOffset: 2,     // Clean buffer from the price scale
        minBarSpacing: 0.2, // Smooth zoom-in/out sensitivity
      },
      handleScroll: {
        mouseWheel: false,  // CRITICAL: Dedicate mousewheel 100% to zoom; prevent horizontal pan conflicts with fixRightEdge
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
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
      priceLineVisible: false, // Prevents persistent horizontal line at current price
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
      lastValueVisible: true,
      priceLineVisible: false,
      visible: false,
    });

    // ── Volume Series: Dedicated Overlay Scale ──
    // CRITICAL: Dedicated overlay priceScaleId isolates volume from the price scale.
    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume-scale',
      lastValueVisible: false, // HIDES volume number from price scale (Fixes dual-price bug)
      priceLineVisible: false, // HIDES horizontal volume line
    });

    // Confine volume histogram strictly to bottom 18% of chart canvas
    chart.priceScale('volume-scale').applyOptions({
      scaleMargins: {
        top: 0.82,
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
    floatingTooltip.style.padding = '12px 14px';
    floatingTooltip.style.boxSizing = 'border-box';
    floatingTooltip.style.fontSize = '12px';
    floatingTooltip.style.textAlign = 'left';
    floatingTooltip.style.zIndex = '100';
    floatingTooltip.style.pointerEvents = 'none';
    floatingTooltip.style.border = '1px solid rgba(56, 139, 253, 0.4)';
    floatingTooltip.style.borderRadius = '8px';
    floatingTooltip.style.background = 'rgba(22, 27, 34, 0.96)';
    floatingTooltip.style.boxShadow = '0 12px 28px rgba(0, 0, 0, 0.6)';
    floatingTooltip.style.backdropFilter = 'blur(8px)';
    floatingTooltip.style.color = '#e6edf3';
    floatingTooltip.style.fontFamily = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';
    floatingTooltip.style.lineHeight = '1.5';
    floatingTooltip.style.minWidth = '220px';
    container.appendChild(floatingTooltip);
  }

  // Fast binary search helper for O(log n) bar lookups across 26k+ points
  function findBarByTime(bars, targetTime) {
    if (!bars || !bars.length) return null;
    let low = 0, high = bars.length - 1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      const b = bars[mid];
      const t = b.time !== undefined ? b.time : b[0];
      if (t === targetTime) return b;
      if (t < targetTime) low = mid + 1;
      else high = mid - 1;
    }
    return null;
  }

  // Helper: Enforces strictly ascending order and eliminates duplicate timestamps
  function sanitizeBars(bars) {
    if (!bars || !Array.isArray(bars) || bars.length === 0) return [];
    const sorted = [...bars].sort((a, b) => a.time - b.time);
    const deduped = [];
    for (let i = 0; i < sorted.length; i++) {
      const b = sorted[i];
      if (deduped.length === 0) {
        deduped.push(b);
      } else {
        const last = deduped[deduped.length - 1];
        if (b.time > last.time) {
          deduped.push(b);
        } else if (b.time === last.time) {
          deduped[deduped.length - 1] = b; // Keep newest bar (overwrite)
        }
      }
    }
    return deduped;
  }

  // Parse compact columnar JSON format { dt: [...], o: [...], h: [...], l: [...], c: [...], v: [...] }
  function parseColumnarBars(json) {
    if (!json || !json.data || !json.data.dt) return [];
    const dt = json.data.dt;
    const o = json.data.o;
    const h = json.data.h;
    const l = json.data.l;
    const c = json.data.c;
    const v = json.data.v;
    const n = dt.length;
    const bars = new Array(n);
    for (let i = 0; i < n; i++) {
      bars[i] = {
        time: dt[i],
        open: o[i],
        high: h[i],
        low: l[i],
        close: c[i],
        volume: v[i] || 0
      };
    }
    return sanitizeBars(bars);
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

        // Resolve complete bar record (OHLCV) whether in Candle mode or Area Line mode
        let ohlc = null;
        if (pBar.open !== undefined) {
          ohlc = pBar;
        } else if (pBar.value !== undefined) {
          if (activeContractMode !== 'continuous') {
            const cBars = contractCache[activeContractMode]?.[currentResolution];
            if (cBars) ohlc = findBarByTime(cBars, param.time);
          } else if (currentResolution === 'daily' && cache.daily) {
            ohlc = findBarByTime(cache.daily, param.time);
          } else if (currentResolution === '15m' && cache.m15) {
            ohlc = findBarByTime(cache.m15, param.time);
          } else if (currentResolution === '1m') {
            const istDateStr = d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
            const ym = istDateStr.slice(0, 7).replace('-', '_');
            if (cache.m1[ym]) {
              const raw = findBarByTime(cache.m1[ym], param.time);
              if (raw) ohlc = { open: raw[1], high: raw[2], low: raw[3], close: raw[4], volume: raw[5] };
            }
          }
          if (!ohlc) {
            ohlc = { close: pBar.value };
          }
        } else {
          ohlc = pBar;
        }

        const closePrice = ohlc.close !== undefined ? ohlc.close : (pBar.value !== undefined ? pBar.value : pBar.close);
        const openPrice = ohlc.open;
        const highPrice = ohlc.high;
        const lowPrice = ohlc.low;
        const volVal = (vBar && vBar.value !== undefined) ? vBar.value : (ohlc.volume !== undefined ? ohlc.volume : null);

        // 1. Update Header HUD
        if (hudDate) hudDate.textContent = currentResolution === 'daily' ? `Date: ${dateStr}` : `IST: ${dateStr} ${timeStr}`;
        if (openPrice !== undefined && highPrice !== undefined && lowPrice !== undefined) {
          if (hudOpen) hudOpen.innerHTML = `O: <strong style="color:var(--text)">₹${openPrice.toFixed(2)}</strong>`;
          if (hudHigh) hudHigh.innerHTML = `H: <strong style="color:var(--accent-green)">₹${highPrice.toFixed(2)}</strong>`;
          if (hudLow) hudLow.innerHTML = `L: <strong style="color:var(--accent-red)">₹${lowPrice.toFixed(2)}</strong>`;
          if (hudClose) hudClose.innerHTML = `C: <strong style="color:var(--text)">₹${closePrice.toFixed(2)}</strong>`;
        } else {
          if (hudOpen) hudOpen.innerHTML = '';
          if (hudHigh) hudHigh.innerHTML = '';
          if (hudLow) hudLow.innerHTML = '';
          if (hudClose) hudClose.innerHTML = `Price: <strong style="color:var(--text)">₹${closePrice.toFixed(2)}</strong>`;
        }
        if (volVal !== null && hudVolume) {
          hudVolume.innerHTML = `Vol: <strong style="color:var(--text)">${volVal.toLocaleString()} lots</strong>`;
        }

        // 2. Update Dynamic Floating Tooltip
        if (floatingTooltip) {
          floatingTooltip.style.display = 'block';

          let ohlcHtml = '';
          if (openPrice !== undefined && highPrice !== undefined && lowPrice !== undefined) {
            const ret = ((closePrice - openPrice) / openPrice) * 100;
            const diff = closePrice - openPrice;
            const retColor = ret >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
            ohlcHtml = `
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:6px 12px; margin-top:6px; font-family:monospace; font-size:11.5px;">
                <div><span style="color:var(--text-muted);">Open:</span> <strong style="color:var(--text);">₹${openPrice.toFixed(2)}</strong></div>
                <div><span style="color:var(--text-muted);">High:</span> <strong style="color:var(--accent-green);">₹${highPrice.toFixed(2)}</strong></div>
                <div><span style="color:var(--text-muted);">Low:</span> <strong style="color:var(--accent-red);">₹${lowPrice.toFixed(2)}</strong></div>
                <div><span style="color:var(--text-muted);">Close:</span> <strong style="color:var(--text);">₹${closePrice.toFixed(2)}</strong></div>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; padding-top:6px; border-top:1px solid rgba(48,54,61,0.6); font-size:11.5px;">
                <span style="color:var(--text-muted);">Bar Change:</span>
                <span style="font-weight:700; color:${retColor}; font-family:monospace;">${ret >= 0 ? '+' : ''}${ret.toFixed(2)}% (${diff >= 0 ? '+' : ''}₹${diff.toFixed(2)})</span>
              </div>
            `;
          } else {
            ohlcHtml = `
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px; font-size:12px;">
                <span style="color:var(--text-muted);">Price:</span>
                <strong style="color:var(--accent); font-size:14px; font-family:monospace;">₹${closePrice.toFixed(2)}</strong>
              </div>
            `;
          }

          const volHtml = (volVal !== null)
            ? `<div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px; padding-top:6px; border-top:1px solid rgba(48,54,61,0.6); font-size:11.5px;">
                <span style="color:var(--text-muted);">Traded Volume:</span>
                <strong style="font-family:monospace; color:var(--text);">${volVal.toLocaleString()} lots</strong>
               </div>`
            : '';

          floatingTooltip.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(56, 139, 253, 0.3); padding-bottom:6px; margin-bottom:4px;">
              <span style="font-weight:700; color:#58a6ff; font-size:11px; text-transform:uppercase; letter-spacing:0.04em;">${timeDisplay}</span>
              <span style="background:rgba(56,139,253,0.15); color:var(--accent); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; border:1px solid rgba(56,139,253,0.3);">${currentResolution.toUpperCase()}</span>
            </div>
            ${ohlcHtml}
            ${volHtml}
          `;

          // Position smoothly without obscuring the cursor or candle
          const w = 230;
          const h = (openPrice !== undefined) ? 165 : 115;
          let left = param.point.x + 20;
          if (left + w > container.clientWidth - 12) {
            left = param.point.x - w - 20;
          }
          if (left < 10) left = 10;

          let top = param.point.y - 35;
          if (top + h > container.clientHeight - 12) {
            top = container.clientHeight - h - 12;
          }
          if (top < 10) top = 10;
          floatingTooltip.style.left = left + 'px';
          floatingTooltip.style.top = top + 'px';
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

      const cleanBars = sanitizeBars(cache.daily);
      const areaData = [];
      const candleData = [];
      const volumeData = [];

      for (let i = 0; i < cleanBars.length; i++) {
        const b = cleanBars[i];
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
      updateBadges('Daily (Macro)', `${cleanBars.length.toLocaleString()} bars`);

      if (fit) {
        chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error('Error loading daily tier:', err);
      updateBadges('Error', 'Failed to load');
    }
  }

  async function load15mTier() {
    updateBadges('Loading 15m...', '--');
    try {
      if (!cache.m15) {
        const res = await fetch('data/deep/ng_15m.json');
        if (!res.ok) throw new Error('Failed to load ng_15m.json');
        cache.m15 = await res.json();
      }

      const cleanBars = sanitizeBars(cache.m15);
      const areaData = [];
      const candleData = [];
      const volumeData = [];

      for (let i = 0; i < cleanBars.length; i++) {
        const b = cleanBars[i];
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
      updateBadges('15-Minute (Swing)', `${cleanBars.length.toLocaleString()} bars`);
    } catch (err) {
      console.error('Error loading 15m tier:', err);
    }
  }

  async function load1mTier(fromTs, toTs) {
    updateBadges('Loading 1-Minute...', '--');
    try {
      const centerTs = Math.floor(((fromTs || 0) + (toTs || fromTs || 0)) / 2) || 1792066980;
      const d = new Date(centerTs * 1000);
      const istDateStr = d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
      const ym = istDateStr.slice(0, 7).replace('-', '_');

      if (!cache.m1[ym]) {
        const res = await fetch(`data/deep/1m/${ym}.json`);
        if (!res.ok) {
          console.info(`1m data for ${ym} not found, falling back to 15m tier`);
          await load15mTier();
          return;
        }
        cache.m1[ym] = await res.json();
      }

      render1mRaw(cache.m1[ym]);
    } catch (err) {
      console.warn('Error loading 1m tier, falling back to 15m:', err);
      await load15mTier();
    }
  }

  function render1mRaw(rawBars) {
    if (!rawBars || !rawBars.length) return;
    const cleanBars = sanitizeBars(rawBars.map(b => ({
      time: b[0],
      open: b[1],
      high: b[2],
      low: b[3],
      close: b[4],
      volume: b[5]
    })));

    const areaData = [];
    const candleData = [];
    const volumeData = [];

    for (let i = 0; i < cleanBars.length; i++) {
      const b = cleanBars[i];
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

    currentResolution = '1m';
    updateBadges('1-Minute (Microstructure)', `${cleanBars.length.toLocaleString()} bars`);
  }

  function renderContractBars(cleanBars, res) {
    if (!cleanBars || !cleanBars.length) return;
    const areaData = [];
    const candleData = [];
    const volumeData = [];

    for (let i = 0; i < cleanBars.length; i++) {
      const b = cleanBars[i];
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

    currentResolution = res;
    const resLabel = res === '1m' ? '1-Minute (Microstructure)' : '15-Minute (Swing)';
    updateBadges(resLabel, `${cleanBars.length.toLocaleString()} bars`);
  }

  async function loadContractTier(tag, res) {
    updateBadges(`Loading ${res}...`, '--');
    if (!contractCache[tag]) contractCache[tag] = {};

    if (!contractCache[tag][res]) {
      try {
        const fetchRes = await fetch(`data/market/${tag}_${res}.json`);
        if (!fetchRes.ok) {
          if (res === '1m') {
            console.warn(`1m data for ${tag} not found, falling back to 15m`);
            return await loadContractTier(tag, '15m');
          }
          throw new Error(`Failed to load data/market/${tag}_${res}.json`);
        }
        const json = await fetchRes.json();
        contractCache[tag][res] = parseColumnarBars(json);
      } catch (err) {
        console.error(`Error loading ${tag} ${res}:`, err);
        updateBadges('Error', 'Failed to load');
        return;
      }
    }

    renderContractBars(contractCache[tag][res], res);
  }

  async function switchContract(tag) {
    isSwitchingResolution = true;
    if (pendingLODTimeout) {
      clearTimeout(pendingLODTimeout);
      pendingLODTimeout = null;
    }

    const titleEl = document.getElementById('deepChartTitle');
    const scopeBadge = document.getElementById('deepContractDataScopeBadge');

    if (tag === 'continuous') {
      activeContractMode = 'continuous';
      if (titleEl) {
        titleEl.textContent = 'Front-Month Historical Price Action & Intraday Structure';
        titleEl.setAttribute('data-dyn-body', 'Continuous front-month contract price series spanning 8 full years (2019 to 2026), unstitched across roll boundaries to preserve true historical price discovery.');
      }
      if (scopeBadge) {
        scopeBadge.innerHTML = '<strong>Data</strong> 8Y Front-Month';
        scopeBadge.setAttribute('data-dyn-title', '8-Year Continuous Front-Month');
        scopeBadge.setAttribute('data-dyn-body', 'Aggregated from 1,653,214 historical 1-minute execution ticks across 92 monthly contracts.');
      }

      const allBtn = document.querySelector('.deep-tf-btn[data-tf="ALL"]');
      if (allBtn) {
        allBtn.textContent = '8Y (All)';
        allBtn.setAttribute('data-dyn-title', '8Y Full Macro View');
        allBtn.setAttribute('data-dyn-body', 'Displays all 8 years of historical daily prices (2019 to 2026).');
      }

      await loadDailyTier(true);
      setTimeout(() => { isSwitchingResolution = false; }, 200);
      return;
    }

    activeContractMode = tag;
    const formattedTag = tag.replace('_', ' ');
    if (titleEl) {
      titleEl.textContent = `${formattedTag} Contract Lifecycle & Price Discovery`;
      titleEl.setAttribute('data-dyn-body', `Individual standalone price action for ${formattedTag} from contract inception to current live market, with direct 15m and 1m resolution streaming.`);
    }
    if (scopeBadge) {
      scopeBadge.innerHTML = `<strong>Contract</strong> ${formattedTag}`;
      scopeBadge.setAttribute('data-dyn-title', `${formattedTag} Standalone History`);
      scopeBadge.setAttribute('data-dyn-body', `Full standalone contract price history from inception date.`);
    }

    const allBtn = document.querySelector('.deep-tf-btn[data-tf="ALL"]');
    if (allBtn) {
      allBtn.textContent = 'Full Life';
      allBtn.setAttribute('data-dyn-title', 'Full Contract Lifecycle');
      allBtn.setAttribute('data-dyn-body', 'Displays entire lifecycle from contract inception date.');
    }

    const tfButtons = document.querySelectorAll('.deep-tf-btn[data-tf]');
    tfButtons.forEach(b => b.classList.remove('active'));
    if (allBtn) allBtn.classList.add('active');

    await loadContractTier(tag, '15m');
    chart.timeScale().fitContent();
    setTimeout(() => { isSwitchingResolution = false; }, 200);
  }

  function onTimeRangeChanged(range) {
    if (!range || !range.from || !range.to || isSwitchingResolution) return;

    if (pendingLODTimeout) {
      clearTimeout(pendingLODTimeout);
    }

    pendingLODTimeout = setTimeout(() => {
      const spanDays = (range.to - range.from) / 86400;

      if (activeContractMode !== 'continuous') {
        if (spanDays <= 7 && currentResolution !== '1m') {
          isSwitchingResolution = true;
          const cur = chart.timeScale().getVisibleRange();
          loadContractTier(activeContractMode, '1m').finally(() => {
            if (cur && cur.from && cur.to) chart.timeScale().setVisibleRange(cur);
            setTimeout(() => { isSwitchingResolution = false; }, 200);
          });
        } else if (spanDays > 7 && currentResolution !== '15m') {
          isSwitchingResolution = true;
          const cur = chart.timeScale().getVisibleRange();
          loadContractTier(activeContractMode, '15m').finally(() => {
            if (cur && cur.from && cur.to) chart.timeScale().setVisibleRange(cur);
            setTimeout(() => { isSwitchingResolution = false; }, 200);
          });
        }
        return;
      }

      const m15StartTs = 1735702200; // 2025-01-01
      const isPre2025 = range.from < m15StartTs;

      if ((spanDays > 120 || isPre2025) && currentResolution !== 'daily') {
        isSwitchingResolution = true;
        const cur = chart.timeScale().getVisibleRange();
        loadDailyTier(false).finally(() => {
          if (cur && cur.from && cur.to) chart.timeScale().setVisibleRange(cur);
          setTimeout(() => { isSwitchingResolution = false; }, 200);
        });
      } else if (spanDays <= 120 && spanDays > 7 && !isPre2025 && currentResolution !== '15m') {
        isSwitchingResolution = true;
        const cur = chart.timeScale().getVisibleRange();
        load15mTier().finally(() => {
          if (cur && cur.from && cur.to) chart.timeScale().setVisibleRange(cur);
          setTimeout(() => { isSwitchingResolution = false; }, 200);
        });
      } else if (spanDays <= 7 && !isPre2025 && currentResolution !== '1m') {
        isSwitchingResolution = true;
        const cur = chart.timeScale().getVisibleRange();
        load1mTier(range.from, range.to).finally(() => {
          if (cur && cur.from && cur.to) chart.timeScale().setVisibleRange(cur);
          setTimeout(() => { isSwitchingResolution = false; }, 200);
        });
      }
    }, 300);
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
          candleSeries.applyOptions({ visible: true, lastValueVisible: true, priceLineVisible: false });
          btnToggle.textContent = 'Candles';
          btnToggle.style.color = 'var(--accent-green)';
          btnToggle.style.borderColor = 'var(--accent-green)';
        } else {
          areaSeries.applyOptions({ visible: true, lastValueVisible: true, priceLineVisible: false });
          candleSeries.applyOptions({ visible: false, lastValueVisible: false, priceLineVisible: false });
          btnToggle.textContent = 'Line';
          btnToggle.style.color = '';
          btnToggle.style.borderColor = '';
        }
      });
    }

    // Contract Selector Dropdown
    const contractSelect = document.getElementById('deepContractSelect');
    if (contractSelect) {
      contractSelect.addEventListener('change', (e) => {
        switchContract(e.target.value);
      });
    }

    // Reset Zoom
    const btnReset = document.getElementById('btnResetDeepZoom');
    if (btnReset) {
      btnReset.addEventListener('click', () => {
        tfButtons.forEach(b => b.classList.remove('active'));
        const allBtn = document.querySelector('.deep-tf-btn[data-tf="ALL"]');
        if (allBtn) allBtn.classList.add('active');
        if (activeContractMode === 'continuous') {
          loadDailyTier(true);
        } else {
          loadContractTier(activeContractMode, '15m').then(() => {
            chart.timeScale().fitContent();
          });
        }
      });
    }
  }

  function applyTimeframe(tf) {
    if (!chart) return;
    isSwitchingResolution = true;
    if (pendingLODTimeout) {
      clearTimeout(pendingLODTimeout);
      pendingLODTimeout = null;
    }

    if (activeContractMode !== 'continuous') {
      const bars = contractCache[activeContractMode]?.[currentResolution] ||
                   contractCache[activeContractMode]?.['15m'] ||
                   contractCache[activeContractMode]?.['1m'];
      const nowTs = (bars && bars.length) ? bars[bars.length - 1].time : 1792068300;

      if (tf === 'ALL') {
        loadContractTier(activeContractMode, '15m').then(() => {
          chart.timeScale().fitContent();
          setTimeout(() => { isSwitchingResolution = false; }, 250);
        });
        return;
      }

      let days = 1;
      switch (tf) {
        case '1D': days = 1; break;
        case '1W': days = 7; break;
        case '1M': days = 30; break;
        case '3M': days = 90; break;
        case 'YTD':
        case '1Y':
        case '5Y':
        default:
          days = 180;
          break;
      }

      const fromTs = nowTs - Math.round(days * 86400);
      const toTs = nowTs;
      const targetRes = (days <= 7) ? '1m' : '15m';

      loadContractTier(activeContractMode, targetRes).then(() => {
        chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
        setTimeout(() => { isSwitchingResolution = false; }, 250);
      });
      return;
    }

    const latestDaily = cache.daily?.[cache.daily.length - 1]?.time || 0;
    const latest15m = cache.m15?.[cache.m15.length - 1]?.time || 0;
    const nowTs = Math.max(latestDaily, latest15m, 1792068300);

    let days = 0;
    switch (tf) {
      case '1D': days = 1; break;
      case '1W': days = 7; break;
      case '1M': days = 30; break;
      case '3M': days = 90; break;
      case 'YTD': {
        const d = new Date(nowTs * 1000);
        const ytdStart = Math.floor(Date.UTC(d.getUTCFullYear(), 0, 1) / 1000);
        days = Math.max(1, (nowTs - ytdStart) / 86400);
        break;
      }
      case '1Y': days = 365; break;
      case '5Y': days = 1825; break;
      case 'ALL':
      default:
        loadDailyTier(true).then(() => {
          setTimeout(() => { isSwitchingResolution = false; }, 250);
        });
        return;
    }

    const fromTs = nowTs - Math.round(days * 86400);
    const toTs = nowTs; // CLAMP TO LATEST AVAILABLE CANDLE (Zero future dead space)

    const onComplete = () => {
      chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
      setTimeout(() => { isSwitchingResolution = false; }, 250);
    };

    if (days <= 7) {
      load1mTier(fromTs, toTs).then(onComplete).catch(() => {
        load15mTier().then(onComplete);
      });
    } else if (days <= 120) {
      load15mTier().then(onComplete).catch(() => {
        loadDailyTier(false).then(onComplete);
      });
    } else {
      loadDailyTier(false).then(onComplete);
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

  function getTODMarketContext(interval, key) {
    if (interval === '09:00') {
      return {
        phase: 'MCX Opening Bell & Overnight Rebalancing',
        catalyst: 'Price discovery digesting overnight NYMEX Globex moves & morning weather model runs.',
        execution: 'Spread: Wide · Risk: Elevated opening jump. Avoid unhedged market orders at open.'
      };
    }
    if (interval >= '09:15' && interval < '10:30') {
      return {
        phase: 'Morning Price Discovery & Book Building',
        catalyst: 'Domestic commercial hedgers and institutional order books establish session baseline.',
        execution: 'Spread: Stabilizing · Liquidity: Moderate. Order depth solidifies.'
      };
    }
    if (interval >= '10:30' && interval < '13:00') {
      return {
        phase: 'Asian Midday Lull (Quiet Mean-Reversion)',
        catalyst: 'Quiescent global window; low international macro volume, algorithmic MM dominance.',
        execution: 'Spread: Tight · Volatility: Low. Favorable for patient limit order accumulation.'
      };
    }
    if (interval >= '13:00' && interval < '14:30') {
      return {
        phase: 'European Pre-Market Positioning',
        catalyst: 'London & European energy trading desks come online; TTF/NBP arbitrage flow starts.',
        execution: 'Spread: Tightening · Momentum: Watch for directional trend initiation from Europe.'
      };
    }
    if (interval >= '14:30' && interval < '17:00') {
      return {
        phase: 'European Full Session (ICE TTF Cross-Flow)',
        catalyst: 'Active European trading hours; ICE TTF gas benchmark volume peaks, guiding global tone.',
        execution: 'Liquidity: Robust · Spread: Institutional. Steady international trend flow.'
      };
    }
    if (key === 'winter_est') {
      if (interval >= '17:00' && interval < '19:30') {
        const isPreUs = interval >= '18:30';
        return {
          phase: isPreUs ? 'US Winter Pre-Market (1h DST Shift)' : 'US Pre-Market Accumulation',
          catalyst: isPreUs
            ? 'In US Winter (EST), NYMEX Pit opens at 19:30 IST (1 hr later than summer).'
            : 'North American desks begin pre-market positioning ahead of cash open.',
          execution: isPreUs
            ? 'Watch: False breakouts frequent before 19:30 IST official US cash bell.'
            : 'Volume begins stepping up; book depth increases steadily.'
        };
      }
    } else {
      if (interval >= '17:00' && interval < '18:30') {
        return {
          phase: 'US Pre-Market Positioning',
          catalyst: 'US commercial desks and hedge funds stage orders for the NYMEX cash opening.',
          execution: 'Spread: Tight · Depth: Thickening in anticipation of NYMEX pit bell.'
        };
      }
    }

    if (key === 'winter_est') {
      if (interval >= '19:30' && interval < '20:30') {
        return {
          phase: 'US NYMEX Pit Open (Winter Schedule: 19:30 IST)',
          catalyst: '19:30 IST marks the winter US cash open. Primary global liquidity influx begins.',
          execution: 'Peak Volume Velocity · Deepest market liquidity and narrowest spreads of the winter day.'
        };
      }
    } else {
      if (interval >= '18:30' && interval < '20:00') {
        return {
          phase: 'US NYMEX Pit Open (Primary Cash Bell: 18:30 IST)',
          catalyst: '18:30 IST marks the official US pit session bell. Primary institutional surge.',
          execution: 'Maximum Depth · Highest volume velocity and tightest bid-ask spreads of the 24h cycle.'
        };
      }
    }

    const isEIAWindow = (key === 'winter_est' && interval >= '21:00' && interval < '21:30') ||
                        (key !== 'winter_est' && interval >= '20:00' && interval < '20:30') ||
                        (key === 'thursday_eia' && interval >= '20:00' && interval <= '21:00');
    if (isEIAWindow) {
      return {
        phase: '🚨 US EIA STORAGE REPORT RELEASE WINDOW',
        catalyst: 'Weekly US EIA underground storage inventory release. Extreme volatility shock up to 2.8x baseline.',
        execution: 'Risk: Violent 15m price dislocation (1.5%–4.0%). Spreads widen instantly; avoid market orders.'
      };
    }

    if (interval >= '20:00' && interval < '22:30') {
      return {
        phase: 'Active US Power & Heating Demand Trading',
        catalyst: 'US cash session in full swing; 18z weather model runs (GFS/ECMWF) cross wires.',
        execution: 'Liquidity: High · Momentum: Strong follow-through on weather degree-day revisions.'
      };
    }

    if (interval >= '22:30' && interval < '23:15') {
      return {
        phase: 'MCX Broker Square-Off Window (MIS Liquidation)',
        catalyst: 'Domestic retail brokers trigger automated square-offs of intraday leverage positions.',
        execution: 'Caution: Mechanical flow spikes and localized stop-runs independent of Henry Hub.'
      };
    }

    return {
      phase: 'Session Cash Close & Settlement Run',
      catalyst: 'MCX daily settlement price calculation (15m VWAP). Delivery margin cutoffs applied.',
      execution: 'Liquidity: Thinning rapidly · Risk: Extreme overnight carryover & gap-open risk.'
    };
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
            backgroundColor: 'rgba(22, 27, 34, 0.96)',
            titleColor: '#58a6ff',
            titleFont: { family: 'Inter', size: 12, weight: '700' },
            bodyColor: '#e6edf3',
            bodyFont: { family: 'Inter', size: 11.5 },
            borderColor: 'rgba(56, 139, 253, 0.35)',
            borderWidth: 1,
            padding: 12,
            boxPadding: 6,
            cornerRadius: 8,
            usePointStyle: true,
            callbacks: {
              title: items => {
                const interval = profile.intervals[items[0].dataIndex];
                const next = getNextInterval(interval);
                return `⏰ Window: ${interval} – ${next} IST`;
              },
              label: (ctx) => {
                if (ctx.datasetIndex === 0) {
                  const vol = ctx.raw || 0;
                  const med = profile.median_volume ? profile.median_volume[ctx.dataIndex] : 0;
                  const ratio = med > 0 ? (vol / med).toFixed(1) : '1.0';
                  return `📊 Average Traded Volume: ${Math.round(vol).toLocaleString()} lots · Median: ${Math.round(med).toLocaleString()} (${ratio}x skew)`;
                }
                const gk = ctx.raw || 0;
                const rng = profile.avg_range_pct ? profile.avg_range_pct[ctx.dataIndex].toFixed(2) : '—';
                const regime = gk >= 20 ? '🔴 ELEVATED VOL' : gk >= 15 ? '🟡 ACTIVE' : '🟢 CALM';
                return `⚡ GK Realized Volatility: ${gk.toFixed(2)}% [${regime}] · Avg 15m Range: ${rng}%`;
              },
              afterBody: (items) => {
                const idx = items[0].dataIndex;
                const interval = profile.intervals[idx];
                const c = getTODMarketContext(interval, key);
                return [
                  `Session Phase: ${c.phase}`,
                  `Market Driver: ${c.catalyst}`,
                  `Execution Rule: ${c.execution}`
                ];
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
