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


    def test_alert_multi_expiry_detection(self):
        # Verify that get_margin_transitions detects non-front month shocks and tender entry
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            db_path = Path(tmp_db.name)

        conn = sqlite3.connect(db_path)
        conn.executescript('''
            CREATE TABLE margins (
                date TEXT, symbol TEXT, expiry TEXT, file_id INTEGER,
                initial_margin_pct REAL, elm_pct REAL, tender_margin_pct REAL, total_margin_pct REAL,
                additional_long_margin_pct REAL, additional_short_margin_pct REAL,
                special_long_margin_pct REAL, special_short_margin_pct REAL, delivery_margin_pct REAL,
                daily_volatility REAL, annualized_volatility REAL
            );
        ''')
        # Seasoning history: 5 earlier publications for both expiries
        for d in ("2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20"):
            for exp, im in (("27OCT2026", 15.5), ("25MAR2027", 17.8)):
                conn.execute("INSERT INTO margins (date, symbol, expiry, file_id, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct) VALUES (?, 'NATURALGAS', ?, 1, ?, 1.25, 0.0, ?)", (d, exp, im, im))
        # Insert prev date (2026-10-21)
        conn.execute("INSERT INTO margins (date, symbol, expiry, file_id, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct, daily_volatility, annualized_volatility) VALUES ('2026-10-21', 'NATURALGAS', '27OCT2026', 1, 15.77, 1.25, 5.0, 20.77, 0.025, 0.40)")
        conn.execute("INSERT INTO margins (date, symbol, expiry, file_id, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct, daily_volatility, annualized_volatility) VALUES ('2026-10-21', 'NATURALGAS', '25MAR2027', 1, 18.00, 1.25, 0.0, 18.00, 0.028, 0.44)")

        # Insert today date (2026-10-22)
        conn.execute("INSERT INTO margins (date, symbol, expiry, file_id, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct, daily_volatility, annualized_volatility) VALUES ('2026-10-22', 'NATURALGAS', '27OCT2026', 1, 19.02, 1.25, 10.0, 29.02, 0.030, 0.47)")
        conn.execute("INSERT INTO margins (date, symbol, expiry, file_id, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct, daily_volatility, annualized_volatility) VALUES ('2026-10-22', 'NATURALGAS', '25MAR2027', 1, 20.50, 1.25, 0.0, 20.50, 0.032, 0.50)")
        conn.commit()
        conn.close()

        orig_db = alert.DB_PATH
        alert.DB_PATH = db_path
        try:
            res = alert.get_margin_transitions("NATURALGAS")
            self.assertIsNotNone(res)
            today_d, prev_d, triggered, all_active = res
            self.assertEqual(today_d, "2026-10-22")
            self.assertEqual(prev_d, "2026-10-21")
            trig_expiries = [t["expiry"] for t in triggered]
            self.assertIn("27OCT2026", trig_expiries)
            self.assertIn("25MAR2027", trig_expiries)

            front = next(t for t in triggered if t["expiry"] == "27OCT2026")
            self.assertEqual(front["today_total"], 29.02)
            self.assertEqual(front["delta_im"], 3.25)
            self.assertEqual(front["delta_total"], 8.25)
            self.assertTrue(front["is_vol_shock"])

            far = next(t for t in triggered if t["expiry"] == "25MAR2027")
            self.assertEqual(far["today_total"], 20.50)
            self.assertEqual(far["delta_im"], 2.50)
            self.assertTrue(far["is_vol_shock"])
        finally:
            alert.DB_PATH = orig_db
            try:
                db_path.unlink()
            except Exception:
                pass


