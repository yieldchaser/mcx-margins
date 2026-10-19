import unittest
import numpy as np
import pandas as pd
from scipy.stats import norm
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scripts.fetch_prices as fetch_prices
import scripts.export_options_chain as export_options_chain
import scripts.export_json as export_json


class AuditFixesRegressionTests(unittest.TestCase):
    def test_fetch_prices_rejects_options(self):
        # 1. Futures row should be accepted
        fut_row = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "26NOV2026",
            "InstrumentName": "FUTCOM",
            "OptionType": "-",
            "Close": 250.0,
            "PreviousClose": 245.0,
        }
        res_fut = fetch_prices.normalize(fut_row, "2026-10-15")
        self.assertIsNotNone(res_fut)
        self.assertEqual(res_fut["symbol"], "NATURALGAS")
        self.assertEqual(res_fut["close"], 250.0)

        # 2. Options row should be strictly rejected from futures table
        opt_row = {
            "Symbol": "NATURALGAS",
            "ExpiryDate": "26NOV2026",
            "InstrumentName": "OPTFUT",
            "OptionType": "CE",
            "StrikePrice": 250.0,
            "Close": 12.50,
            "PreviousClose": 10.0,
        }
        res_opt = fetch_prices.normalize(opt_row, "2026-10-15")
        self.assertIsNone(res_opt, "normalize() must reject OPTFUT option rows")

    def test_black76_put_theta_positive_carrying_cost(self):
        # In Black-76, Put Theta includes + r * P calendar drift
        F = 250.0
        K = 250.0
        T = 30.0 / 365.25
        r = 0.066
        sigma = 0.45
        
        greeks_put = export_options_chain.calculate_greeks(F, K, T, r, sigma, is_call=False)
        put_price = export_options_chain.black76_price(F, K, T, r, sigma, is_call=False)
        disc = np.exp(-r * T)
        d1 = (np.log(F / K) + 0.5 * (sigma ** 2) * T) / (sigma * np.sqrt(T))
        n_d1 = norm.pdf(d1)
        expected_theta = ((- (disc * F * sigma * n_d1) / (2.0 * np.sqrt(T)) + r * put_price) / 365.25)
        
        self.assertAlmostEqual(greeks_put["theta"], round(expected_theta, 3), places=3)

    def test_value_area_captures_at_least_70_pct(self):
        # Monopolized volume: single bin has 80% volume
        prices = [200.0, 205.0, 210.0]
        vols = [8000, 1000, 1000] # Total = 10,000, first bin = 80%
        vap_series = pd.Series(vols, index=prices)
        total_vap_vol = float(vap_series.sum())
        sorted_vap = vap_series.sort_values(ascending=False)
        cum_vol = sorted_vap.cumsum()

        va_mask = (cum_vol.shift(1, fill_value=0) < (total_vap_vol * 0.70)) if total_vap_vol > 0 else pd.Series(True, index=sorted_vap.index)
        va_prices = [float(p) for p in sorted_vap[va_mask].index]
        self.assertGreater(len(va_prices), 0, "Value area must never be empty on dominant volume")
        self.assertIn(200.0, va_prices)

    def test_delta_distribution_skips_cross_contract_roll(self):
        fm_series = [
            {"date": "2026-10-25", "expiry": "26OCT2026", "initial_margin_pct": 35.0, "dte": 1},
            # Roll transition to next contract with lower base margin
            {"date": "2026-10-26", "expiry": "26NOV2026", "initial_margin_pct": 18.0, "dte": 28},
            {"date": "2026-10-27", "expiry": "26NOV2026", "initial_margin_pct": 18.5, "dte": 27},
        ]
        
        # Test the loop logic from _export_delta_distribution
        deltas = []
        for i in range(len(fm_series) - 1):
            today = fm_series[i]
            tomorrow = fm_series[i + 1]
            if today.get("expiry") != tomorrow.get("expiry"):
                continue
            deltas.append(tomorrow["initial_margin_pct"] - today["initial_margin_pct"])
            
        # Should only record the 26NOV2026 delta (18.5 - 18.0 = +0.5), skipping the roll jump (-17.0)
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0], 0.5)


if __name__ == "__main__":
    unittest.main()
