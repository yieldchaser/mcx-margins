import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.fetch_prices as fetch_prices


class FetchPricesTests(unittest.TestCase):
    def test_save_records_upserts_existing_rows(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(fetch_prices.CREATE_SQL)

        first = {
            "date": "2026-01-02",
            "symbol": "NATURALGAS",
            "expiry": "25JAN2026",
            "instrument": "FUTCOM",
            "option_type": "-",
            "strike_price": 0.0,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "prev_close": 99.5,
            "volume_lots": 1000,
            "volume_kgs": 1000.0,
            "value_lacs": 10.0,
            "open_interest": 5000,
        }
        revised = dict(first)
        revised.update({"close": 102.25, "volume_lots": 1200, "open_interest": 5400})

        self.assertEqual(fetch_prices.save_records(conn, [first]), 1)
        self.assertEqual(fetch_prices.save_records(conn, [revised]), 1)

        row = conn.execute(
            "SELECT close, volume_lots, open_interest FROM prices WHERE date=? AND symbol=? AND expiry=?",
            (first["date"], first["symbol"], first["expiry"]),
        ).fetchone()
        self.assertEqual(row, (102.25, 1200, 5400))

    def test_parse_response_handles_null_and_empty_payloads(self):
        self.assertEqual(fetch_prices.parse_response('{"Data": null}'), [])
        self.assertEqual(fetch_prices.parse_response('{"Data": []}'), [])
        self.assertEqual(fetch_prices.parse_response('{"d": {"Data": null}}'), [])
        self.assertEqual(fetch_prices.parse_response(''), [])
        self.assertEqual(fetch_prices.parse_response('{"other": 123}'), [])

    def test_normalize_drops_post_expiry_rows(self):
        # Contract expired on 20AUG2007, bhavcopy on 2007-08-21 (DTE = -1)
        post_expiry = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "20AUG2007",
            "InstrumentName": "FUTCOM",
            "Close": 250.0,
        }
        self.assertIsNone(fetch_prices.normalize(post_expiry, "2007-08-21"))

        # Active contract (DTE >= 0)
        active = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "27OCT2026",
            "InstrumentName": "FUTCOM",
            "Close": 250.0,
        }
        result = fetch_prices.normalize(active, "2026-10-12")
        self.assertIsNotNone(result)
        self.assertEqual(result["expiry"], "27OCT2026")


if __name__ == "__main__":
    unittest.main()
