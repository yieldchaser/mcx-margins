# MCX Margin Intelligence — Natural Gas Futures Dashboard

An automated intelligence platform extracting daily margin levels and volatility indexes from MCX CCL. Designed to visualize forward curves, historical volume offsets, and 16+ years of backfilled seasonal loading sets.

[![View Dashboard](https://img.shields.io/badge/View-Live--Dashboard-3fb950?style=for-the-badge&logo=github)](https://yieldchaser.github.io/mcx-margins/)
[![Daily Update](https://img.shields.io/badge/Daily--Update-Automated-388bfd?style=for-the-badge&logo=githubactions)](https://github.com/yieldchaser/mcx-margins/actions)

---

## 📊 Live Dashboard
The standalone layout translates scraped SQLite streams into structural JSON aggregates rendered efficiently inside panel workloads.

[**👉 Click to Launch the Dashboard**](https://yieldchaser.github.io/mcx-margins/)

### 📈 Major Feature Sets

*   **Overview Hub**: Front Month snapshot lists framed caching live ELM rates, structural volume aggregates, and predictive Hike/Cut Panic buffers.
*   **Term Structure**: Complete dual-axis loading curves comparing `NATURALGAS` vs `NATGASMINI` margin weights directly scaling spreads cleanly.
*   **Historical Trends**: Rich Chronological diagnostic sets spanning benchmarks since 2010 comparing absolute margin load values against daily steps.
*   **Seasonality Check**: Standard average Monthly/Annual load benchmarks framed inside rich Thermal Grid diagnostic lists cleanly.
*   **Analytics Layer**: DTE-to-Margin offsets framed framing heavy correlational lag predictors benchmarking Tomorrow’s projected weights safely.
*   **Raw Data Explorer**: Multi-column list filtering scaling continuous searches capable of direct Spreadsheet local downloading.

---

## 🚀 Current Database Context

The platform leverages a local highly dense SQLite buffer cached at `data/margins.db`:

| Symbol | Range | Records | Min Margin % | Max Margin % |
| :--- | :--- | :--- | :--- | :--- |
| **NATURALGAS** | `2010-01-01` to `Present` | **86,663** | 0.00% | 100.00% |
| **NATGASMINI** | `2023-03-14` to `Present` | **38,704** | 0.00% | 100.00% |

> **Total records**: ~125,367 continuous data points processed correctly scaling pipelines safely.

---

## 🛠️ System Architecture (Excel → SPA Pipeline)

The platform converts static spreadsheet calculations into direct automated streams inside actionable bundles:

### 1. Scraper Module (`scraper.py` + `main.py`)
*   Uses a **Multi-Layered Playwright stealth browser** setup navigating homepage streams first to safely acquire session cookies bypasses triggers.
*   Intercepts `POST /backpage.aspx/GetDailyMargin` direct API endpoints avoiding heavy DOM scraping payloads safely.
*   Normalizes standard daily volatility offsets mapping cleanly into standalone rows immediately.

### 2. Structured Storage (`db.py`)
*   SQLite cached buffers utilizing heavy indexes mapping continuous date composite lists avoids deduplication loads.
*   Single table configuration supporting heavy upsert continuous conflict diagnostics scaling securely loads correctly.

### 3. Static Indexer publishes (`export_json.py`)
Continually bundles heavy SQLite rows creating dense static caching buffers mirroring aggregates directly inside `docs/data/*.json`:
*   Aggregates dense historical monthly averages.
*   Creates DTE buckets offset curves.
*   Constructs term matrix matrices benchmarks securely cleanly.

### 4. SPA Client (`docs/index.html`)
Fast Zero-Dependency layout caching pure Vanilla async requests natively benchmarking parallel structures mapped strictly inside Chart.js frameworks concurrently without React framework delay loads.

---

## ⚙️ Continuous Automated Wiring

Defined securely scaling continuous pipelines mapping inside `.github/workflows/daily_margin.yml`:

*   **Trigger Schedule**: Runs automatically @ **1:30 & 13:30 UTC** (`7:00 AM & 7:00 PM IST`) loads concurrently.
*   **Step Setup Diagnostics**:
    1. Triggres Chromium launchers fetches last 3 fallback buffer days Catch late updates safely.
    2. Runs `export_json.py` aggregates full static payoads payloads directly scalable.
    3. Triggers atomic commit updates pushing DB datasets framing static output publishing maps safely.

---

## 💻 Local Setup Operations

To run pipelines or diagnostics locally on local machines:

### Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

### Quick Commands
*   **Re-run bundle export maps**: `python export_json.py`
*   **Summary lists indices totals**: `python query.py --summary`
*   **Excel output Diagnostics runs**: `python query.py --excel`

**View local outputs cleanly**:
```bash
python export_json.py
cd docs && python -m http.server 8080
```
Then visit: `http://localhost:8080` safely.
