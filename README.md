# MCX CCL Margin Scraper — Complete Analysis

All files read: `main.py`, `scraper.py`, `db.py`, `backfill.py`, `query.py`, `requirements.txt`, `.github/workflows/daily_margin.yml`. Database queried via Node.js binary parsing.

---

## Question 1: What does this project do?

This project is an automated daily margin data scraper for the **MCX CCL (Multi Commodity Exchange Clearing Corporation Limited)** website. It uses a headless Chromium browser (via Playwright) to navigate to `https://www.mcxccl.com/risk-management/daily-margin`, bypass Akamai bot detection by first visiting the homepage, fill in a date, click the "Show" button, and intercept the JSON API response from the `POST /backpage.aspx/GetDailyMargin` endpoint. It then filters the results to keep only two symbols — `NATURALGAS` and `NATGASMINI` — normalizes the percentage fields, and stores them in a local SQLite database at `data/margins.db`. A GitHub Actions workflow runs this automatically every weekday evening (Indian time), committing the updated database back to the repository. A query tool (`query.py`) lets you inspect the data or export it to Excel.

---

## Question 2: What data is collected — fields/columns for NATURALGAS and NATGASMINI?

Both symbols are stored in the single `margins` table in `data/margins.db`. The table schema (defined in `db.py`) has these columns:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `date` | TEXT | Trading date in `YYYY-MM-DD` format |
| `symbol` | TEXT | Either `NATURALGAS` or `NATGASMINI` |
| `expiry` | TEXT | Contract expiry date (e.g., `26MAR2026`) |
| `instrument_id` | TEXT | Instrument type from API (e.g., `FUTCOM`) |
| `file_id` | INTEGER | File ID from the API response |
| `initial_margin_pct` | REAL | Initial margin as a percentage (e.g., `33.1`) |
| `elm_pct` | REAL | Extreme Loss Margin % (uses `ELMLong` from API, falls back to `ELMShort`) |
| `tender_margin_pct` | REAL | Tender period margin % |
| `total_margin_pct` | REAL | Total margin % (sum of all applicable margins) |
| `additional_long_margin_pct` | REAL | Additional margin for long positions % |
| `additional_short_margin_pct` | REAL | Additional margin for short positions % |
| `special_long_margin_pct` | REAL | Special margin for long positions % |
| `special_short_margin_pct` | REAL | Special margin for short positions % |
| `delivery_margin_pct` | REAL | Delivery margin % |
| `daily_volatility` | REAL | Daily volatility (e.g., `0.04996`) |
| `annualized_volatility` | REAL | Annualized volatility (e.g., `0.789937`) |
| `raw_data` | TEXT | Full JSON snapshot of the normalized row |
| `created_at` | TEXT | Timestamp when the record was inserted |

The unique constraint is `(date, symbol, expiry, file_id)`, so re-running for the same date safely upserts rather than duplicates. There are three indexes: on `date`, on `symbol`, and a composite `(date, symbol)`.

A real sample record from the database (2026-02-27, NATURALGAS, expiry 26MAR2026):
```json
{
  "date": "2026-02-27", "symbol": "NATURALGAS", "expiry": "26MAR2026",
  "instrument_id": "FUTCOM", "file_id": 1,
  "initial_margin_pct": 33.1, "elm_pct": 1.25,
  "tender_margin_pct": 0.0, "total_margin_pct": 33.1,
  "additional_long_margin_pct": 0.0, "additional_short_margin_pct": 0.0,
  "special_long_margin_pct": 0.0, "special_short_margin_pct": 0.0,
  "delivery_margin_pct": 0.0,
  "daily_volatility": 0.04996, "annualized_volatility": 0.789937
}
```

---

## Question 3: What does the database currently have?

The database at `data/margins.db` currently contains **only one date of data: 2026-02-27** (the most recent trading day before this analysis). The equivalent output of `python3 query.py --summary` would be:

