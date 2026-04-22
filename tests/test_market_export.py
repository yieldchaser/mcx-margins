import unittest
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.export_json as export_json


class MarketExportTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
