#!/usr/bin/env python3
"""
Export margins.db to JSON files for the MCX Margin Intelligence Web Dashboard.
Run: python export_json.py
Output: docs/data/*.json
"""

import sqlite3
import json
import math
import statistics
import urllib.request
from datetime import datetime, date, timezone
from pathlib import Path

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("  [WARN] numpy/scikit-learn not available — Items 1–9 advanced stats will be skipped")

DB_PATH = Path("data/margins.db")
PRICE_DB_PATH = Path("data/prices.db")
OUT_DIR = Path("docs/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MARKET_SCHEMA_VERSION = "1.0.0"
MARKET_SYMBOLS = ("NATURALGAS", "NATGASMINI")
MARKET_SYMBOL_KEYS = {"NATURALGAS": "ng", "NATGASMINI": "ngm"}
SOURCE_REGISTRY = {
    "margins": {
        "name": "MCX CCL margins",
        "db_path": str(DB_PATH),
        "tables": ["margins"],
        "namespace": "root",
        "grain": "date-symbol-expiry-file_id",
    },
    "market_futures": {
        "name": "MCX futures bhavcopy",
        "db_path": str(PRICE_DB_PATH),
        "tables": ["prices"],
        "namespace": "market",
        "grain": "date-symbol-expiry",
        "filter": "instrument='FUTCOM'",
    },
}


def save(filename, data):
    path = OUT_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [OK] {filename}")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
MONTH_NAMES = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def compute_dte(expiry_str, ref_date_str):
    """Parse expiry like '26MAR2026' and return days from ref_date."""
    try:
        day = int(expiry_str[:2])
        mon = MONTH_MAP[expiry_str[2:5]]
        yr = int(expiry_str[5:])
        expiry_date = date(yr, mon, day)
        ref = date.fromisoformat(ref_date_str)
        return (expiry_date - ref).days
    except Exception:
        return 9999


def safe_corr(x, y):
    n = min(len(x), len(y))
    if n < 2:
        return None
    x, y = x[:n], y[:n]
    try:
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den = math.sqrt(
            sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)
        )
        return round(num / den, 4) if den > 0 else None
    except Exception:
        return None


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value):
    if value is None:
        return None
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    f = _safe_float(value)
    return int(f) if f is not None else None


def _round(value, digits=4):
    f = _safe_float(value)
    return round(f, digits) if f is not None else None


def _mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _stdev(values):
    vals = [v for v in values if v is not None]
    return statistics.stdev(vals) if len(vals) >= 2 else None


def _percentile_rank(values, value):
    vals = sorted(v for v in values if v is not None)
    if not vals or value is None:
        return None
    return round(100 * sum(1 for v in vals if v <= value) / len(vals), 1)


def _zscore(value, history):
    vals = [v for v in history if v is not None]
    if value is None or len(vals) < 5:
        return None
    avg = sum(vals) / len(vals)
    sd = statistics.stdev(vals)
    return round((value - avg) / sd, 3) if sd > 0 else None


def _freshness_status(latest_date):
    if not latest_date:
        return {"label": "MISSING", "age_days": None}
    try:
        age = (date.today() - date.fromisoformat(latest_date)).days
    except ValueError:
        return {"label": "INVALID", "age_days": None}
    if age <= 1:
        label = "LIVE"
    elif age <= 5:
        label = "DELAYED"
    else:
        label = "STALE"
    return {"label": label, "age_days": age}


def _is_market_futures_row(row):
    symbol = str(row.get("symbol", "")).upper()
    instrument = str(row.get("instrument", "")).upper()
    return symbol in MARKET_SYMBOLS and instrument == "FUTCOM"


def _market_row_from_db(row):
    rec = dict(row)
    symbol = str(rec.get("symbol", "")).upper()
    if symbol == "NATGAS":
        symbol = "NATURALGAS"
    normalized = {
        "date": rec.get("date"),
        "symbol": symbol,
        "expiry": rec.get("expiry"),
        "instrument": rec.get("instrument"),
        "open": _round(rec.get("open"), 4),
        "high": _round(rec.get("high"), 4),
        "low": _round(rec.get("low"), 4),
        "close": _round(rec.get("close"), 4),
        "prev_close": _round(rec.get("prev_close"), 4),
        "volume_lots": _safe_int(rec.get("volume_lots")),
        "volume_kgs": _round(rec.get("volume_kgs"), 3),
        "value_lacs": _round(rec.get("value_lacs"), 3),
        "open_interest": _safe_int(rec.get("open_interest")),
    }
    normalized["dte"] = compute_dte(normalized["expiry"], normalized["date"])
    prev_close = normalized["prev_close"]
    close = normalized["close"]
    normalized["return_pct"] = (
        round(((close - prev_close) / prev_close) * 100, 4)
        if close is not None and prev_close not in (None, 0)
        else None
    )
    return normalized


def _select_front_month(rows, ref_date=None):
    candidates = []
    for row in rows:
        dte = row.get("dte")
        if dte is None and ref_date:
            dte = compute_dte(row.get("expiry", ""), ref_date)
        if dte is not None and dte >= 0:
            candidates.append((dte, row.get("expiry", ""), row))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def _enrich_market_history(rows):
    enriched = []
    closes, returns, volumes, open_interest = [], [], [], []
    for idx, row in enumerate(sorted(rows, key=lambda r: r["date"])):
        close = row.get("close")
        volume = row.get("volume_lots")
        oi = row.get("open_interest")
        ret = row.get("return_pct")
        prior_oi = open_interest[-1] if open_interest else None
        volume_hist = volumes[-20:]
        return_window = [v for v in returns[-19:] + [ret] if v is not None]
        oi_change = oi - prior_oi if oi is not None and prior_oi is not None else None
        oi_change_pct = (
            round((oi_change / prior_oi) * 100, 3)
            if oi_change is not None and prior_oi not in (None, 0)
            else None
        )
        vol_z = _zscore(volume, volume_hist)
        realized = _stdev(return_window)
        volume_pct = _percentile_rank(volumes[-252:], volume)
        oi_pct = _percentile_rank(open_interest[-252:], oi)
        liquidity_score = None
        if volume_pct is not None or oi_pct is not None:
            liquidity_score = round((volume_pct or 0) * 0.6 + (oi_pct or 0) * 0.4, 1)
        enriched_row = {
            **row,
            "return_pct": ret,
            "rolling_realized_vol_20d": round(realized * math.sqrt(252), 3) if realized is not None else None,
            "volume_z_20d": vol_z,
            "oi_change": oi_change,
            "oi_change_pct": oi_change_pct,
            "liquidity_score": liquidity_score,
        }
        if idx >= 5 and close is not None and closes[-5] not in (None, 0):
            enriched_row["return_5d_pct"] = round(((close - closes[-5]) / closes[-5]) * 100, 3)
        else:
            enriched_row["return_5d_pct"] = None
        enriched.append(enriched_row)
        closes.append(close)
        returns.append(ret)
        volumes.append(volume)
        open_interest.append(oi)
    return enriched


def _signal_severity(score):
    if score >= 75:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _make_signal(symbol, signal_id, label, score, lookback, features, reason, direction="NEUTRAL"):
    score = int(max(0, min(100, round(score))))
    return {
        "id": signal_id,
        "symbol": symbol,
        "label": label,
        "score": score,
        "severity": _signal_severity(score),
        "direction": direction,
        "lookback": lookback,
        "features": features,
        "reason": reason,
    }


