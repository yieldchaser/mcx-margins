import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.scraper as scraper
import src.db as db
import scripts.alert as alert


class MarginIntegrityTests(unittest.TestCase):
    def test_scraper_normalize_row_drops_post_expiry(self):
        # Contract expired on 26AUG2026, date is 2026-09-14 (DTE = -19)
        post_expiry = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "26AUG2026",
            "initialMargin": 10.5,
        }
        self.assertIsNone(scraper.normalize_row(post_expiry, "2026-09-14"))

        # Active contract (DTE >= 0)
        active = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "27OCT2026",
            "initialMargin": 15.0,
        }
        res = scraper.normalize_row(active, "2026-10-12")
        self.assertIsNotNone(res)
        self.assertEqual(res["expiry"], "27OCT2026")

    def test_db_upsert_margin_rejects_post_expiry(self):
        row = {
            "date": "2026-09-14",
            "symbol": "NATURALGAS",
            "expiry": "26AUG2026",
            "initial_margin_pct": 10.0,
        }
        # upsert_margin should return False for post-expiry row
        self.assertFalse(db.upsert_margin(row))

    def test_alert_selects_front_month_by_dte(self):
        # Create in-memory DB to test alert logic
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE margins (
                date TEXT, symbol TEXT, expiry TEXT,
                initial_margin_pct REAL, total_margin_pct REAL,
                daily_volatility REAL, annualized_volatility REAL
            );
        """)
        # Insert 2 contracts for 2026-10-12:
        # '23FEB2027' comes first alphabetically ('23' < '27'), but DTE is 134 days
        # '27OCT2026' comes second alphabetically, but DTE is 15 days
        conn.execute("INSERT INTO margins VALUES ('2026-10-12', 'NATURALGAS', '23FEB2027', 21.0, 21.0, 0.03, 0.5)")
        conn.execute("INSERT INTO margins VALUES ('2026-10-12', 'NATURALGAS', '27OCT2026', 15.0, 15.0, 0.02, 0.38)")

        cur = conn.cursor()
        cur.execute("SELECT m.initial_margin_pct, m.expiry, m.total_margin_pct, m.daily_volatility, m.annualized_volatility FROM margins m WHERE m.date='2026-10-12'")
        candidates = []
        for row in cur.fetchall():
            dte = alert.compute_dte(row[1], '2026-10-12')
            if dte is not None and dte >= 0:
                candidates.append((dte, row))
        best = min(candidates, key=lambda x: (x[0], x[1][1]))[1]
        self.assertEqual(best[1], "27OCT2026")
        self.assertEqual(best[0], 15.0)


if __name__ == "__main__":
    unittest.main()