```
==========================================================================================
  MCX CCL Margin Data Summary
==========================================================================================

Symbol               Count   Earliest     Latest       Avg IM%  Min IM%  Max IM%
--------------------------------------------------------------------------------
NATGASMINI              60   2026-02-27   2026-02-27     25.22    16.26    32.90
NATURALGAS              59   2026-02-27   2026-02-27     27.36    22.69    33.10

Total symbols: 2, Total records: 119
```

- **NATGASMINI**: 60 records (one per contract expiry), all from 2026-02-27. Average initial margin 25.22%, ranging from 16.26% to 32.90%.
- **NATURALGAS**: 59 records (one per contract expiry), all from 2026-02-27. Average initial margin 27.36%, ranging from 22.69% to 33.10%.
- **Total**: 119 records across 1 date. The database file is 110,592 bytes (27 SQLite pages).

---

## Question 4: What happens when I run `python3 backfill.py 2022-01-01`?

**What it does step by step:**

1. Calls `db.init_db()` to create the `margins` table if it doesn't exist.
2. Calls `db.get_all_dates()` to load all dates already in the database (currently just `2026-02-27`).
3. Generates all weekdays (Monday–Friday) from `2022-01-01` to today using `generate_weekdays()`.
4. Computes the list of **missing dates** = all weekdays minus dates already in DB.
5. Iterates through each missing date, calling `fetch_and_save(date_str)` which:
   - Launches a headless Chromium browser
   - Visits `https://www.mcxccl.com/` (homepage, to bypass Akamai)
   - Navigates to `https://www.mcxccl.com/risk-management/daily-margin`
   - Fills the date fields and clicks "Show"
   - Intercepts the `GetDailyMargin` API response
   - Filters for `NATURALGAS` and `NATGASMINI` only
   - Upserts matching records into `data/margins.db`
6. Waits **3 seconds** (`REQUEST_DELAY = 3`) between each date request.
7. Prints a final summary of dates attempted, dates with data, holidays/empty days, errors, and total records saved.

**How long will it take?**

From `2022-01-01` to `2026-02-28` there are approximately **1,085 weekdays**. With 1 date already in the DB, that leaves ~**1,084 dates to fetch**. Each date requires launching a browser, loading two pages, waiting for the API, plus the 3-second delay — realistically **30–60 seconds per date**. Total estimate: **~10 to 19 hours** of continuous runtime. Many dates will be Indian market holidays (MCX is closed ~15–20 days/year), which return 0 records quickly, so the actual time may be toward the lower end.

**Where does data get saved?**

All data is saved to `data/margins.db` (a SQLite file). This path is hardcoded in `db.py` as `DB_PATH = Path("data/margins.db")`. The `data/` directory is created automatically if it doesn't exist.

**Can I stop and resume safely?**

**Yes, completely safe.** The backfill script checks existing dates at startup (`existing_dates = set(db.get_all_dates())`) and skips any date already in the database. If you stop mid-run (Ctrl+C), the next time you run `python3 backfill.py 2022-01-01` it will pick up exactly where it left off — only fetching dates not yet in the DB. The upsert logic (`ON CONFLICT ... DO UPDATE`) also means re-running a partially-saved date won't create duplicates.

---

## Question 5: What happens automatically every weekday — the GitHub Actions workflow?

The workflow is defined in `.github/workflows/daily_margin.yml` and is named **"Daily Margin Fetch"**.

**Trigger:** Runs automatically at **14:30 UTC every Monday through Friday** (which is 8:00 PM IST — after MCX market close). It can also be triggered manually via `workflow_dispatch`.

**What it does, step by step:**

1. **Checks out the repository** (including the current `data/margins.db` file) using `actions/checkout@v4`.
2. **Sets up Python 3.10** using `actions/setup-python@v5`.
3. **Installs dependencies**: runs `pip install -r requirements.txt` (installs `playwright`, `pandas`, `openpyxl`, `python-dateutil`), then installs the Chromium browser binary via `python -m playwright install chromium` and its system dependencies via `python -m playwright install-deps chromium`.
4. **Fetches today's margin data**: runs `python main.py $(date +%Y-%m-%d)` — this scrapes the MCX CCL website for today's date and saves NATURALGAS and NATGASMINI records into `data/margins.db`.
5. **Commits and pushes the updated database back to the repo**:
   - Configures git with the `github-actions[bot]` identity
   - Stages the entire `data/` directory (`git add data/`)
   - Only commits if there are actual changes (`git diff --staged --quiet || git commit -m "data: daily margin YYYY-MM-DD"`)
   - Pushes using the built-in `GITHUB_TOKEN` secret

