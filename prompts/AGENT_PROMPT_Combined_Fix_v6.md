# Two Fixes — Send as ONE message (both fixes are small, safe to do together)

```bash
cd mcx-margins && git pull origin main
```

---

## FIX 1 — Tooltips (Variable Name Conflict)

Open `docs/index.html`. The ? badge shows but hovering does nothing because there are two conflicting variable declarations for the same DOM element. Open F12 → Console — there will be a red "already declared" or ReferenceError on page load.

**Edit: Search the entire `<script>` block and make these replacements:**

1. Find and DELETE every one of these lines wherever they appear (there will be duplicates):
```
const overlay = document.getElementById('tooltipOverlay');
const ttOverlay = document.getElementById('tooltipOverlay');
let hideTimer;
let ttHideTimer;
```

2. Add this ONCE at the very top of the `<script>` block (before any function):
```javascript
const _ttEl = document.getElementById('tooltipOverlay');
let _ttTimer;
```

3. Find the `showTooltip` function definition and replace its entire body with:
```javascript
function showTooltip(key) {
  const tt = TOOLTIPS[key];
  if (!tt || !_ttEl) return;
  clearTimeout(_ttTimer);
  document.getElementById('ttTitle').textContent = tt.title;
  document.getElementById('ttBody').innerHTML = tt.body;
  _ttEl.classList.add('visible');
}
```

4. Find the `hideTooltip` function definition and replace its entire body with:
```javascript
function hideTooltip() {
  _ttTimer = setTimeout(() => { if (_ttEl) _ttEl.classList.remove('visible'); }, 150);
}
```

5. Verify with Ctrl+F in the file:
   - `const overlay` → must appear **0 times**
   - `const ttOverlay` → must appear **0 times**
   - `let hideTimer` → must appear **0 times**
   - `let ttHideTimer` → must appear **0 times**
   - `_ttEl` → must appear exactly **4 times** (declaration + showTooltip + hideTooltip + the classList line)

---

## FIX 2 — Henry Hub Price (CORS failure → pre-fetch in Python)

The browser fetch from `query1.finance.yahoo.com` is blocked by CORS on GitHub Pages. Fix: fetch the price data in Python during the daily Actions run and save as a static JSON file. The dashboard then reads it locally — no CORS possible.

### Step A — Add HH price fetching to `export_json.py`

Open `export_json.py`. Add this import at the top with the other imports:
```python
import urllib.request
import json as json_lib
```

Then add this function and call it from `if __name__ == "__main__":`:

```python
def export_hh_price():
    """Fetch Henry Hub front-month price history from Yahoo Finance and save as JSON."""
    import time
    # 5 years of daily data
    period1 = int(time.time()) - (5 * 365 * 24 * 3600)
    period2 = int(time.time())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/NGW00.CME"
        f"?period1={period1}&period2={period2}&interval=1d"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json_lib.loads(resp.read())
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        prices = []
        for ts, close in zip(timestamps, closes):
            if close is not None:
                date_str = __import__('datetime').date.fromtimestamp(ts).isoformat()
                prices.append({"date": date_str, "price": round(close, 4)})
        save("hh_price.json", {"symbol": "NGW00.CME", "currency": "USD/MMBtu", "prices": prices})
    except Exception as e:
        print(f"  ⚠ HH price fetch failed: {e} — skipping hh_price.json")
```

In the `if __name__ == "__main__":` block, add this call right before `conn.close()`:
```python
    export_hh_price()
```

### Step B — Update `docs/index.html` to read local JSON instead of browser fetch

Find the `renderHistory()` function. Find the entire `if (showPrice) { try { ... } catch(e) { ... } }` block that contains the Yahoo Finance fetch URL. Replace that entire block with:

```javascript
  if (showPrice) {
    try {
      const hhData = await loadJSON('hh_price');
      if (hhData && hhData.prices && hhData.prices.length > 0) {
        // Build date→price lookup
        const priceMap = {};
        hhData.prices.forEach(p => { priceMap[p.date] = p.price; });

        // Align to our margin date labels
        const aligned = labels.map(d => priceMap[d] ?? null);
        const hasAny = aligned.some(v => v !== null);

        if (hasAny) {
          priceDataset = {
            label: 'Henry Hub ($/MMBtu)',
            data: aligned,
            borderColor: '#3fb950',
            backgroundColor: 'transparent',
            tension: 0.2,
            pointRadius: 0,
            borderWidth: 2,
            borderDash: [5, 3],
            yAxisID: 'yPrice'
          };
        }
      }
    } catch(e) {
      console.warn('HH price JSON load failed:', e);
    }
  }
```

### Step C — Run export and commit everything

```bash
# Fetch HH price and regenerate all JSON files
python export_json.py

# Verify the file was created
ls -lh docs/data/hh_price.json
# Should show file size > 5KB (will have years of daily prices)

# Check first few entries look right
python3 -c "
import json
d = json.load(open('docs/data/hh_price.json'))
print('Total prices:', len(d['prices']))
print('Sample:', d['prices'][-5:])
"

git add export_json.py docs/index.html docs/data/hh_price.json
git commit -m "fix: tooltips variable conflict resolved; HH price via pre-fetched JSON (no CORS)"
git push
```

---

## Verify after GitHub Pages deploys (~2 min)

**Tooltips:**
- Open F12 Console → must show ZERO red errors
- Hover any card title with ? badge → glassmorphism overlay appears center-screen
- Move mouse away → overlay fades

**Henry Hub:**
- Go to History tab
- Checkbox "Overlay Henry Hub Price (NGW00)" is visible in controls bar
- Tick it → chart immediately redraws with:
  - Blue line (left Y-axis) = Initial Margin %
  - Green dashed line (right Y-axis) = Henry Hub $/MMBtu
  - Legend shows both series
- Change range to 1Y or All → both lines update together
- Untick → green line disappears, right axis removed

If `hh_price.json` fetch failed during export (Yahoo blocks the Python request too), you will see the warning in terminal output. In that case, run this one-time manual fetch and commit the file:
```bash
python3 -c "
import urllib.request, json, time
period1 = int(time.time()) - (5*365*24*3600)
period2 = int(time.time())
url = f'https://query1.finance.yahoo.com/v8/finance/chart/NGW00.CME?period1={period1}&period2={period2}&interval=1d'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())
r = data['chart']['result'][0]
prices = [{'date': __import__(\"datetime\").date.fromtimestamp(ts).isoformat(), 'price': round(c,4)} for ts,c in zip(r['timestamp'], r['indicators']['quote'][0]['close']) if c]
out = {'symbol': 'NGW00.CME', 'currency': 'USD/MMBtu', 'prices': prices}
json.dump(out, open('docs/data/hh_price.json','w'))
print(f'Saved {len(prices)} price points')
"
git add docs/data/hh_price.json
git commit -m "data: add HH price history manually"
git push
```
