import unittest
import os
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import scripts.export_turnover as export_turnover


class TurnoverExportTests(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(ROOT, "data", "prices.db")
        self.output_path = os.path.join(ROOT, "docs", "data", "market", "turnover_analytics.json")

    def test_multiplier_logic(self):
        # NATURALGAS before 2008-04-21 was 500 mmBtu
        self.assertEqual(export_turnover.get_contract_multiplier("NATURALGAS", "2007-01-15"), 500.0)
        self.assertEqual(export_turnover.get_contract_multiplier("NATURALGAS", "2008-04-18"), 500.0)
        # NATURALGAS from 2008-04-21 onwards is 1250 mmBtu
        self.assertEqual(export_turnover.get_contract_multiplier("NATURALGAS", "2008-04-21"), 1250.0)
        self.assertEqual(export_turnover.get_contract_multiplier("NATURALGAS", "2026-10-23"), 1250.0)
        # NATGASMINI is 250 mmBtu
        self.assertEqual(export_turnover.get_contract_multiplier("NATGASMINI", "2023-03-14"), 250.0)
        self.assertEqual(export_turnover.get_contract_multiplier("NATGASMINI", "2026-10-23"), 250.0)

    def test_parse_expiry(self):
        d = export_turnover.parse_expiry("27OCT2026")
        self.assertIsNotNone(d)
        self.assertEqual(d.year, 2026)
        self.assertEqual(d.month, 10)
        self.assertEqual(d.day, 27)

    def test_export_file_validity(self):
        if not os.path.exists(self.output_path):
            export_turnover.export_turnover_analytics(self.db_path, self.output_path)

        self.assertTrue(os.path.exists(self.output_path))
        with open(self.output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Structure checks
        self.assertIn("meta", data)
        self.assertIn("kpis", data)
        self.assertIn("yearly", data)
        self.assertIn("monthly_seasonality", data)
        self.assertIn("daily", data)

        # Meta checks
        meta = data["meta"]
        self.assertGreater(meta["trading_days"], 5000)
        self.assertGreater(meta["total_turnover_lakh_cr"], 100.0)  # > 100 Lakh Crores
        self.assertGreaterEqual(meta["last_updated"], "2026-10-23")

        # KPI checks
        kpis = data["kpis"]
        self.assertIn("current_session", kpis)
        self.assertIn("ytd_current", kpis)
        self.assertIn("ath_day", kpis)
        self.assertEqual(kpis["ath_day"]["date"], "2026-01-22")
        self.assertGreater(kpis["ath_day"]["turnover_cr"], 25000.0)

        # Yearly history checks
        yearly = data["yearly"]
        self.assertGreaterEqual(len(yearly), 19)
        y2025 = next(y for y in yearly if y["year"] == "2025")
        self.assertGreater(y2025["turnover_lakh_cr"], 15.0)  # ~16.6 Lakh Cr
        y2026 = next(y for y in yearly if y["year"] == "2026")
        self.assertTrue(y2026["is_ytd"])
        self.assertGreater(y2026["mini_share_pct"], 20.0)  # Mini is > 20% in 2026

        # Monthly seasonality checks
        seasonality = data["monthly_seasonality"]
        self.assertEqual(len(seasonality), 12)
        total_share = sum(m["share_pct"] for m in seasonality)
        self.assertAlmostEqual(total_share, 100.0, delta=0.5)

        # Daily series checks
        daily = data["daily"]
        self.assertEqual(len(daily), meta["trading_days"])
        # Latest daily row
        latest = daily[-1]
        self.assertEqual(latest[0], meta["last_updated"])
        self.assertGreater(latest[1], 1000.0)  # Turnover in Cr

        # Chronological order and non-negativity
        prev_date = ""
        for row in daily:
            self.assertGreater(row[0], prev_date)
            prev_date = row[0]
            self.assertGreaterEqual(row[1], 0.0)  # total_cr >= 0
            self.assertGreaterEqual(row[2], 0.0)  # ma30_cr >= 0


if __name__ == "__main__":
    unittest.main()