**Net result:** Every weekday evening, the `data/margins.db` file in the repository is automatically updated with that day's margin data for NATURALGAS and NATGASMINI, with a commit message like `data: daily margin 2026-02-28`. If the website returns no data (holiday, outage), nothing is committed.

---

## Question 6: After the backfill completes, what exact command exports the final Excel?

```bash
python3 query.py --excel
```

**What it produces:**

- Creates a directory called `exports/` if it doesn't exist
- Writes the file **`exports/mcx_margins.xlsx`**
- The Excel file has **two sheets**:
  1. **"Daily Margins"** — all records for `NATURALGAS` and `NATGASMINI`, ordered by `date DESC, symbol ASC, expiry ASC`, with columns: `Date`, `Symbol`, `Expiry`, `Instrument ID`, `File ID`, `Initial Margin %`, `ELM %`, `Tender Margin %`, `Total Margin %`, `Additional Long Margin %`, `Additional Short Margin %`, `Special Long Margin %`, `Special Short Margin %`, `Delivery Margin %`, `Daily Volatility`, `Annualized Volatility`, `Created At`
  2. **"Summary"** — per-symbol statistics: `Symbol`, `Record Count`, `Earliest Date`, `Latest Date`, `Avg Initial Margin %`, `Min Initial Margin %`, `Max Initial Margin %`
- Column widths are auto-fitted (capped at 30 characters wide)
- Requires `pandas` and `openpyxl` to be installed (both are in `requirements.txt`)

The export query (in `query.py`) explicitly filters `WHERE symbol IN ('NATURALGAS', 'NATGASMINI')`, so only those two symbols appear in the Excel regardless of what else might be in the database.

---

After writing the file, run these git commands to commit and push:
```bash
cd /workspace/56d40feb-509a-4ae5-8e49-e7e07078677d/sessions/agent_6aa4f2a7-c83b-470b-8a08-6afa1486243d && git add README.md && git commit -m "docs: add README with project analysis and usage guide" && git push
```

Use attempt_completion to report the result once the file is written and pushed successfully.

---

## Code Audit — 7-Question Analysis

### Q1: Akamai Bypass in `scraper.py` — ✅ Complete and Functional

Uses a **multi-layered Playwright stealth approach**:

1. **Homepage-first navigation** (lines 104–112): visits `https://www.mcxccl.com/` first to acquire Akamai session cookies before hitting the data page.
2. **Stealth JS injection** (lines 41–47, applied via `add_init_script`): removes `navigator.webdriver`, fakes `window.chrome`, sets realistic `languages` and `hardwareConcurrency`.
3. **Realistic browser context** (lines 73–83): Windows Chrome 120 user-agent, 1920×1080 viewport, `en-US` locale, `Asia/Kolkata` timezone, full `sec-ch-ua` headers.
4. **Launch args** (lines 22–29): `--disable-blink-features=AutomationControlled` suppresses the automation flag.
5. **API response interception** (lines 89–101): intercepts the `POST /backpage.aspx/GetDailyMargin` JSON response directly — no DOM scraping.
6. **Correct dual-format date handling**: fills `#txtDate` as `DD/MM/YYYY` (display) and `cph_InnerContainerRight_C001_txtDate_hid_val` as `YYYYMMDD` (what the API reads).

---

### Q2: Filtering in `main.py` — ✅ Only NATURALGAS and NATGASMINI

Exact filter logic (`main.py` lines 14, 57–59):

```python
SYMBOLS_TO_STORE = {"NATURALGAS", "NATGASMINI"}

if normalized.get("symbol") not in SYMBOLS_TO_STORE:
    skipped += 1
    continue
```