def _build_market_signals(symbol, history_rows, joined_rows):
    if not history_rows:
        return []
    latest = history_rows[-1]
    signals = []
    ret_1d = latest.get("return_pct") or 0
    ret_5d = latest.get("return_5d_pct") or 0
    direction = "UP" if ret_5d > 0 else "DOWN" if ret_5d < 0 else "NEUTRAL"
    score = min(100, abs(ret_5d) * 10 + abs(ret_1d) * 12)
    signals.append(_make_signal(
        symbol,
        "price_momentum",
        "Price Momentum",
        score,
        "5 trading days",
        {"return_1d_pct": _round(ret_1d, 3), "return_5d_pct": _round(ret_5d, 3)},
        f"{symbol} front-month price is {direction.lower()} over 5 sessions with {ret_5d:.2f}% return.",
        direction,
    ))

    vol_z = latest.get("volume_z_20d")
    vol_score = min(100, abs(vol_z or 0) * 30)
    vol_label = "Volume Shock" if vol_score >= 60 else "Volume Normal"
    signals.append(_make_signal(
        symbol,
        "volume_shock",
        vol_label,
        vol_score,
        "20 trading days",
        {"volume_lots": latest.get("volume_lots"), "volume_z_20d": vol_z},
        f"Latest volume is {vol_z:.2f} standard deviations from its 20-day baseline." if vol_z is not None else "Insufficient volume history for z-score.",
        "UP" if (vol_z or 0) > 0 else "DOWN",
    ))

    oi_change_pct = latest.get("oi_change_pct")
    oi_score = min(100, abs(oi_change_pct or 0) * 6)
    oi_direction = "EXPANDING" if (oi_change_pct or 0) > 0 else "CONTRACTING" if (oi_change_pct or 0) < 0 else "FLAT"
    signals.append(_make_signal(
        symbol,
        "open_interest_shift",
        "Open Interest Shift",
        oi_score,
        "1 trading day",
        {"open_interest": latest.get("open_interest"), "oi_change_pct": oi_change_pct},
        f"Open interest is {oi_direction.lower()} by {oi_change_pct:.2f}% versus the prior front-month observation." if oi_change_pct is not None else "Open-interest change is unavailable.",
        oi_direction,
    ))

    liq = latest.get("liquidity_score")
    liq_score = 100 - liq if liq is not None else 0
    signals.append(_make_signal(
        symbol,
        "liquidity_stress",
        "Liquidity Stress",
        liq_score,
        "Trailing 252 observations",
        {"liquidity_score": liq, "volume_lots": latest.get("volume_lots"), "open_interest": latest.get("open_interest")},
        f"Liquidity score is {liq:.1f}; lower values indicate weaker volume and open-interest support." if liq is not None else "Insufficient liquidity history for scoring.",
        "STRESS" if liq_score >= 60 else "NORMAL",
    ))

    joined = [row for row in joined_rows if row.get("symbol") == symbol]
    if len(joined) >= 6:
        latest_join = joined[-1]
        prior = joined[-6]
        margin_now = latest_join.get("initial_margin_pct")
        margin_prior = prior.get("initial_margin_pct")
        margin_change = (
            margin_now - margin_prior
            if margin_now is not None and margin_prior is not None
            else None
        )
        price_return = latest_join.get("return_5d_pct")
        if price_return is None:
            price_now = latest_join.get("close")
            price_prior = prior.get("close")
            price_return = (
                ((price_now - price_prior) / price_prior) * 100
                if price_now is not None and price_prior not in (None, 0)
                else None
            )
        divergence = abs(price_return or 0) - abs(margin_change or 0)
        div_score = max(0, min(100, divergence * 12))
        signals.append(_make_signal(
            symbol,
            "margin_market_divergence",
            "Margin-Market Divergence",
            div_score,
            "5 trading days",
            {
                "price_return_5d_pct": _round(price_return, 3),
                "margin_change_5d_pct": _round(margin_change, 3),
            },
            "Price has moved materially more than initial margin over the same window." if div_score >= 45 else "Margin and market movement are broadly aligned.",
            "DIVERGING" if div_score >= 45 else "CONFIRMED",
        ))
    return signals


def _build_margin_front_series_for_symbol(cur, symbol):
    cur.execute("SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date", (symbol,))
    dates = [r[0] for r in cur.fetchall()]
    series = []
    for d in dates:
        cur.execute(
            """
            SELECT expiry, initial_margin_pct, total_margin_pct, elm_pct,
                   tender_margin_pct, daily_volatility, annualized_volatility
            FROM margins WHERE date=? AND symbol=?
            ORDER BY expiry ASC
            """,
            (d, symbol),
        )
        rows = []
        for row in cur.fetchall():
            rows.append({
                "date": d,
                "symbol": symbol,
                "expiry": row[0],
                "dte": compute_dte(row[0], d),
                "initial_margin_pct": row[1],
                "total_margin_pct": row[2],
                "elm_pct": row[3],
                "tender_margin_pct": row[4],
                "daily_volatility": row[5],
                "annualized_volatility": row[6],
            })
        best = _select_front_month(rows, d)
        if best:
            series.append(best)
    return series