class AlertNoiseAndDedupTests(unittest.TestCase):
    """End-to-end behaviour of scripts/alert.py against a temp DB + temp ledger."""

    COLS = ("date, symbol, expiry, file_id, initial_margin_pct, elm_pct, "
            "tender_margin_pct, total_margin_pct, daily_volatility, annualized_volatility")

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.db_path = self.tmp / "margins.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"CREATE TABLE margins ({self.COLS})")
        conn.commit()
        conn.close()
        self.orig = (alert.DB_PATH, alert.PRICE_DB_PATH, alert.STATE_PATH, alert.send_email)
        alert.DB_PATH = self.db_path
        alert.PRICE_DB_PATH = self.tmp / "no_prices.db"
        alert.STATE_PATH = self.tmp / "alert_state.json"
        self.sent = []

        def fake_send(subject, body):
            self.sent.append(subject)
            return True
        alert.send_email = fake_send

    def tearDown(self):
        alert.DB_PATH, alert.PRICE_DB_PATH, alert.STATE_PATH, alert.send_email = self.orig
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, date, expiry, im, tender=0.0, file_id=1):
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"INSERT INTO margins ({self.COLS}) VALUES (?, 'NATURALGAS', ?, ?, ?, 1.25, ?, ?, 0.03, 0.5)",
                     (date, expiry, file_id, im, tender, im + tender))
        conn.commit()
        conn.close()

    def seed_history(self, expiry, im, dates=("2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20")):
        for d in dates:
            self.add(d, expiry, im)

    def test_same_event_emailed_exactly_once_across_repeated_runs(self):
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 16.0)  # +3pp real shock on front month
        for _ in range(8):  # 8 scheduled runs in a day
            alert.main([])
        self.assertEqual(len(self.sent), 1)
        self.assertIn("28DEC2026", self.sent[0])

    def test_intraday_revision_with_new_numbers_sends_update(self):
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 16.0, file_id=1)
        alert.main([])
        self.add("2026-11-24", "28DEC2026", 18.0, file_id=2)  # MCX revises later same day
        alert.main([])
        alert.main([])
        self.assertEqual(len(self.sent), 2)

    def test_new_listing_placeholder_zero_does_not_alert(self):
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 13.1)
        self.add("2026-11-23", "25MAY2027", 0.0)     # listing-day placeholder
        self.add("2026-11-24", "25MAY2027", 21.0)    # first real SPAN print
        alert.main([])
        self.assertEqual(self.sent, [])

    def test_unseasoned_far_month_does_not_alert(self):
        # Mirrors 2026-11-26: 25MAY2027 listed 1 day ago, 13.62 -> 16.32
        self.seed_history("28DEC2026", 16.0)
        self.add("2026-11-25", "28DEC2026", 16.15)
        self.add("2026-11-26", "28DEC2026", 15.67)
        self.add("2026-11-25", "25MAY2027", 13.62)
        self.add("2026-11-26", "25MAY2027", 16.32)
        alert.main([])
        self.assertEqual(self.sent, [])
        res = alert.get_margin_transitions("NATURALGAS")
        far = next(c for c in res[3] if c["expiry"] == "25MAY2027")
        self.assertEqual(far["suppressed_reason"], "unseasoned-listing")

    def test_seasoned_far_month_shock_still_alerts(self):
        self.seed_history("25MAR2027", 14.0)
        self.add("2026-11-23", "25MAR2027", 14.0)
        self.add("2026-11-24", "25MAR2027", 16.5)
        alert.main([])
        self.assertEqual(len(self.sent), 1)

    def test_tender_entry_alerts_once(self):
        self.seed_history("24NOV2026", 15.0, dates=("2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"))
        self.add("2026-11-17", "24NOV2026", 15.6, tender=0.0)
        self.add("2026-11-18", "24NOV2026", 15.2, tender=5.0)
        alert.main([])
        alert.main([])
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Tender", self.sent[0])

    def test_routine_tender_step_does_not_alert(self):
        self.seed_history("24NOV2026", 15.0, dates=("2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14"))
        self.add("2026-11-18", "24NOV2026", 15.2, tender=5.0)
        self.add("2026-11-19", "24NOV2026", 15.9, tender=10.0)
        alert.main([])
        self.assertEqual(self.sent, [])

    def test_failed_or_skipped_send_is_not_recorded(self):
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 16.0)
        alert.send_email = lambda s, b: False  # e.g. no password configured
        alert.main([])
        self.assertFalse(alert.STATE_PATH.exists())

    def test_dry_run_and_record_only(self):
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 16.0)
        alert.main(["--dry-run"])
        self.assertEqual(self.sent, [])
        self.assertFalse(alert.STATE_PATH.exists())
        alert.main(["--record-only"])
        self.assertEqual(self.sent, [])
        alert.main([])
        self.assertEqual(self.sent, [])  # already recorded

    def test_corrupt_state_file_recovers(self):
        alert.STATE_PATH.write_text("{not json")
        self.seed_history("28DEC2026", 13.0)
        self.add("2026-11-23", "28DEC2026", 13.0)
        self.add("2026-11-24", "28DEC2026", 16.0)
        alert.main([])
        self.assertEqual(len(self.sent), 1)


if __name__ == "__main__":
    unittest.main()