Identical filter exists in `backfill.py` lines 14 and 35–36. All other symbols are silently skipped before any DB write.

---

### Q3: Backfill Safety in `backfill.py` — ✅ Safe to Stop and Resume

Exact skip logic (`backfill.py` lines 63–71):

```python
existing_dates = set(db.get_all_dates())
print(f"[backfill] Found {len(existing_dates)} dates already in DB")
all_weekdays = generate_weekdays(start_date, today)
missing_dates = [d for d in all_weekdays if d not in existing_dates]
print(f"[backfill] Dates to fetch: {len(missing_dates)} (skipping {len(all_weekdays) - len(missing_dates)} already in DB)")
if not missing_dates:
    print("[backfill] All dates already in DB. Nothing to do.")
    return
```

Additionally, `db.upsert_margin()` uses `ON CONFLICT(date, symbol, expiry, file_id) DO UPDATE SET ...`, so partial re-runs never create duplicates.

---

### Q4: DB Tracking in Git — ✅ `data/margins.db` IS tracked (not in `.gitignore`)

Complete `.gitignore` contents:

```
__pycache__/
*.pyc
*.pyo
.env
exports/
.DS_Store
debug_*.py
```

`data/`, `*.db`, and `margins.db` are **not listed**. The DB is intentionally tracked — the GitHub Actions workflow commits it back with `git add data/` after each daily fetch.

---

### Q5: GitHub Actions Workflow — ✅ All Four Items Present

**Cron schedule** (`.github/workflows/daily_margin.yml` line 5):
```yaml
- cron: '30 14 * * 1-5'  # 14:30 UTC = 8:00 PM IST, Mon-Fri
```
✅ Correct.

**Install Playwright + Chromium** (lines 22–25):
```yaml
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```
✅ Both the Python package and the browser binary + system deps are installed.

**Run main.py** (lines 28–29):
```yaml
python main.py $(date +%Y-%m-%d)
```
✅ Correct.

**Commit and push DB** (lines 31–39):
```yaml
git config user.email "github-actions[bot]@users.noreply.github.com"
git config user.name "github-actions[bot]"
git add data/
git diff --staged --quiet || git commit -m "data: daily margin $(date +%Y-%m-%d)"
git push
```
✅ Uses `contents: write` permission, guards against empty commits, uses built-in `GITHUB_TOKEN`.

---

### Q6: Recommendation for Backfill — Option B: Local Terminal

**`python3 backfill.py 2022-01-01` is the correct choice.**

GitHub Actions has a **6-hour job timeout**. A ~1,084-date backfill at 30–60 seconds per date requires **9–18 hours** of continuous runtime — the workflow would be killed partway through, and since it only commits at the end of the job, all progress would be lost.

`backfill.py` is specifically designed for long runs: it checks existing dates at startup, skips them, and writes to the DB continuously. Stop at any point with Ctrl+C, re-run the same command, and it resumes exactly where it left off. After completion, a single `git add data/margins.db && git commit && git push` uploads the full history.

---

### Q7: GO/NO-GO Assessment — ✅ GO

| Item | Status |
|---|---|
| Akamai bypass (homepage-first + stealth JS + realistic fingerprint) | ✅ |
| Symbol filter (NATURALGAS + NATGASMINI only) in both `main.py` and `backfill.py` | ✅ |
| Backfill resume safety (skips existing dates; upsert prevents duplicates) | ✅ |
| `data/margins.db` tracked in git (not in `.gitignore`) | ✅ |
| GitHub Actions: correct cron (14:30 UTC Mon-Fri) | ✅ |
| GitHub Actions: installs Playwright + Chromium | ✅ |
| GitHub Actions: runs `main.py` with today's date | ✅ |
| GitHub Actions: commits and pushes updated DB | ✅ |
| `requirements.txt` has all needed packages | ✅ |
| DB schema has `UNIQUE` constraint + upsert | ✅ |

**The repo is fully committed and ready. The daily automation is correctly wired. The only remaining task is the historical backfill, which must be run locally (not via GitHub Actions) due to the 6-hour job timeout constraint.**
