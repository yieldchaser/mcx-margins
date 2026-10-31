#!/usr/bin/env python3
"""
Empirical Return Distribution & Fat-Tail Leptokurtosis Engine.

Extracts roll-consistent front-month returns from data/prices.db,
computes higher central moments, adaptive Freedman-Diaconis binning,
continuous scaled Gaussian PDF overlays, clearinghouse shock multipliers,
and breakeven survival leverage matrices for NATURALGAS and NATGASMINI.

Output: docs/data/return_distribution.json
"""

import sys
import sqlite3
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parent
PRICE_DB_PATH = REPO_ROOT / "data" / "prices.db" if (REPO_ROOT / "data" / "prices.db").exists() else Path("data/prices.db")
MARGIN_DB_PATH = REPO_ROOT / "data" / "margins.db" if (REPO_ROOT / "data" / "margins.db").exists() else Path("data/margins.db")
OUT_DIR = REPO_ROOT / "docs" / "data" if (REPO_ROOT / "docs" / "data").parent.exists() else Path("docs/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

SYMBOLS_CONFIG = {
    "NATURALGAS": {
        "aliases": ("NATURALGAS", "NATGAS"),
        "lot_size": 1250,
        "default_vol_daily": 0.022935,
        "default_margin_pct": 14.48,
    },
    "NATGASMINI": {
        "aliases": ("NATGASMINI",),
        "lot_size": 250,
        "default_vol_daily": 0.022672,
        "default_margin_pct": 14.30,
    },
}

GAUSSIAN_TAIL_PROBS = {
    "beyond_1s": 31.73,
    "beyond_2s": 4.55,
    "beyond_3s": 0.27,
}


def compute_dte(expiry_str, ref_date_str):
    """Parse expiry like '26MAR2026' and return days from ref_date."""
    try:
        day = int(expiry_str[:2])
        mon = MONTH_MAP.get(expiry_str[2:5].upper())
        if not mon:
            return 9999
        yr = int(expiry_str[5:])
        if yr < 100:
            yr += 2000
        expiry_date = date(yr, mon, day)
        ref = date.fromisoformat(ref_date_str)
        return (expiry_date - ref).days
    except Exception:
        return 9999


def extract_front_month_series(conn_prices, symbol_aliases):
    """
    Extract date-sorted continuous front-month price records.
    Filters instrument='FUTCOM', dte >= 0, close > 0, prev_close > 0.
    Selects front contract on each date (minimal DTE >= 0).
    """
    placeholders = ",".join("?" for _ in symbol_aliases)
    query = f"""
        SELECT date, symbol, expiry, instrument, open, high, low, close, prev_close, volume_lots, open_interest
        FROM prices
        WHERE symbol IN ({placeholders})
          AND UPPER(COALESCE(instrument, '')) = 'FUTCOM'
        ORDER BY date ASC, expiry ASC
    """
    cur = conn_prices.cursor()
    rows = cur.execute(query, symbol_aliases).fetchall()

    by_date = {}
    for r in rows:
        d = r[0]
        exp = r[2]
        close = r[7]
        prev_close = r[8]
        if close is None or prev_close is None or prev_close <= 0 or close <= 0:
            continue
        dte = compute_dte(exp, d)
        if dte >= 0:
            by_date.setdefault(d, []).append((dte, exp, r))

    front_series = []
    for d in sorted(by_date.keys()):
        # Minimal DTE candidate (tie-break on expiry)
        best = min(by_date[d], key=lambda item: (item[0], item[1]))[2]
        front_series.append({
            "date": best[0],
            "symbol": best[1],
            "expiry": best[2],
            "close": float(best[7]),
            "prev_close": float(best[8]),
            "volume_lots": int(best[9]) if best[9] is not None else 0,
            "open_interest": int(best[10]) if best[10] is not None else 0,
            "dte": compute_dte(best[2], best[0]),
        })
    return front_series


def compute_distribution_metrics(returns_array):
    """
    Compute sample moments, quantiles, Freedman-Diaconis & fixed 0.50% bins,
    and continuous scaled Gaussian PDF overlay counts.
    """
    n = len(returns_array)
    if n < 4:
        return None

    r = np.asarray(returns_array, dtype=float)
    mu = float(np.mean(r))
    sorted_r = np.sort(r)
    median = float(sorted_r[n // 2] if n % 2 != 0 else (sorted_r[n // 2 - 1] + sorted_r[n // 2]) / 2.0)

    # Sample standard deviation (Bessel corrected N - 1)
    s = float(np.std(r, ddof=1))
    vol_ann = s * math.sqrt(252.0)

    # Central moments
    diff = r - mu
    m2 = float(np.mean(diff ** 2))
    m3 = float(np.mean(diff ** 3))
    m4 = float(np.mean(diff ** 4))

    # Fisher-Pearson Skewness
    g1 = m3 / (m2 ** 1.5) if m2 > 0 else 0.0
    g1_adj = (math.sqrt(n * (n - 1)) / (n - 2)) * g1 if n > 2 and m2 > 0 else g1

    # Sample Excess Kurtosis (Normal distribution = 0.0)
    g2 = (m4 / (m2 ** 2)) - 3.0 if m2 > 0 else 0.0
    g2_adj = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6.0) if n > 3 and m2 > 0 else g2

    # Quantiles
    q1 = float(np.percentile(r, 1))
    q5 = float(np.percentile(r, 5))
    q10 = float(np.percentile(r, 10))
    q25 = float(np.percentile(r, 25))
    q50 = median
    q75 = float(np.percentile(r, 75))
    q90 = float(np.percentile(r, 90))
    q95 = float(np.percentile(r, 95))
    q99 = float(np.percentile(r, 99))
    iqr = q75 - q25

    # Bin widths
    w_fd = float(max(0.001, 2.0 * iqr * (n ** (-1.0 / 3.0))))
    w_fixed = 0.0050  # Fixed 0.50%

    # Tail frequencies
    zs = (r - mu) / s if s > 0 else np.zeros_like(r)
    b1_obs = float((np.sum(np.abs(zs) > 1.0) / n) * 100.0)
    b2_obs = float((np.sum(np.abs(zs) > 2.0) / n) * 100.0)
    b3_obs = float((np.sum(np.abs(zs) > 3.0) / n) * 100.0)
    trm_3s = float(round(b3_obs / GAUSSIAN_TAIL_PROBS["beyond_3s"], 2)) if b3_obs > 0 else 0.0

    def generate_histogram(bin_width):
        min_v = float(np.min(r))
        max_v = float(np.max(r))
        k_min = int(math.floor(min_v / bin_width))
        k_max = int(math.ceil(max_v / bin_width))
        edges = [k * bin_width for k in range(k_min, k_max + 1)]
        counts, _ = np.histogram(r, bins=edges)

        labels = []
        bin_centers = []
        gaussian_fit = []
        factor = (n * bin_width) / (s * math.sqrt(2.0 * math.pi)) if s > 0 else 0.0

        for i in range(len(counts)):
            mid = (edges[i] + edges[i + 1]) / 2.0
            bin_centers.append(round(mid, 6))
            labels.append(f"{mid * 100.0:+.2f}%")
            z = (mid - mu) / s if s > 0 else 0.0
            c_x = factor * math.exp(-0.5 * z * z)
            gaussian_fit.append(round(c_x, 2))

        return {
            "bin_width": round(bin_width, 6),
            "bins": labels,
            "bin_centers": bin_centers,
            "counts": [int(c) for c in counts],
            "gaussian_fit": gaussian_fit,
        }

    return {
        "sample_size": n,
        "moments": {
            "mean": round(mu, 6),
            "median": round(median, 6),
            "std_dev": round(s, 6),
            "annualized_vol": round(vol_ann, 6),
            "skewness": round(g1, 6),
            "skewness_adjusted": round(g1_adj, 6),
            "excess_kurtosis": round(g2, 6),
            "excess_kurtosis_adjusted": round(g2_adj, 6),
        },
        "quantiles": {
            "p1": round(q1, 6),
            "p5": round(q5, 6),
            "p10": round(q10, 6),
            "p25": round(q25, 6),
            "p50": round(q50, 6),
            "p75": round(q75, 6),
            "p90": round(q90, 6),
            "p95": round(q95, 6),
            "p99": round(q99, 6),
            "iqr": round(iqr, 6),
        },
        "tail_frequencies": {
            "beyond_1s": {"observed_pct": round(b1_obs, 2), "gaussian_pct": GAUSSIAN_TAIL_PROBS["beyond_1s"]},
            "beyond_2s": {"observed_pct": round(b2_obs, 2), "gaussian_pct": GAUSSIAN_TAIL_PROBS["beyond_2s"]},
            "beyond_3s": {"observed_pct": round(b3_obs, 2), "gaussian_pct": GAUSSIAN_TAIL_PROBS["beyond_3s"], "trm": trm_3s},
        },
        "bins_fd": generate_histogram(w_fd),
        "bins_fixed": generate_histogram(w_fixed),
    }


def compute_stress_matrix(s, latest_price, latest_vol_daily, lot_size, rets_decimal):
    """
    Clearinghouse Volatility Shock & Breakeven Survival Leverage Matrix.
    z in [-4.0, -3.0, -2.0, -1.0, 0.0, +1.0, +2.0, +3.0, +4.0].
    """
    zs = [-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]
    matrix = []
    r = np.asarray(rets_decimal, dtype=float)
    mu = float(np.mean(r))
    sample_zs = (r - mu) / s if s > 0 else np.zeros_like(r)
    n = len(r)

    for z in zs:
        shock_pct = z * s * 100.0
        delta = abs(shock_pct) / 100.0
        gamma = math.sqrt(0.94 + 0.06 * (z ** 2))
        proj_vol_daily = latest_vol_daily * gamma
        proj_margin_pct = max(13.0, 6.45 * proj_vol_daily * 100.0)

        # Shocked price & contract value
        p_shock = latest_price * (1.0 + shock_pct / 100.0)
        contract_val = p_shock * lot_size
        rupee_margin = contract_val * (proj_margin_pct / 100.0)

        # Breakeven Survival Leverage
        m_pred = proj_margin_pct / 100.0
        l_long = 1.0 / (delta + (1.0 - delta) * m_pred)
        l_short = 1.0 / (delta + (1.0 + delta) * m_pred)

        # Historical count
        if z < 0:
            hist_cnt = int(np.sum(sample_zs <= z))
        elif z > 0:
            hist_cnt = int(np.sum(sample_zs >= z))
        else:
            hist_cnt = n

        matrix.append({
            "z_score": round(z, 1),
            "price_shock_pct": round(shock_pct, 2),
            "vol_multiplier": round(gamma, 4),
            "projected_vol_daily": round(proj_vol_daily, 5),
            "projected_margin_pct": round(proj_margin_pct, 2),
            "rupee_margin_lot": int(round(rupee_margin)),
            "survival_leverage_long": round(l_long, 2),
            "survival_leverage_short": round(l_short, 2),
            "historical_count": hist_cnt,
        })
    return matrix


def export_return_distribution(conn_prices=None, cur_margins=None):
    """
    Build and export docs/data/return_distribution.json.
    Can be invoked from scripts/export_json.py or standalone.
    """
    close_prices_conn = False
    if conn_prices is None:
        conn_prices = sqlite3.connect(PRICE_DB_PATH)
        close_prices_conn = True

    close_margins_conn = False
    if cur_margins is None and MARGIN_DB_PATH.exists():
        conn_m = sqlite3.connect(MARGIN_DB_PATH)
        cur_margins = conn_m.cursor()
        close_margins_conn = True

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols": {},
    }

    lookback_map = {
        "max": None,
        "5Y": 1260,
        "3Y": 756,
        "1Y": 252,
    }

    try:
        for sym, cfg in SYMBOLS_CONFIG.items():
            series = extract_front_month_series(conn_prices, cfg["aliases"])
            if not series:
                print(f"  [WARN] No price series found for {sym}")
                continue

            n_total = len(series)
            date_start = series[0]["date"]
            date_end = series[-1]["date"]
            latest_rec = series[-1]
            latest_price = latest_rec["close"]
            lot_size = cfg["lot_size"]

            # Query margins database for latest vol and initial margin matching front expiry
            latest_vol_daily = cfg["default_vol_daily"]
            latest_margin_pct = cfg["default_margin_pct"]
            if cur_margins is not None:
                try:
                    placeholders = ",".join("?" for _ in cfg["aliases"])
                    # First try exact match on front expiry
                    m_row = cur_margins.execute(f"""
                        SELECT initial_margin_pct, annualized_volatility, daily_volatility
                        FROM margins
                        WHERE symbol IN ({placeholders}) AND expiry = ?
                        ORDER BY date DESC
                        LIMIT 1
                    """, (*cfg["aliases"], latest_rec["expiry"])).fetchone()

                    if not m_row:
                        m_row = cur_margins.execute(f"""
                            SELECT initial_margin_pct, annualized_volatility, daily_volatility
                            FROM margins
                            WHERE symbol IN ({placeholders})
                            ORDER BY date DESC, expiry ASC
                            LIMIT 1
                        """, cfg["aliases"]).fetchone()

                    if m_row and m_row[0] is not None:
                        latest_margin_pct = float(m_row[0])
                    if m_row and len(m_row) > 2 and m_row[2] is not None and m_row[2] > 0:
                        latest_vol_daily = float(m_row[2])
                    elif m_row and m_row[1] is not None and m_row[1] > 0:
                        latest_vol_daily = float(m_row[1]) / math.sqrt(252.0)
                except Exception as ex:
                    print(f"  [WARN] Failed to read margins for {sym}: {ex}")

            # 1D Returns
            simple_1d = [((r["close"] - r["prev_close"]) / r["prev_close"]) for r in series]
            log_1d = [math.log(r["close"] / r["prev_close"]) for r in series]

            # 5D Returns (continuous front series)
            simple_5d, log_5d = [], []
            for i in range(5, len(series)):
                p_now = series[i]["close"]
                p_prior = series[i - 5]["close"]
                simple_5d.append((p_now - p_prior) / p_prior)
                log_5d.append(math.log(p_now / p_prior))

            # Primary distributions (1D Max lookback)
            primary_simple = compute_distribution_metrics(simple_1d)
            primary_log = compute_distribution_metrics(log_1d)

            # Stress matrix
            s_daily = primary_simple["moments"]["std_dev"]
            stress_mat = compute_stress_matrix(s_daily, latest_price, latest_vol_daily, lot_size, simple_1d)

            # Live session contextualizer
            latest_simple_pct = ((latest_rec["close"] - latest_rec["prev_close"]) / latest_rec["prev_close"]) * 100.0
            latest_log_pct = math.log(latest_rec["close"] / latest_rec["prev_close"]) * 100.0
            mu_1d = primary_simple["moments"]["mean"]
            z_latest = (latest_simple_pct / 100.0 - mu_1d) / s_daily if s_daily > 0 else 0.0
            percentile_latest = float(np.mean(np.array(simple_1d) <= (latest_simple_pct / 100.0)) * 100.0)
            hist_count_latest = int(np.sum(np.array(simple_1d) <= (latest_simple_pct / 100.0)))
            # Gaussian expected count below z: N * 0.5 * (1 + erf(z / sqrt(2)))
            gauss_prob = 0.5 * (1.0 + math.erf(z_latest / math.sqrt(2.0)))
            gauss_expected_count = int(round(n_total * gauss_prob))

            live_session_info = {
                "date": latest_rec["date"],
                "expiry": latest_rec["expiry"],
                "close": round(latest_price, 2),
                "prev_close": round(latest_rec["prev_close"], 2),
                "simple_return_pct": round(latest_simple_pct, 2),
                "log_return_pct": round(latest_log_pct, 2),
                "z_score": round(z_latest, 2),
                "percentile_rank": round(percentile_latest, 1),
                "historical_count": hist_count_latest,
                "gaussian_expected_count": gauss_expected_count,
            }

            # Build multi-horizon, multi-lookback slice trees
            horizons = {"1D": {}, "5D": {}}
            for lb_key, lb_n in lookback_map.items():
                s_slice = simple_1d[-lb_n:] if lb_n else simple_1d
                l_slice = log_1d[-lb_n:] if lb_n else log_1d
                horizons["1D"][lb_key] = {
                    "simple": compute_distribution_metrics(s_slice),
                    "log": compute_distribution_metrics(l_slice),
                }

            for lb_key, lb_n in lookback_map.items():
                if len(simple_5d) > 0:
                    s5_slice = simple_5d[-lb_n:] if lb_n else simple_5d
                    l5_slice = log_5d[-lb_n:] if lb_n else log_5d
                    horizons["5D"][lb_key] = {
                        "simple": compute_distribution_metrics(s5_slice),
                        "log": compute_distribution_metrics(l5_slice),
                    }

            sym_payload = {
                "sample_size": n_total,
                "date_range": {"start": date_start, "end": date_end},
                "latest_price": round(latest_price, 2),
                "latest_vol_daily": round(latest_vol_daily, 6),
                "latest_margin_pct": round(latest_margin_pct, 2),
                "lot_size": lot_size,
                "live_session": live_session_info,
                "simple_returns": primary_simple,
                "log_returns": primary_log,
                "stress_matrix": stress_mat,
                "horizons": horizons,
            }

            payload["symbols"][sym] = sym_payload

        # Write to docs/data/return_distribution.json
        out_file = OUT_DIR / "return_distribution.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"  [OK] Exported {out_file} ({out_file.stat().st_size:,} bytes)")
        return payload

    finally:
        if close_prices_conn and conn_prices:
            conn_prices.close()
        if close_margins_conn and cur_margins:
            try:
                cur_margins.connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    export_return_distribution()