def _market_validation(conn, latest_date, futures_rows):
    validation = {"status": "ok", "checks": []}

    def add_check(name, status, message, count=None):
        validation["checks"].append({
            "name": name,
            "status": status,
            "message": message,
            "count": count,
        })

    dupes = conn.execute(
        """
        SELECT date, symbol, expiry, COUNT(*) AS n
        FROM prices
        WHERE symbol IN ('NATURALGAS','NATGASMINI','NATGAS')
          AND UPPER(COALESCE(instrument,''))='FUTCOM'
        GROUP BY date, symbol, expiry
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    add_check("duplicate_futures_rows", "ok" if not dupes else "error", "No duplicate futures rows." if not dupes else "Duplicate futures rows detected.", len(dupes))

    impossible = [
        r for r in futures_rows
        if (r.get("close") is not None and r.get("close") <= 0)
        or (r.get("open") is not None and r.get("open") < 0)
        or (r.get("high") is not None and r.get("high") < 0)
        or (r.get("low") is not None and r.get("low") < 0)
    ]
    add_check("impossible_prices", "ok" if not impossible else "error", "All futures prices are positive where present." if not impossible else "Non-positive futures prices detected.", len(impossible))

    negative_volume = [
        r for r in futures_rows
        if (r.get("volume_lots") is not None and r.get("volume_lots") < 0)
        or (r.get("volume_kgs") is not None and r.get("volume_kgs") < 0)
        or (r.get("open_interest") is not None and r.get("open_interest") < 0)
    ]
    add_check("negative_volume_or_oi", "ok" if not negative_volume else "error", "Volume and open interest are non-negative." if not negative_volume else "Negative volume or open interest detected.", len(negative_volume))

    freshness = _freshness_status(latest_date)
    add_check("stale_source", "ok" if freshness["label"] in ("LIVE", "DELAYED") else "warn", f"Market data freshness: {freshness['label']}.", freshness["age_days"])

    for symbol in MARKET_SYMBOLS:
        dates = sorted({r["date"] for r in futures_rows if r["symbol"] == symbol})
        gaps = []
        if len(dates) >= 2:
            start, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
            seen = set(dates)
            cur = start
            while cur <= end:
                if cur.weekday() < 5 and cur.isoformat() not in seen:
                    gaps.append(cur.isoformat())
                cur = date.fromordinal(cur.toordinal() + 1)
        add_check(
            f"weekday_gaps_{symbol.lower()}",
            "ok" if len(gaps) <= 20 else "warn",
            "Weekday gaps are within expected holiday/backfill tolerance." if len(gaps) <= 20 else "Large number of weekday gaps detected; includes exchange holidays.",
            len(gaps),
        )

    if any(c["status"] == "error" for c in validation["checks"]):
        validation["status"] = "error"
    elif any(c["status"] == "warn" for c in validation["checks"]):
        validation["status"] = "warn"
    return validation


def _export_market_intelligence(margin_cur):
    outputs = []
    market_dir = OUT_DIR / "market"
    market_dir.mkdir(parents=True, exist_ok=True)
    contract_root = market_dir / "contract"
    contract_root.mkdir(parents=True, exist_ok=True)

    if not PRICE_DB_PATH.exists():
        missing = {
            "schema_version": MARKET_SCHEMA_VERSION,
            "status": "missing",
            "source": "market_futures",
            "message": f"{PRICE_DB_PATH} not found; market intelligence skipped.",
        }
        save("market/meta.json", missing)
        return {"status": "missing", "outputs": ["market/meta.json"], "latest_date": None}

    conn = sqlite3.connect(PRICE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = [
            _market_row_from_db(row)
            for row in conn.execute(
                """
                SELECT date, symbol, expiry, instrument, open, high, low, close,
                       prev_close, volume_lots, volume_kgs, value_lacs, open_interest
                FROM prices
                WHERE symbol IN ('NATURALGAS','NATGASMINI','NATGAS')
                  AND UPPER(COALESCE(instrument,''))='FUTCOM'
                ORDER BY symbol, date, expiry
                """
            ).fetchall()
        ]
        rows = [r for r in rows if _is_market_futures_row(r)]
        latest_date = max((r["date"] for r in rows), default=None)
        min_date = min((r["date"] for r in rows), default=None)
        validation = _market_validation(conn, latest_date, rows)
        freshness = _freshness_status(latest_date)

        symbol_counts = {}
        for symbol in MARKET_SYMBOLS:
            sym_rows = [r for r in rows if r["symbol"] == symbol]
            symbol_counts[symbol] = {
                "rows": len(sym_rows),
                "dates": len({r["date"] for r in sym_rows}),
                "expiries": len({r["expiry"] for r in sym_rows}),
                "first_date": min((r["date"] for r in sym_rows), default=None),
                "latest_date": max((r["date"] for r in sym_rows), default=None),
            }

        meta = {
            "schema_version": MARKET_SCHEMA_VERSION,
            "source": "market_futures",
            "status": validation["status"],
            "generated_at": _utc_now(),
            "latest_date": latest_date,
            "date_range": {"from": min_date, "to": latest_date},
            "freshness": freshness,
            "row_count": len(rows),
            "symbols": symbol_counts,
            "validation": validation,
        }
        save("market/meta.json", meta); outputs.append("market/meta.json")

        by_symbol_date = {symbol: {} for symbol in MARKET_SYMBOLS}
        for row in rows:
            by_symbol_date[row["symbol"]].setdefault(row["date"], []).append(row)

        histories = {}
        for symbol in MARKET_SYMBOLS:
            front_rows = []
            for d in sorted(by_symbol_date[symbol]):
                best = _select_front_month(by_symbol_date[symbol][d], d)
                if best:
                    front_rows.append(best)
            histories[symbol] = _enrich_market_history(front_rows)
            key = MARKET_SYMBOL_KEYS[symbol]
            save(f"market/history_{key}.json", {
                "schema_version": MARKET_SCHEMA_VERSION,
                "symbol": symbol,
                "rows": histories[symbol],
            })
            outputs.append(f"market/history_{key}.json")

        contract_histories = {}
        contract_row_lookup = {}
        for symbol in MARKET_SYMBOLS:
            by_expiry = {}
            for row in rows:
                if row["symbol"] == symbol:
                    by_expiry.setdefault(row["expiry"], []).append(row)
            for expiry, expiry_rows in by_expiry.items():
                enriched = _enrich_market_history(sorted(expiry_rows, key=lambda r: r["date"]))
                contract_histories[(symbol, expiry)] = enriched
                for enriched_row in enriched:
                    contract_row_lookup[(symbol, expiry, enriched_row["date"])] = enriched_row

        current = {"schema_version": MARKET_SCHEMA_VERSION, "as_of": latest_date}
        forward = {"schema_version": MARKET_SCHEMA_VERSION, "as_of": latest_date}
        for symbol in MARKET_SYMBOLS:
            active = sorted(
                [r for r in by_symbol_date[symbol].get(latest_date, []) if r["dte"] >= 0],
                key=lambda r: r["dte"],
            )
            volumes = [r.get("volume_lots") for r in active]
            ois = [r.get("open_interest") for r in active]
            front_close = active[0]["close"] if active else None
            curve = []
            for idx, row in enumerate(active):
                flow_row = contract_row_lookup.get((symbol, row["expiry"], row["date"]), {})
                volume_pct = _percentile_rank(volumes, row.get("volume_lots"))
                oi_pct = _percentile_rank(ois, row.get("open_interest"))
                liquidity_score = None
                if volume_pct is not None or oi_pct is not None:
                    liquidity_score = round((volume_pct or 0) * 0.6 + (oi_pct or 0) * 0.4, 1)
                entry = {
                    **row,
                    "rolling_realized_vol_20d": flow_row.get("rolling_realized_vol_20d"),
                    "volume_z_20d": flow_row.get("volume_z_20d"),
                    "oi_change": flow_row.get("oi_change"),
                    "oi_change_pct": flow_row.get("oi_change_pct"),
                    "spread_vs_front": _round(row["close"] - front_close, 4) if row.get("close") is not None and front_close is not None else None,
                    "spread_vs_next": _round(active[idx + 1]["close"] - row["close"], 4) if idx + 1 < len(active) and row.get("close") is not None and active[idx + 1].get("close") is not None else None,
                    "liquidity_score": liquidity_score,
                }
                curve.append(entry)
            ranked = sorted(curve, key=lambda r: (r.get("liquidity_score") is not None, r.get("liquidity_score") or -1), reverse=True)
            ranks = {id(row): i + 1 for i, row in enumerate(ranked)}
            for row in curve:
                row["liquidity_rank"] = ranks.get(id(row))
            current[symbol] = curve
            forward[symbol] = {
                "curve": curve,
                "curve_slope": _round(curve[-1]["close"] - curve[0]["close"], 4) if len(curve) >= 2 and curve[-1].get("close") is not None and curve[0].get("close") is not None else None,
                "front_to_back_tension": _round(((curve[-1]["close"] - curve[0]["close"]) / curve[0]["close"]) * 100, 3) if len(curve) >= 2 and curve[0].get("close") not in (None, 0) and curve[-1].get("close") is not None else None,
            }
        save("market/current.json", current); outputs.append("market/current.json")
        save("market/forward_curve.json", forward); outputs.append("market/forward_curve.json")

        contract_index = {"schema_version": MARKET_SCHEMA_VERSION, "ng": [], "ngm": []}
        for symbol in MARKET_SYMBOLS:
            key = MARKET_SYMBOL_KEYS[symbol]
            symbol_dir = contract_root / key
            symbol_dir.mkdir(parents=True, exist_ok=True)
            by_expiry = {}
            for row in rows:
                if row["symbol"] == symbol:
                    by_expiry.setdefault(row["expiry"], []).append(row)
            for expiry, expiry_rows in sorted(by_expiry.items()):
                enriched = contract_histories.get((symbol, expiry)) or _enrich_market_history(sorted(expiry_rows, key=lambda r: r["date"]))
                out_name = f"market/contract/{key}/{expiry}.json"
                save(out_name, {
                    "schema_version": MARKET_SCHEMA_VERSION,
                    "symbol": symbol,
                    "expiry": expiry,
                    "rows": enriched,
                })
                outputs.append(out_name)
                dates = [r["date"] for r in enriched]
                contract_index[key].append({
                    "expiry": expiry,
                    "obs": len(enriched),
                    "first_date": min(dates) if dates else None,
                    "last_date": max(dates) if dates else None,
                })
        save("market/contract_index.json", contract_index); outputs.append("market/contract_index.json")

        joined_symbols = {}
        flat_joined = []
        for symbol in MARKET_SYMBOLS:
            margin_series = _build_margin_front_series_for_symbol(margin_cur, symbol)
            market_by_date = {row["date"]: row for row in histories[symbol]}
            joined = []
            for m in margin_series:
                market = market_by_date.get(m["date"])
                if not market:
                    continue
                entry = {
                    "date": m["date"],
                    "symbol": symbol,
                    "margin_expiry": m["expiry"],
                    "market_expiry": market["expiry"],
                    "dte": m["dte"],
                    "initial_margin_pct": m["initial_margin_pct"],
                    "total_margin_pct": m["total_margin_pct"],
                    "daily_volatility": m["daily_volatility"],
                    "annualized_volatility": m["annualized_volatility"],
                    "close": market["close"],
                    "return_pct": market["return_pct"],
                    "return_5d_pct": market.get("return_5d_pct"),
                    "volume_lots": market["volume_lots"],
                    "volume_z_20d": market.get("volume_z_20d"),
                    "open_interest": market["open_interest"],
                    "oi_change_pct": market.get("oi_change_pct"),
                    "liquidity_score": market.get("liquidity_score"),
                }
                joined.append(entry)
                flat_joined.append(entry)
            joined_symbols[symbol] = joined
        save("market/margin_joined_front.json", {
            "schema_version": MARKET_SCHEMA_VERSION,
            "symbols": joined_symbols,
        })
        outputs.append("market/margin_joined_front.json")

        signals = {
            "schema_version": MARKET_SCHEMA_VERSION,
            "as_of": latest_date,
            "signals": [],
        }
        for symbol in MARKET_SYMBOLS:
            signals["signals"].extend(_build_market_signals(symbol, histories[symbol], flat_joined))
        save("market/signals.json", signals); outputs.append("market/signals.json")

        return {
            "status": validation["status"],
            "outputs": outputs,
            "latest_date": latest_date,
            "row_count": len(rows),
        }
    finally:
        conn.close()


def export_manifest():
    sources = {}
    for key, source in SOURCE_REGISTRY.items():
        source_info = dict(source)
        db_path = Path(source["db_path"])
        source_info["exists"] = db_path.exists()
        if db_path.exists():
            source_info["bytes"] = db_path.stat().st_size
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                table = source["tables"][0]
                cur.execute(f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table}")
                count, min_date, max_date = cur.fetchone()
                source_info["row_count"] = count
                source_info["date_range"] = {"from": min_date, "to": max_date}
                source_info["freshness"] = _freshness_status(max_date)
            except Exception as exc:
                source_info["error"] = str(exc)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        sources[key] = source_info

    datasets = []
    for path in sorted(OUT_DIR.rglob("*.json")):
        rel = path.relative_to(OUT_DIR).as_posix()
        if rel == "manifest.json":
            continue
        source = "market_futures" if rel.startswith("market/") else "margins"
        if rel == "hh_price.json":
            source = "external_henry_hub"
        datasets.append({
            "path": f"data/{rel}",
            "source": source,
            "schema_version": MARKET_SCHEMA_VERSION if rel.startswith("market/") else "legacy",
            "bytes": path.stat().st_size,
            "generated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })

    save("manifest.json", {
        "schema_version": "1.0.0",
        "generated_at": _utc_now(),
        "sources": sources,
        "datasets": datasets,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Items 1–9: Advanced analytics helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _build_front_month_series(cur):
    """Build date-sorted front-month NATURALGAS series with margin, vol, dte."""
    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol='NATURALGAS' ORDER BY date"
    )
    dates = [r[0] for r in cur.fetchall()]
    series = []
    for d in dates:
        cur.execute(
            """SELECT expiry, initial_margin_pct, total_margin_pct, elm_pct,
                      tender_margin_pct, daily_volatility, annualized_volatility
               FROM margins WHERE date=? AND symbol='NATURALGAS'
               ORDER BY expiry ASC""",
            (d,),
        )
        rows = cur.fetchall()
        best, best_dte = None, 99999
        for row in rows:
            dte = compute_dte(row[0], d)
            if 0 <= dte < best_dte:
                best_dte = dte
                best = row
        if best and best[1] is not None and best[5] is not None:
            series.append({
                "date": d,
                "year": int(d[:4]),
                "expiry": best[0],
                "dte": best_dte,
                "initial_margin_pct": best[1],
                "total_margin_pct": best[2],
                "elm_pct": best[3],
                "tender_margin_pct": best[4],
                "daily_volatility": best[5],
                "annualized_volatility": best[6],
            })
    return series


def _ols_fit(x, y):
    """Simple OLS: y = slope*x + intercept. Returns slope, intercept, r2."""
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    n = len(x)
    if n < 3:
        return 0.0, 0.0, 0.0
    mx, my = x.mean(), y.mean()
    ss_xy = ((x - mx) * (y - my)).sum()
    ss_xx = ((x - mx) ** 2).sum()
    if ss_xx == 0:
        return 0.0, my, 0.0
    slope = ss_xy / ss_xx
    intercept = my - slope * mx
    ss_res = ((y - (slope * x + intercept)) ** 2).sum()
    ss_tot = ((y - my) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(intercept), float(r2)


def _percentile(arr, pct):
    """Compute percentile of sorted array."""
    if not arr:
        return 0.0
    a = sorted(arr)
    k = (len(a) - 1) * pct / 100.0
    f = int(k)
    c = f + 1 if f + 1 < len(a) else f
    d = k - f
    return a[f] + d * (a[c] - a[f])


def _classify_regime(vol_daily_pct, year):
    """Regime A = structural (low-vol / pre-2019), Regime B = elevated."""
    vol_pct = vol_daily_pct * 100  # convert to percent
    if vol_pct >= 4.5 and year >= 2019:
        return "B"
    return "A"


# ── Item 3: Regime Detection ─────────────────────────────────────────────────
def _export_regime_model(cur, fm_series):
    """Fit per-regime OLS, tag rows, compute percentiles. Returns regime params dict."""
    print("  [Item 3] Regime detection & model...")

    a_x, a_y, b_x, b_y = [], [], [], []
    for row in fm_series:
        regime = _classify_regime(row["daily_volatility"], row["year"])
        row["regime"] = regime
        vol_pct = row["daily_volatility"] * 100
        margin = row["initial_margin_pct"]
        if regime == "A":
            a_x.append(vol_pct)
            a_y.append(margin)
        else:
            b_x.append(vol_pct)
            b_y.append(margin)

    slope_a, intercept_a, r2_a = _ols_fit(a_x, a_y)
    slope_b, intercept_b, r2_b = _ols_fit(b_x, b_y)

    # Residual std per regime
    res_a = [a_y[i] - (slope_a * a_x[i] + intercept_a) for i in range(len(a_x))]
    res_b = [b_y[i] - (slope_b * b_x[i] + intercept_b) for i in range(len(b_x))]
    sigma_a = float(np.std(res_a)) if res_a else 0.0
    sigma_b = float(np.std(res_b)) if res_b else 0.0

    # Percentiles: all-time and within current regime
    all_margins = [r["initial_margin_pct"] for r in fm_series]
    latest = fm_series[-1] if fm_series else None
    current_regime = latest["regime"] if latest else "B"
    regime_margins = [r["initial_margin_pct"] for r in fm_series if r["regime"] == current_regime]

    all_sorted = sorted(all_margins)
    regime_sorted = sorted(regime_margins)
    if latest:
        m = latest["initial_margin_pct"]
        pct_alltime = round(sum(1 for v in all_sorted if v <= m) / len(all_sorted) * 100)
        pct_regime = round(sum(1 for v in regime_sorted if v <= m) / len(regime_sorted) * 100)
    else:
        pct_alltime, pct_regime = 50, 50

    regime_params = {
        "regime_a": {"slope": round(slope_a, 4), "intercept": round(intercept_a, 4),
                     "r2": round(r2_a, 4), "n": len(a_x), "sigma": round(sigma_a, 4)},
        "regime_b": {"slope": round(slope_b, 4), "intercept": round(intercept_b, 4),
                     "r2": round(r2_b, 4), "n": len(b_x), "sigma": round(sigma_b, 4)},
        "current_regime": current_regime,
        "current_pct_alltime": pct_alltime,
        "current_pct_regime": pct_regime,
    }
    save("regime_model.json", regime_params)
    return regime_params


# ── Item 1: Forecast Bands ───────────────────────────────────────────────────
def _export_forecast_bands(fm_series, panic_entries, regime_params):
    """Compute ±1σ/±2σ prediction intervals from rolling residual std."""
    print("  [Item 1] Forecast bands...")

    # Compute residuals for historical predictions
    residuals = []
    for i in range(len(fm_series) - 1):
        today = fm_series[i]
        tomorrow = fm_series[i + 1]
        predicted = 0.886 * today["initial_margin_pct"] + 43.0 * today["daily_volatility"]
        actual = tomorrow["initial_margin_pct"]
        residuals.append(predicted - actual)

    # Rolling 30-day std of residuals (global fallback)
    window = 30
    if len(residuals) >= window:
        recent_residuals = residuals[-window:]
        rolling_sigma = float(np.std(recent_residuals))
    else:
        rolling_sigma = float(np.std(residuals)) if residuals else 1.0

    # FIX 15: DTE-bucketed residual std — near expiries get tighter sigma, far expiries wider
    residuals_by_dte = {"0-30": [], "31-90": [], "91+": []}
    for i in range(len(fm_series) - 1):
        today = fm_series[i]
        tomorrow = fm_series[i + 1]
        predicted = 0.886 * today["initial_margin_pct"] + 43.0 * today["daily_volatility"]
        actual = tomorrow["initial_margin_pct"]
        residual = predicted - actual
        dte = today["dte"]
        if dte <= 30:
            residuals_by_dte["0-30"].append(residual)
        elif dte <= 90:
            residuals_by_dte["31-90"].append(residual)
        else:
            residuals_by_dte["91+"].append(residual)

    sigma_by_bucket = {}
    for bucket, res in residuals_by_dte.items():
        # Use last 90 observations per bucket for sigma
        recent = res[-90:] if len(res) > 90 else res
        sigma_by_bucket[bucket] = float(np.std(recent)) if len(recent) >= 5 else rolling_sigma

    # Build forecast bands per expiry from panic_entries
    bands = []
    for entry in panic_entries:
        pred = entry["predicted_tomorrow"]
        dte = entry["dte"]
        # FIX 15: DTE-bucketed sigma — near expiries tighter, far expiries wider
        if dte <= 30:
            sigma = sigma_by_bucket["0-30"]
        elif dte <= 90:
            sigma = sigma_by_bucket["31-90"]
        else:
            sigma = sigma_by_bucket["91+"]
        if sigma == 0:
            sigma = rolling_sigma  # fallback to global
        bands.append({
            "expiry": entry["expiry"],
            "dte": dte,
            "current": entry["initial_margin_pct"],
            "predicted": pred,
            "sigma_1": round(sigma, 4),
            "sigma_2": round(2 * sigma, 4),
            "upper_1": round(pred + sigma, 3),
            "lower_1": round(pred - sigma, 3),
            "upper_2": round(pred + 2 * sigma, 3),
            "lower_2": round(pred - 2 * sigma, 3),
        })

    save("forecast_bands.json", {
        "rolling_sigma": round(rolling_sigma, 4),
        "window_days": window,
        "sigma_by_dte_bucket": {k: round(v, 4) for k, v in sigma_by_bucket.items()},
        "bands": bands,
    })


# ── Item 2: Model Health / Backtest Scorecard ────────────────────────────────
def _export_model_health(fm_series):
    """Compute directional accuracy, MAE, RMSE, interval hit rates."""
    print("  [Item 2] Model health scorecard...")

    # Build prediction vs actual pairs
    pairs = []
    residuals_all = []
    for i in range(len(fm_series) - 1):
        today = fm_series[i]
        tomorrow = fm_series[i + 1]
        predicted = 0.886 * today["initial_margin_pct"] + 43.0 * today["daily_volatility"]
        actual = tomorrow["initial_margin_pct"]
        pred_delta = predicted - today["initial_margin_pct"]
        actual_delta = actual - today["initial_margin_pct"]
        residual = predicted - actual
        residuals_all.append(residual)
        pairs.append({
            "pred_delta": pred_delta,
            "actual_delta": actual_delta,
            "predicted": predicted,
            "actual": actual,
            "residual": residual,
        })

    # Rolling sigma for interval checks
    def rolling_sigma_at(idx, window=30):
        start = max(0, idx - window)
        chunk = [p["residual"] for p in pairs[start:idx]]
        return float(np.std(chunk)) if len(chunk) >= 5 else float(np.std(residuals_all))

    def compute_metrics(recent_pairs, offset):
        if not recent_pairs:
            return None
        n = len(recent_pairs)
        dir_correct = sum(1 for p in recent_pairs
                          if (p["pred_delta"] > 0 and p["actual_delta"] > 0) or
                             (p["pred_delta"] < 0 and p["actual_delta"] < 0) or
                             (abs(p["pred_delta"]) < 0.01 and abs(p["actual_delta"]) < 0.01))
        errors = [abs(p["predicted"] - p["actual"]) for p in recent_pairs]
        sq_errors = [e ** 2 for e in errors]
        mae = sum(errors) / n
        rmse = math.sqrt(sum(sq_errors) / n)

        # Interval hit rates
        hits_1s, hits_2s = 0, 0
        for j, p in enumerate(recent_pairs):
            idx = offset + j
            sigma = rolling_sigma_at(idx)
            if abs(p["residual"]) <= sigma:
                hits_1s += 1
            if abs(p["residual"]) <= 2 * sigma:
                hits_2s += 1

        return {
            "directional_accuracy": round(dir_correct / n * 100, 1),
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "interval_hit_rate_1sigma": round(hits_1s / n * 100, 1),
            "interval_hit_rate_2sigma": round(hits_2s / n * 100, 1),
            "n": n,
        }

    result = {}
    for label, days in [("30d", 30), ("90d", 90), ("365d", 365)]:
        if len(pairs) >= days:
            offset = len(pairs) - days
            result[label] = compute_metrics(pairs[-days:], offset)
        elif pairs:
            result[label] = compute_metrics(pairs, 0)
        else:
            result[label] = None

    save("model_health.json", result)


# ── Item 4: Delta Distribution ───────────────────────────────────────────────
def _export_delta_distribution(fm_series):
    """Compute daily margin change histogram by DTE bucket."""
    print("  [Item 4] Delta distribution...")

    # Compute deltas
    deltas_by_bucket = {"0-30": [], "31-90": [], "91+": []}
    deltas_by_quartile = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}

    for i in range(len(fm_series) - 1):
        today = fm_series[i]
        tomorrow = fm_series[i + 1]
        delta = tomorrow["initial_margin_pct"] - today["initial_margin_pct"]
        dte = today["dte"]
        margin = today["initial_margin_pct"]

        if dte <= 30:
            deltas_by_bucket["0-30"].append(delta)
        elif dte <= 90:
            deltas_by_bucket["31-90"].append(delta)
        else:
            deltas_by_bucket["91+"].append(delta)

        if margin < 17:
            deltas_by_quartile["Q1"].append(delta)
        elif margin < 22:
            deltas_by_quartile["Q2"].append(delta)
        elif margin < 28:
            deltas_by_quartile["Q3"].append(delta)
        else:
            deltas_by_quartile["Q4"].append(delta)

    def build_histogram(vals):
        if not vals:
            return {"bins": [], "counts": [], "percentiles": {}}
        bins = []
        bin_width = 0.25
        edges = [round(-5.0 + i * bin_width, 2) for i in range(int(10.0 / bin_width) + 1)]
        counts = [0] * (len(edges) + 1)  # +1 for overflow on each side
        labels = ["<-5.0"]
        for j in range(len(edges) - 1):
            labels.append(f"{edges[j]:.2f}")
        labels.append(">5.0")

        for v in vals:
            if v < -5.0:
                counts[0] += 1
            elif v >= 5.0:
                counts[-1] += 1
            else:
                idx = int((v + 5.0) / bin_width) + 1
                idx = min(idx, len(counts) - 2)
                counts[idx] += 1

        sorted_vals = sorted(vals)
        pcts = {}
        for p in [5, 10, 25, 50, 75, 90, 95]:
            pcts[f"P{p}"] = round(_percentile(sorted_vals, p), 3)

        return {"bins": labels, "counts": counts, "percentiles": pcts, "n": len(vals)}

    histograms = {}
    for bucket, vals in deltas_by_bucket.items():
        histograms[bucket] = build_histogram(vals)

    conditional = {}
    for q, vals in deltas_by_quartile.items():
        if vals:
            sv = sorted(vals)
            conditional[q] = {
                "P10": round(_percentile(sv, 10), 3),
                "P50": round(_percentile(sv, 50), 3),
                "P90": round(_percentile(sv, 90), 3),
                "n": len(vals),
            }

    # Determine current quartile
    latest = fm_series[-1] if fm_series else None
    current_q = "Q2"
    if latest:
        m = latest["initial_margin_pct"]
        if m < 17: current_q = "Q1"
        elif m < 22: current_q = "Q2"
        elif m < 28: current_q = "Q3"
        else: current_q = "Q4"

    save("delta_distribution.json", {
        "histograms": histograms,
        "conditional": conditional,
        "current_quartile": current_q,
        "current_margin": round(latest["initial_margin_pct"], 2) if latest else 0,
    })


# ── Item 5: Forward Curve Confidence Cone ────────────────────────────────────
def _export_curve_cone(cur, fwd, latest_date):
    """Compute P10/P50/P90 at equivalent DTE for each active expiry."""
    print("  [Item 5] Forward curve confidence cone...")

    # Fetch all NATURALGAS history with DTE
    cur.execute(
        """SELECT date, expiry, total_margin_pct, daily_volatility
           FROM margins WHERE symbol='NATURALGAS' AND total_margin_pct IS NOT NULL"""
    )
    hist_rows = cur.fetchall()
    # Build DTE→margin mapping
    dte_margin_all = []
    dte_margin_recent = []  # last 5 years
    cutoff_year = int(latest_date[:4]) - 5

    for row in hist_rows:
        d, exp, tm, dv = row
        dte = compute_dte(exp, d)
        if dte < 0 or dte > 400:
            continue
        dte_margin_all.append((dte, tm))
        if int(d[:4]) >= cutoff_year:
            dte_margin_recent.append((dte, tm))

    def cone_at_dte(target_dte, data):
        window = 15
        vals = [tm for dte, tm in data if abs(dte - target_dte) <= window]
        if len(vals) < 5:
            vals = [tm for dte, tm in data if abs(dte - target_dte) <= 30]
        if not vals:
            return None, None, None, None
        sv = sorted(vals)
        p10 = round(_percentile(sv, 10), 2)
        p50 = round(_percentile(sv, 50), 2)
        p90 = round(_percentile(sv, 90), 2)
        # Current percentile within this DTE bucket
        return p10, p50, p90, len(sv)

    ng_fwd = fwd.get("NATURALGAS", [])
    cone = []
    for contract in ng_fwd:
        dte = contract["dte"]
        current = contract["total_margin_pct"]
        p10_all, p50_all, p90_all, n_all = cone_at_dte(dte, dte_margin_all)
        p10_rec, p50_rec, p90_rec, n_rec = cone_at_dte(dte, dte_margin_recent)

        # Compute percentile of current within all-time bucket
        vals_at_dte = sorted([tm for d, tm in dte_margin_all if abs(d - dte) <= 15])
        hist_pct = round(sum(1 for v in vals_at_dte if v <= current) / len(vals_at_dte) * 100) if vals_at_dte else 50

        # Trailing 5Y percentile — no hardcoded year, uses rolling dte_margin_recent
        vals_at_dte_rec = sorted([tm for d, tm in dte_margin_recent if abs(d - dte) <= 15])
        if not vals_at_dte_rec:
            vals_at_dte_rec = sorted([tm for d, tm in dte_margin_recent if abs(d - dte) <= 30])
        hist_pct_recent = round(sum(1 for v in vals_at_dte_rec if v <= current) / len(vals_at_dte_rec) * 100) if vals_at_dte_rec else hist_pct

        cone.append({
            "expiry": contract["expiry"],
            "dte": dte,
            "current": current,
            "p10_alltime": p10_all, "p50_alltime": p50_all, "p90_alltime": p90_all, "n_alltime": n_all,
            "p10_recent": p10_rec, "p50_recent": p50_rec, "p90_recent": p90_rec, "n_recent": n_rec,
            "hist_pct": hist_pct,
            "hist_pct_recent": hist_pct_recent,
        })

    save("curve_cone.json", {"as_of": latest_date, "cone": cone})


# ── Item 6: Structural vs Policy Buffer Decomposition ────────────────────────
def _export_decomposition(fm_series, regime_params):
    """Decompose margin into vol-implied (fair) and policy buffer."""
    print("  [Item 6] Margin decomposition...")

    rp = regime_params["regime_b"]
    slope, intercept = rp["slope"], rp["intercept"]

    # Last 365 days
    recent = fm_series[-365:] if len(fm_series) >= 365 else fm_series
    ts = []
    buffers = []
    for row in recent:
        vol_pct = row["daily_volatility"] * 100
        fair = slope * vol_pct + intercept
        actual = row["initial_margin_pct"]
        buf = actual - fair
        buffers.append(buf)
        ts.append({
            "date": row["date"],
            "actual": round(actual, 3),
            "fair_margin": round(fair, 3),
            "policy_buffer": round(buf, 3),
        })

    # Buffer percentile for today
    sorted_bufs = sorted(buffers)
    latest_buf = buffers[-1] if buffers else 0
    buf_pct = round(sum(1 for v in sorted_bufs if v <= latest_buf) / len(sorted_bufs) * 100) if sorted_bufs else 50

    save("decomposition.json", {
        "slope": slope, "intercept": intercept,
        "today": {
            "actual": ts[-1]["actual"] if ts else 0,
            "fair_margin": ts[-1]["fair_margin"] if ts else 0,
            "policy_buffer": ts[-1]["policy_buffer"] if ts else 0,
            "buffer_percentile": buf_pct,
        },
        "timeseries": ts,
    })


# ── Item 7: Seasonality Box Plots ────────────────────────────────────────────
def _export_seasonality_boxplot(cur):
    """Compute box plot stats per month using FRONT-MONTH margin per date.

    FIX 9: Previously aggregated ALL expiry rows, which included tender-period
    contracts (100% margin) and far-out contracts (near-0%), making the min/max
    meaningless. Now we select the single front-month contract per date
    (lowest DTE >= 0) to represent daily margin conditions accurately.
    """
    print("  [Item 7] Seasonality boxplots (front-month per date)...")

    cur.execute(
        """SELECT DISTINCT date FROM margins WHERE symbol='NATURALGAS' ORDER BY date"""
    )
    all_dates = [r[0] for r in cur.fetchall()]

    month_vals_all = {}
    month_vals_5y = {}
    current_year = date.today().year

    for d in all_dates:
        yr = int(d[:4])
        mon = int(d[5:7])
        cur.execute(
            """SELECT expiry, initial_margin_pct FROM margins
               WHERE date=? AND symbol='NATURALGAS' AND initial_margin_pct IS NOT NULL""",
            (d,)
        )
        rows = cur.fetchall()
        # Pick front-month: smallest DTE >= 0
        best_val = None
        best_dte = 99999
        for row in rows:
            dte = compute_dte(row[0], d)
            if 0 <= dte < best_dte:
                best_dte = dte
                best_val = row[1]
        if best_val is None:
            continue
        month_vals_all.setdefault(mon, []).append(best_val)
        if yr >= current_year - 5:
            month_vals_5y.setdefault(mon, []).append(best_val)

    def box_stats(vals):
        if not vals:
            return None
        sv = sorted(vals)
        n = len(sv)
        return {
            "min": round(sv[0], 2),
            "p10": round(_percentile(sv, 10), 2),
            "p25": round(_percentile(sv, 25), 2),
            "median": round(_percentile(sv, 50), 2),
            "p75": round(_percentile(sv, 75), 2),
            "p90": round(_percentile(sv, 90), 2),
            "max": round(sv[-1], 2),
            "mean": round(sum(sv) / n, 2),
            "std": round(float(np.std(sv)), 2),
            "n": n,
        }

    result = {"all_years": [], "last_5_years": []}
    for m in range(1, 13):
        name = MONTH_NAMES[m]
        result["all_years"].append({"month": name, "month_num": m, **(box_stats(month_vals_all.get(m, [])) or {})})
        result["last_5_years"].append({"month": name, "month_num": m, **(box_stats(month_vals_5y.get(m, [])) or {})})

    save("seasonality_boxplot.json", result)


# ── Item 8: Stress Score ─────────────────────────────────────────────────────
def _export_stress_score(cur, fm_series, latest_date):
    """Compute composite 0-100 stress score from margin + vol percentiles."""
    print("  [Item 8] Stress score...")

    # Trailing 5-year data for percentile baselines
    cutoff_year = int(latest_date[:4]) - 5
    recent = [r for r in fm_series if r["year"] >= cutoff_year]

    all_margins = sorted([r["initial_margin_pct"] for r in recent])
    all_vols = sorted([r["daily_volatility"] * 100 for r in recent])

    latest = fm_series[-1] if fm_series else None
    if latest:
        m = latest["initial_margin_pct"]
        v = latest["daily_volatility"] * 100
        margin_pct = round(sum(1 for x in all_margins if x <= m) / len(all_margins) * 100) if all_margins else 50
        vol_pct = round(sum(1 for x in all_vols if x <= v) / len(all_vols) * 100) if all_vols else 50
        score = round(0.5 * margin_pct + 0.5 * vol_pct)
    else:
        margin_pct, vol_pct, score = 50, 50, 50

    if score < 40:
        label = "CALM"
    elif score < 60:
        label = "NORMAL"
    elif score < 75:
        label = "MONITOR"
    elif score < 90:
        label = "ELEVATED"
    else:
        label = "STRESS"

    stress_data = {
        "stress_score": score,
        "stress_label": label,
        "margin_pct": margin_pct,
        "vol_pct": vol_pct,
    }

    # Save standalone + patch into current.json
    save("stress_score.json", stress_data)


# ── Item 9: Event Probabilities (Logistic Model) ─────────────────────────────
def _export_event_probabilities(cur, fm_series, panic_entries, regime_params):
    """Train logistic regression for P(hike)/P(cut) and emit per-expiry probabilities."""
    print("  [Item 9] Event probabilities...")

    rp_b = regime_params["regime_b"]
    slope_b, intercept_b = rp_b["slope"], rp_b["intercept"]

    # Build training data from fm_series
    # Features: margin, vol_pct, dte, margin_percentile, days_since_last_change, policy_buffer
    all_margins_sorted = sorted([r["initial_margin_pct"] for r in fm_series])
    n_total = len(all_margins_sorted)

    def margin_percentile(m):
        return sum(1 for v in all_margins_sorted if v <= m) / n_total * 100 if n_total else 50

    rows_X = []
    rows_y_hike = []
    rows_y_cut = []
    last_change_day = 0

    for i in range(len(fm_series) - 1):
        today = fm_series[i]
        tomorrow = fm_series[i + 1]
        delta = tomorrow["initial_margin_pct"] - today["initial_margin_pct"]

        vol_pct = today["daily_volatility"] * 100
        fair = slope_b * vol_pct + intercept_b
        policy_buf = today["initial_margin_pct"] - fair

        if abs(delta) > 0.1:
            last_change_day = 0
        else:
            last_change_day += 1

        features = [
            today["initial_margin_pct"],
            vol_pct,
            min(today["dte"], 300),
            margin_percentile(today["initial_margin_pct"]),
            min(last_change_day, 60),
            policy_buf,
        ]
        rows_X.append(features)
        rows_y_hike.append(1 if delta > 0.5 else 0)
        rows_y_cut.append(1 if delta < -0.5 else 0)

    if len(rows_X) < 100:
        print("  [Item 9] Not enough data for logistic model")
        save("event_probabilities.json", {"error": "insufficient data"})
        return

    X = np.array(rows_X)
    y_hike = np.array(rows_y_hike)
    y_cut = np.array(rows_y_cut)

    # Walk-forward: train on last 365d window, evaluate
    eval_window = min(365, len(X) - 365)
    if eval_window < 30:
        eval_window = min(90, len(X) // 2)

    train_end = len(X) - eval_window
    X_train, X_test = X[:train_end], X[train_end:]
    y_hike_train, y_hike_test = y_hike[:train_end], y_hike[train_end:]
    y_cut_train, y_cut_test = y_cut[:train_end], y_cut[train_end:]

    # Train models
    lr_hike = LogisticRegression(max_iter=1000, C=1.0)
    lr_cut = LogisticRegression(max_iter=1000, C=1.0)

    # Ensure both classes present
    if y_hike_train.sum() < 5 or (1 - y_hike_train).sum() < 5:
        print("  [Item 9] Hike class imbalance too severe")
        save("event_probabilities.json", {"error": "class imbalance"})
        return

    lr_hike.fit(X_train, y_hike_train)
    lr_cut.fit(X_train, y_cut_train)

    # Brier scores on test set
    p_hike_test = lr_hike.predict_proba(X_test)[:, 1]
    p_cut_test = lr_cut.predict_proba(X_test)[:, 1]
    brier_hike = float(np.mean((p_hike_test - y_hike_test) ** 2))
    brier_cut = float(np.mean((p_cut_test - y_cut_test) ** 2))

    # Retrain on ALL data for production predictions
    lr_hike.fit(X, y_hike)
    lr_cut.fit(X, y_cut)

    # Predict for each current expiry
    latest = fm_series[-1]
    latest_margin_pct_rank = margin_percentile(latest["initial_margin_pct"])

    per_expiry = []
    for entry in panic_entries:
        vol_pct = (entry["vol_daily"] if entry["vol_daily"] else latest["daily_volatility"]) * 100
        fair = slope_b * vol_pct + intercept_b
        policy_buf = entry["initial_margin_pct"] - fair   # use initial, matching training
        feat = np.array([[
            entry["initial_margin_pct"],   # use initial, matching training feature
            vol_pct,
            min(entry["dte"], 300),
            latest_margin_pct_rank,
            0,  # days_since_last_change unknown per-expiry; use 0
            policy_buf,
        ]])
        p_h = float(lr_hike.predict_proba(feat)[0, 1])
        p_c = float(lr_cut.predict_proba(feat)[0, 1])
        p_f = max(0, 1.0 - p_h - p_c)
        # Normalize
        total = p_h + p_c + p_f
        if total > 0:
            p_h, p_c, p_f = p_h / total, p_c / total, p_f / total

        per_expiry.append({
            "expiry": entry["expiry"],
            "dte": entry["dte"],
            "p_hike": round(p_h, 3),
            "p_cut": round(p_c, 3),
            "p_flat": round(p_f, 3),
        })

    # Serialize model coefficients
    coefficients = {
        "hike": {
            "coef": lr_hike.coef_[0].tolist(),
            "intercept": float(lr_hike.intercept_[0]),
            "features": ["margin_pct", "vol_pct", "dte", "margin_percentile", "days_since_change", "policy_buffer"],
        },
        "cut": {
            "coef": lr_cut.coef_[0].tolist(),
            "intercept": float(lr_cut.intercept_[0]),
            "features": ["margin_pct", "vol_pct", "dte", "margin_percentile", "days_since_change", "policy_buffer"],
        },
    }

    save("event_probabilities.json", {
        "per_expiry": per_expiry,
        "brier_hike": round(brier_hike, 4),
        "brier_cut": round(brier_cut, 4),
        "n_train": len(X),
        "coefficients": coefficients,
    })


def main():
    print("MCX Margin Dashboard — JSON Export")
    print("=" * 40)
    conn = get_conn()
    cur = conn.cursor()

    # ── meta.json ──────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM margins")
    count, min_date, max_date = cur.fetchone()
    save(
        "meta.json",
        {
            "last_updated": max_date,
            "total_records": count,
            "date_range": {"from": min_date, "to": max_date},
        },
    )

    # ── current.json ──────────────────────────────────────────────────────────
    latest_date = max_date  # already fetched above
    result = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    seen_cur: dict = {"NATURALGAS": set(), "NATGASMINI": set()}  # dedup by expiry
    cur.execute(
        """
        SELECT symbol, expiry, initial_margin_pct, elm_pct, tender_margin_pct,
               total_margin_pct, additional_long_margin_pct, additional_short_margin_pct,
               special_long_margin_pct, special_short_margin_pct, delivery_margin_pct,
               daily_volatility, annualized_volatility
        FROM margins WHERE date = ?
        ORDER BY symbol, expiry
        """,
        (latest_date,),
    )
    for row in cur.fetchall():
        sym = row[0]
        expiry = row[1]
        if sym not in result or expiry in seen_cur.get(sym, set()):
            continue
        seen_cur[sym].add(expiry)
        dte = compute_dte(expiry, latest_date)
        entry = {
            "expiry": expiry,
            "dte": dte,
            "initial_margin_pct": row[2],
            "elm_pct": row[3],
            "tender_margin_pct": row[4],
            "total_margin_pct": row[5],
            "additional_long_margin_pct": row[6],
            "additional_short_margin_pct": row[7],
            "special_long_margin_pct": row[8],
            "special_short_margin_pct": row[9],
            "delivery_margin_pct": row[10],
            "daily_volatility": row[11],
            "annualized_volatility": row[12],
        }
        result[sym].append(entry)
    # Sort by DTE ascending
    for sym in ["NATURALGAS", "NATGASMINI"]:
        result[sym].sort(key=lambda x: x["dte"])
    save("current.json", result)

    # ── history_ng.json + history_ngm.json (front-month daily series) ─────────
    for sym, fname in [("NATURALGAS", "history_ng.json"), ("NATGASMINI", "history_ngm.json")]:
        cur.execute(
            "SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date", (sym,)
        )
        dates = [r[0] for r in cur.fetchall()]
        series = []
        for d in dates:
            cur.execute(
                """
                SELECT expiry, initial_margin_pct, total_margin_pct, elm_pct,
                       tender_margin_pct, daily_volatility, annualized_volatility
                FROM margins WHERE date=? AND symbol=?
                ORDER BY expiry ASC
                """,
                (d, sym),
            )
            rows = cur.fetchall()
            best = None
            best_dte = 99999
            for row in rows:
                dte = compute_dte(row[0], d)
                if 0 <= dte < best_dte:
                    best_dte = dte
                    best = row
            if best:
                series.append(
                    {
                        "date": d,
                        "expiry": best[0],
                        "dte": best_dte,
                        "initial_margin_pct": best[1],
                        "total_margin_pct": best[2],
                        "elm_pct": best[3],
                        "tender_margin_pct": best[4],
                        "daily_volatility": best[5],
                        "annualized_volatility": best[6],
                    }
                )
        save(fname, series)

    # ── contract_index.json + per-contract docs/data/contract/<EXPIRY>.json ───
    # Two-tier lazy loading: index (~31 KB) loaded once for dropdown;
    # individual contract file (~75 KB avg) fetched only when contract selected.
    # Self-sustaining: new contracts in margins.db get their own file on next run.
    from pathlib import Path as _Path
    _cdir = _Path(OUT_DIR) / "contract"
    _cdir.mkdir(parents=True, exist_ok=True)
    _SYM_MAP = {"NATURALGAS": "ng", "NATGASMINI": "ngm"}
    _cidx = {"ng": [], "ngm": []}
    for _sym, _skey in _SYM_MAP.items():
        cur.execute(
            """
            SELECT date, expiry, initial_margin_pct, total_margin_pct, elm_pct,
                   tender_margin_pct, daily_volatility, annualized_volatility
            FROM margins
            WHERE symbol=? AND initial_margin_pct IS NOT NULL
            ORDER BY expiry ASC, date ASC
            """,
            (_sym,),
        )
        _bexp = {}
        for _r in cur.fetchall():
            _exp = _r[1]
            if _exp not in _bexp:
                _bexp[_exp] = []
            _dv, _av = _r[6], _r[7]
            _bexp[_exp].append({
                "date": _r[0],
                "dte": compute_dte(_exp, _r[0]),
                "initial_margin_pct": _r[2],
                "total_margin_pct": _r[3],
                "elm_pct": _r[4],
                "tender_margin_pct": _r[5],
                "daily_volatility": round(_dv * 100, 4) if _dv is not None else None,
                "annualized_volatility": round(_av * 100, 4) if _av is not None else None,
            })
        for _exp, _rows in _bexp.items():
            with open(_cdir / f"{_exp}.json", "w") as _f:
                json.dump({"expiry": _exp, "symbol": _sym, "rows": _rows},
                          _f, separators=(",", ":"))
            _ds = [rr["date"] for rr in _rows]
            _cidx[_skey].append({
                "expiry": _exp, "obs": len(_rows),
                "first_date": min(_ds), "last_date": max(_ds),
            })
        _cidx[_skey].sort(key=lambda x: x["expiry"])
    save("contract_index.json", _cidx)

    # ── seasonal_month.json ───────────────────────────────────────────────────
    # Use inner GROUP BY (date, expiry) to deduplicate — margins has 3 rows per (date,symbol,expiry).
    # Outer aggregation then gives correct counts and averages.
    cur.execute(
        """
        SELECT strftime('%m', date) as mon,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM (
            SELECT strftime('%m', date) as date, expiry,
                   initial_margin_pct, total_margin_pct
            FROM margins WHERE symbol='NATURALGAS'
            GROUP BY date, expiry
        )
        GROUP BY mon ORDER BY mon
        """,
    )
    seasonal_month = []
    for row in cur.fetchall():
        m = int(row[0])
        seasonal_month.append(
            {
                "month": MONTH_NAMES[m],
                "month_num": m,
                "avg_initial_margin": round(row[1], 3),
                "avg_total_margin": round(row[2], 3),
                "count": row[3],
                "min": round(row[4], 3),
                "max": round(row[5], 3),
            }
        )
    save("seasonal_month.json", seasonal_month)

    # Standard deviation per month — deduplicated (date, expiry) raw values
    cur.execute(
        """
        SELECT strftime('%m', date) as mon, initial_margin_pct
        FROM (
            SELECT strftime('%m', date) as date, expiry, initial_margin_pct
            FROM margins WHERE symbol='NATURALGAS' AND initial_margin_pct IS NOT NULL
            GROUP BY date, expiry
        )
        ORDER BY mon
        """,
    )
    month_vals: dict = {}
    for row in cur.fetchall():
        m = int(row[0])
        month_vals.setdefault(m, []).append(row[1])
    # Patch std_dev into seasonal_month
    for entry in seasonal_month:
        vals = month_vals.get(entry["month_num"], [])
        entry["std_dev"] = round(statistics.stdev(vals), 3) if len(vals) > 1 else 0.0
    save("seasonal_month.json", seasonal_month)  # resave with std_dev

    # ── seasonal_year.json ────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT strftime('%Y', date) as yr,
               AVG(initial_margin_pct), AVG(total_margin_pct), COUNT(*),
               MIN(initial_margin_pct), MAX(initial_margin_pct)
        FROM (
            SELECT date, expiry,
                   initial_margin_pct, total_margin_pct
            FROM margins WHERE symbol='NATURALGAS'
            GROUP BY date, expiry
        )
        GROUP BY yr ORDER BY yr
        """,
    )
    seasonal_year = []
    for row in cur.fetchall():
        seasonal_year.append(
            {
                "year": int(row[0]),
                "avg_initial_margin": round(row[1], 3),
                "avg_total_margin": round(row[2], 3),
                "count": row[3],
                "min": round(row[4], 3),
                "max": round(row[5], 3),
            }
        )
    save("seasonal_year.json", seasonal_year)

    # ── seasonal_heatmap.json ─────────────────────────────────────────────────
    cur.execute(
        """
        SELECT strftime('%Y', date) as yr, strftime('%m', date) as mon,
               AVG(initial_margin_pct)
        FROM margins WHERE symbol='NATURALGAS'
        GROUP BY yr, mon
        """,
    )
    years_set = set()
    heatmap_raw: dict = {}
    for row in cur.fetchall():
        yr, mn = row[0], int(row[1])
        years_set.add(yr)
        heatmap_raw.setdefault(yr, {})[MONTH_NAMES[mn]] = round(row[2], 2)
    save(
        "seasonal_heatmap.json",
        {
            "years": sorted(years_set),
            "months": ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
            "data": heatmap_raw,
        },
    )

    # ── dte_curve.json — all-time + trailing 5Y ───────────────────────────────
    from datetime import datetime as _dt, timedelta as _td
    _cutoff_5y = (_dt.strptime(max_date, "%Y-%m-%d") - _td(days=5 * 365)).strftime("%Y-%m-%d")

    cur.execute(
        "SELECT date, expiry, initial_margin_pct, tender_margin_pct FROM margins WHERE symbol='NATURALGAS'",
    )
    bin_order = ["0-7", "8-14", "15-30", "31-60", "61-90", "91-120", "121-180", "181+"]
    bin_mid = {
        "0-7": 3, "8-14": 11, "15-30": 22, "31-60": 45,
        "61-90": 75, "91-120": 105, "121-180": 150, "181+": 200,
    }

    def get_bin(dte):
        if dte <= 7:     return "0-7"
        elif dte <= 14:  return "8-14"
        elif dte <= 30:  return "15-30"
        elif dte <= 60:  return "31-60"
        elif dte <= 90:  return "61-90"
        elif dte <= 120: return "91-120"
        elif dte <= 180: return "121-180"
        return "181+"

    dte_data: dict = {}
    dte_data_5y: dict = {}
    seen_dte: set = set()  # dedup (date, expiry) — margins has 3 rows per pair
    for row in cur.fetchall():
        d, exp, im, tm = row[0], row[1], row[2], row[3]
        if (d, exp) in seen_dte:
            continue
        seen_dte.add((d, exp))
        dte = compute_dte(exp, d)
        if dte < 0 or im is None:
            continue
        b = get_bin(dte)
        dte_data.setdefault(b, {"im": [], "tm": []})
        dte_data[b]["im"].append(im)
        if tm is not None:
            dte_data[b]["tm"].append(tm)
        # Trailing 5Y — cutoff derived from max_date, no hardcoded year
        if d >= _cutoff_5y:
            dte_data_5y.setdefault(b, {"im": [], "tm": []})
            dte_data_5y[b]["im"].append(im)
            if tm is not None:
                dte_data_5y[b]["tm"].append(tm)

    dte_curve = []
    for b in bin_order:
        if b in dte_data and dte_data[b]["im"]:
            d5 = dte_data_5y.get(b, {"im": [], "tm": []})
            dte_curve.append(
                {
                    "dte_bin": b,
                    "dte_mid": bin_mid[b],
                    "avg_initial_margin": round(statistics.mean(dte_data[b]["im"]), 3),
                    "avg_tender_margin": round(statistics.mean(dte_data[b]["tm"]), 3) if dte_data[b]["tm"] else 0.0,
                    "count": len(dte_data[b]["im"]),
                    "avg_initial_5y": round(statistics.mean(d5["im"]), 3) if d5["im"] else None,
                    "avg_tender_5y": round(statistics.mean(d5["tm"]), 3) if d5["tm"] else None,
                    "count_5y": len(d5["im"]),
                }
            )
    save("dte_curve.json", dte_curve)


    # ── forward_curve.json ────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT symbol, expiry, initial_margin_pct, total_margin_pct,
               daily_volatility, annualized_volatility
        FROM margins WHERE date=? ORDER BY symbol, expiry
        """,
        (latest_date,),
    )
    fwd: dict = {"as_of": latest_date, "NATURALGAS": [], "NATGASMINI": []}
    seen_fwd: dict = {"NATURALGAS": set(), "NATGASMINI": set()}  # dedup by expiry
    for row in cur.fetchall():
        sym, exp, im, tm, dv, av = row
        if sym in fwd and exp not in seen_fwd[sym]:
            seen_fwd[sym].add(exp)
            dte = compute_dte(exp, latest_date)
            fwd[sym].append(
                {
                    "expiry": exp,
                    "dte": dte,
                    "initial_margin_pct": im,
                    "total_margin_pct": tm,
                    "daily_volatility": dv,
                    "annualized_volatility": av,
                }
            )
    for sym in ["NATURALGAS", "NATGASMINI"]:
        fwd[sym].sort(key=lambda x: x["dte"])
    save("forward_curve.json", fwd)

    # ── volatility_correlation.json ───────────────────────────────────────────
    # One row per date (front month) for NATURALGAS
    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol='NATURALGAS' ORDER BY date",
    )
    all_dates = [r[0] for r in cur.fetchall()]

    ts = []
    for d in all_dates:
        cur.execute(
            """
            SELECT expiry, initial_margin_pct, daily_volatility, annualized_volatility
            FROM margins WHERE date=? AND symbol='NATURALGAS'
            """,
            (d,),
        )
        rows = cur.fetchall()
        best = None
        best_dte = 99999
        for row in rows:
            dte = compute_dte(row[0], d)
            if 0 <= dte < best_dte:
                best_dte = dte
                best = row
        if best and best[1] is not None and best[2] is not None:
            ts.append(
                {
                    "date": d,
                    "margin_pct": best[1],
                    "vol_daily": best[2],
                    "vol_annual": best[3],
                }
            )

    margins_list = [r["margin_pct"] for r in ts]
    vols_list = [r["vol_daily"] for r in ts]

    lag_corr = {}
    for lag in [0, 5, 10, 15, 20, 30]:
        if lag == 0:
            lag_corr[str(lag)] = safe_corr(margins_list, vols_list)
        else:
            lag_corr[str(lag)] = safe_corr(margins_list[lag:], vols_list[:-lag])

    save(
        "volatility_correlation.json",
        {
            "lags": [0, 5, 10, 15, 20, 30],
            "NATURALGAS": lag_corr,
            "timeseries": ts,  # full history
        },
    )

    # ── panic_spread.json ─────────────────────────────────────────────────────
    # Compute from forward_curve data (already loaded)
    ng_fwd = fwd["NATURALGAS"]
    # Compute mean vol for last 20 days
    recent_vols = [r["vol_daily"] for r in ts[-20:] if r["vol_daily"] is not None]
    mean_vol_20 = sum(recent_vols) / len(recent_vols) if recent_vols else 0.04

    panic_entries = []
    for i, contract in enumerate(ng_fwd):
        im = contract["initial_margin_pct"] or 0   # use initial consistently
        tm = contract["total_margin_pct"] or 0      # kept for display and spread
        dv = contract["daily_volatility"] or mean_vol_20
        predicted = im * 0.886 + dv * 43.0          # formula now uses initial, not total
        spread_vs_next = (
            tm - ng_fwd[i + 1]["total_margin_pct"]
            if i + 1 < len(ng_fwd)
            else 0.0
        )
        action = "HIKE" if predicted > im else "CUT"   # compare vs initial
        panic_entries.append(
            {
                "expiry": contract["expiry"],
                "dte": contract["dte"],
                "initial_margin_pct": round(im, 3),
                "total_margin_pct": round(tm, 3),
                "vol_daily": round(dv, 6),
                "predicted_tomorrow": round(predicted, 3),
                "spread_vs_next": round(spread_vs_next, 3),  # renamed from spread_vs_prev
                "action": action,
            }
        )
    save(
        "panic_spread.json",
        {"as_of": latest_date, "NATURALGAS": panic_entries},
    )

    # ── Items 1–9 (advanced analytics) ────────────────────────────────────────
    if HAS_SKLEARN:
        # Build full front-month history series (date-sorted, non-null)
        fm_series = _build_front_month_series(cur)
        regime_params = _export_regime_model(cur, fm_series)          # Item 3 first (others depend on it)
        _export_forecast_bands(fm_series, panic_entries, regime_params) # Item 1
        _export_model_health(fm_series)                                  # Item 2
        _export_delta_distribution(fm_series)                            # Item 4
        _export_curve_cone(cur, fwd, latest_date)                        # Item 5
        _export_decomposition(fm_series, regime_params)                  # Item 6
        _export_seasonality_boxplot(cur)                                  # Item 7
        _export_stress_score(cur, fm_series, latest_date)                # Item 8 — updates current.json
        _export_event_probabilities(cur, fm_series, panic_entries, regime_params)  # Item 9

    try:
        print()
        print("MCX Market Intelligence - JSON Export")
        print("=" * 40)
        market_status = _export_market_intelligence(cur)
        print(
            f"  [MARKET] status={market_status.get('status')} "
            f"latest={market_status.get('latest_date')} "
            f"outputs={len(market_status.get('outputs', []))}"
        )
    except Exception as e:
        print(f"  [WARN] Market intelligence export failed: {e}")

    conn.close()
    print()
    print(f"All JSON files exported to {OUT_DIR}/")
    print(f"Latest data: {latest_date} | Total records: {count:,}")


def export_hh_price():
    """Fetch Henry Hub front-month price history from Yahoo Finance (NG=F) and save as JSON.

    Fetches from 2009-01-01 to cover the full MCX margin history (2010-present).
    NG=F (Natural Gas Continuous) on Yahoo Finance has data back to the 1990s.
    ~4000 rows at daily interval is trivially small (~80 KB).
    """
    import time
    # Full history from 2009-01-01 — covers all MCX margin data since 2010
    period1 = int(datetime(2009, 1, 1).timestamp())
    period2 = int(time.time())
    # NG=F = Natural Gas Continuous Contract (front month) on Yahoo Finance
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/NG%3DF"
        f"?period1={period1}&period2={period2}&interval=1d"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        prices = []
        for ts, close in zip(timestamps, closes):
            if close is not None:
                date_str = date.fromtimestamp(ts).isoformat()
                prices.append({"date": date_str, "price": round(close, 4)})
        save("hh_price.json", {"symbol": "NG=F", "currency": "USD/MMBtu", "prices": prices})
    except Exception as e:
        print(f"  [WARN] HH price fetch failed: {e} - skipping hh_price.json")


if __name__ == "__main__":
    main()
    export_hh_price()
    export_manifest()
