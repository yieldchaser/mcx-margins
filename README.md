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

The platform converts static calculations into automated daily streams:

### 1. Scraper Module (`src/scraper.py` + `main.py`)
*   Uses a **Multi-Layered Playwright stealth browser** triggering homepage navigations first to bypass target session cookies and bot detections safely.
*   Intercepts `POST /backpage.aspx/GetDailyMargin` API payloads directly inside browser execution, omitting heavy DOM nodes for fast scraping.
*   Normalizes standardized volatility data points mapping seamlessly into daily offset streams.

### 2. Structured Storage (`src/db.py`)
*   Local fast **SQLite cached repository** utilizing rich composed composite framing indexes preserving strict consistency and skipping overlapping duplications securely.

### 3. Static Indexer publishes (`export_json.py`)
Continually bundles aggregates drafting fully dense statically loaded caches stored natively inside `docs/data/*.json`:
*   Assembles dense historical correlation coefficients.
*   Resolves Cross-Origin (CORS) limits offline supporting **Henry Hub benchmark price** layering loads fallback scripts securely.

### 4. Continuous Alerts Pipeline (`alert.py`)
*   Queries historical margin shifts from SQLite date differentials.
*   Auto-flags sudden absolute shifts (> thresholds) triggering rich **HTML Email Alerts via SMTP** keeping traders aligned ahead of funding timelines.

### 5. SPA Client Dashboard (`docs/index.html`)
Fast **Vanilla Javascript SPA layout with Glassmorphism overlay aesthetics**. Renders lightweight requests into parallel structural outputs using standard Chart.js concurrent plotting without React bundle wait times safely.

---

## ⚙️ Continuous Automated Wiring

Defined securely inside the `.github/workflows/daily_margin.yml` Github Actions configuration:

*   **Trigger Schedule**: Runs automatically @ **1:30 & 13:30 UTC** (`7:00 AM & 7:00 PM IST`) loads seamlessly.
*   **Sequential Pipeline Operations**:
    1. **Fetch Setup Check**: Triggers Chromium fetch streams loading last 3 days to catch delayed update offsets safely.
    2. **Static Bundling**: Runs static stream aggregates publishing directly into local SPA documentation trees.
    3. **Threshold Guard**: Executes threshold differential algorithms sending email alerts when spikes load safely.
    4. **Commit publishing**: Auto-streams push state differentials securely committing back incremental database commits autonomously.

---

## 💻 Local Setup Operations

To run pipelines or diagnostics locally on local machines:

### Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

### Quick CLI Helpers
*   **Fetch Single Date updates**: `python main.py YYYY-MM-DD`
*   **Re-run full aggregate publish**: `python export_json.py`
*   **Console Summary metrics**: `python query.py --summary`
*   **Direct Excel Sheet export files**: `python query.py --excel`

**View local live dashboards safely**:
```bash
python export_json.py
cd docs && python -m http.server 8080
```
Then visit: `http://localhost:8080` safely.
