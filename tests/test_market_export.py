import unittest
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.export_json as export_json


class MarketExportTests(unittest.TestCase):
    def _make_margin_conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE margins (
                date TEXT,
                symbol TEXT,
                expiry TEXT,
                file_id INTEGER,
                created_at TEXT,
                initial_margin_pct REAL,
                elm_pct REAL,
                tender_margin_pct REAL,
                total_margin_pct REAL,
                additional_long_margin_pct REAL,
                additional_short_margin_pct REAL,
                special_long_margin_pct REAL,
                special_short_margin_pct REAL,
                delivery_margin_pct REAL,
                daily_volatility REAL,
                annualized_volatility REAL
            )
            """
        )
        return conn

    def test_futures_filter_excludes_options(self):
        self.assertTrue(export_json._is_market_futures_row({
            "symbol": "NATURALGAS",
            "instrument": "FUTCOM",
        }))
        self.assertFalse(export_json._is_market_futures_row({
            "symbol": "NATURALGAS",
            "instrument": "OPTFUT",
        }))

    def test_select_front_month_uses_nearest_non_expired_contract(self):
        rows = [
            {"expiry": "27APR2026", "dte": 5},
            {"expiry": "26MAY2026", "dte": 34},
            {"expiry": "23APR2026", "dte": -1},
        ]
        self.assertEqual(export_json._select_front_month(rows)["expiry"], "27APR2026")

    def test_enrich_market_history_adds_rolling_metrics(self):
        rows = []
        start = date(2026, 1, 1)
        for i in range(25):
            close = 100 + i
            rows.append({
                "date": (start + timedelta(days=i)).isoformat(),
                "symbol": "NATURALGAS",
                "expiry": "27APR2026",
                "dte": 100 - i,
                "open": close - 1,
                "high": close + 1,
                "low": close - 2,
                "close": close,
                "prev_close": close - 1,
                "return_pct": 1.0,
                "volume_lots": 100 + i,
                "volume_kgs": 100 + i,
                "value_lacs": 10 + i,
                "open_interest": 500 + i,
            })
        enriched = export_json._enrich_market_history(rows)
        self.assertIn("rolling_realized_vol_20d", enriched[-1])
        self.assertIn("volume_z_20d", enriched[-1])
        self.assertIn("oi_change_pct", enriched[-1])
        self.assertIn("return_20d_pct", enriched[-1])
        self.assertIn("range_pct", enriched[-1])
        self.assertIn("turnover_ratio", enriched[-1])
        self.assertIn("oi_flow_state", enriched[-1])
        self.assertEqual(enriched[-1]["return_5d_pct"], round(((124 - 119) / 119) * 100, 3))

    def test_market_signals_are_explainable(self):
        history = export_json._enrich_market_history([
            {
                "date": f"2026-01-{day:02d}",
                "symbol": "NATURALGAS",
                "expiry": "27APR2026",
                "dte": 120 - day,
                "open": 100 + day,
                "high": 101 + day,
                "low": 99 + day,
                "close": 100 + day,
                "prev_close": 99 + day,
                "return_pct": 1.0,
                "volume_lots": 100 + day * 5,
                "volume_kgs": 100 + day * 5,
                "value_lacs": 10,
                "open_interest": 500 + day * 10,
            }
            for day in range(1, 15)
        ])
        joined = [
            {
                "date": row["date"],
                "symbol": "NATURALGAS",
                "initial_margin_pct": 10 + idx * 0.1,
                "close": row["close"],
                "return_5d_pct": row.get("return_5d_pct"),
            }
            for idx, row in enumerate(history)
        ]
        signals = export_json._build_market_signals("NATURALGAS", history, joined)
        self.assertGreaterEqual(len(signals), 4)
        for signal in signals:
            self.assertIn("score", signal)
            self.assertIn("features", signal)
            self.assertIn("reason", signal)
            self.assertTrue(signal["reason"])

    def test_freshness_status_marks_stale_sources(self):
        stale_date = (date.today() - timedelta(days=10)).isoformat()
        self.assertEqual(export_json._freshness_status(stale_date)["label"], "STALE")

    def test_oi_flow_state_classifies_positioning_quadrants(self):
        self.assertEqual(export_json._oi_flow_state(1.2, 3.4), "long_build")
        self.assertEqual(export_json._oi_flow_state(-1.2, 3.4), "short_build")
        self.assertEqual(export_json._oi_flow_state(-1.2, -3.4), "long_unwind")
        self.assertEqual(export_json._oi_flow_state(1.2, -3.4), "short_cover")
        self.assertEqual(export_json._oi_flow_state(0.0, 0.0), "neutral")

    def test_contract_alignment_status_covers_overlap_cases(self):
        self.assertEqual(
            export_json._contract_alignment_status({"2026-01-01"}, {"2026-01-01"}),
            "aligned",
        )
        self.assertEqual(
            export_json._contract_alignment_status({"2026-01-01", "2026-01-02"}, {"2026-01-02"}),
            "partial",
        )
        self.assertEqual(
            export_json._contract_alignment_status({"2026-01-01"}, {"2026-01-03"}),
            "disjoint",
        )
        self.assertEqual(
            export_json._contract_alignment_status({"2026-01-01"}, set()),
            "missing_market",
        )
        self.assertEqual(
            export_json._contract_alignment_status(set(), {"2026-01-01"}),
            "missing_margin",
        )

    def test_load_margin_rows_applies_export_dedupe_priority(self):
        conn = self._make_margin_conn()
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO margins (
                date, symbol, expiry, file_id, created_at,
                initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct,
                additional_long_margin_pct, additional_short_margin_pct,
                special_long_margin_pct, special_short_margin_pct,
                delivery_margin_pct, daily_volatility, annualized_volatility
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-01-02", "NATURALGAS", "25JAN2026", 1, "2026-01-02T10:00:00",
                    10.0, 1.25, 0.0, 11.25, None, None, None, None, None, 0.03, 0.48,
                ),
                (
                    "2026-01-02", "NATURALGAS", "25JAN2026", 2, "2026-01-02T09:00:00",
                    12.0, 1.25, 0.0, 13.25, None, None, None, None, None, 0.04, 0.50,
                ),
                (
                    "2026-01-03", "NATURALGAS", "26FEB2026", 3, "2026-01-03T09:00:00",
                    20.0, 1.25, 0.0, 21.25, None, None, None, None, None, 0.05, 0.60,
                ),
                (
                    "2026-01-03", "NATURALGAS", "26FEB2026", 3, "2026-01-03T12:00:00",
                    21.0, 1.25, 0.0, 22.25, None, None, None, None, None, 0.055, 0.62,
                ),
                (
                    "2026-01-04", "NATURALGAS", "27MAR2026", 4, "2026-01-04T08:00:00",
                    30.0, None, None, None, None, None, None, None, None, None, None,
                ),
                (
                    "2026-01-04", "NATURALGAS", "27MAR2026", 4, "2026-01-04T08:00:00",
                    31.0, 1.25, 0.0, 32.25, None, None, None, None, None, 0.06, 0.70,
                ),
            ],
        )
        rows = export_json._load_margin_rows(
            cur,
            "symbol = ?",
            ("NATURALGAS",),
            "date ASC, expiry ASC",
        )
        by_expiry = {row["expiry"]: row for row in rows}
        self.assertEqual(by_expiry["25JAN2026"]["file_id"], 2)
        self.assertEqual(by_expiry["25JAN2026"]["initial_margin_pct"], 12.0)
        self.assertEqual(by_expiry["26FEB2026"]["created_at"], "2026-01-03T12:00:00")
        self.assertEqual(by_expiry["26FEB2026"]["initial_margin_pct"], 21.0)
        self.assertEqual(by_expiry["27MAR2026"]["total_margin_pct"], 32.25)
        self.assertEqual(by_expiry["27MAR2026"]["annualized_volatility"], 0.70)

    def test_joined_symbol_summary_ignores_misaligned_rows(self):
        rows = [
            {
                "date": f"2026-01-{day:02d}",
                "alignment_status": "aligned",
                "margin_change_1d": float(day),
                "return_1d_pct": float(day) / 10,
                "rolling_realized_vol_20d": 20.0 + day,
                "volume_z_20d": day / 5,
                "oi_change_pct": day / 2,
            }
            for day in range(1, 8)
        ]
        rows.append(
            {
                "date": "2026-01-08",
                "alignment_status": "partial",
                "margin_change_1d": 999.0,
                "return_1d_pct": 999.0,
                "rolling_realized_vol_20d": 999.0,
                "volume_z_20d": 999.0,
                "oi_change_pct": 999.0,
            }
        )
        summary = export_json._joined_symbol_summary(rows)
        self.assertEqual(summary["aligned_obs"], 7)
        self.assertIn("lag_0", summary["lag_correlations"])
        self.assertIn("price_return", summary["lag_correlations"]["lag_1"])

    def test_build_curve_history_for_symbol_marks_curve_scope(self):
        history = export_json._build_curve_history_for_symbol(
            {
                "2026-01-02": [
                    {"date": "2026-01-02", "expiry": "25JAN2026", "dte": 23, "close": 100.0, "volume_lots": 1000, "open_interest": 8000},
                    {"date": "2026-01-02", "expiry": "26FEB2026", "dte": 55, "close": 105.0, "volume_lots": 500, "open_interest": 4000},
                    {"date": "2026-01-02", "expiry": "27MAR2026", "dte": 84, "close": 110.0, "volume_lots": 200, "open_interest": 2000},
                ]
            }
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["series_scope"], "active_curve")
        self.assertEqual(history[0]["front_expiry"], "25JAN2026")
        self.assertEqual(history[0]["front_second_spread"], 5.0)
        self.assertEqual(history[0]["front_back_spread"], 10.0)
        self.assertEqual(history[0]["curve_state"], "contango")


if __name__ == "__main__":
    unittest.main()
