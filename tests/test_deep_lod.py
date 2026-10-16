import json
import os
import unittest

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEEP_DIR = os.path.join(REPO_DIR, "docs", "data", "deep")


class DeepLodParityTests(unittest.TestCase):
    """Verifies complete structural parity and integrity between NATURALGAS and NATGASMINI LOD pyramids."""

    def test_manifest_contains_both_symbols(self):
        manifest_path = os.path.join(DEEP_DIR, "manifest.json")
        self.assertTrue(os.path.exists(manifest_path), "manifest.json must exist in docs/data/deep")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("ng", manifest, "manifest.json must index 'ng'")
        self.assertIn("ngm", manifest, "manifest.json must index 'ngm'")

        for sym in ["ng", "ngm"]:
            meta = manifest[sym]
            self.assertIn("daily", meta)
            self.assertIn("h1", meta)
            self.assertIn("m15", meta)
            self.assertIn("m1_months", meta)
            self.assertGreater(meta["daily"]["bars"], 500, f"{sym} daily bars must exceed 500")
            self.assertGreater(meta["m15"]["bars"], 10000, f"{sym} 15m bars must exceed 10,000")
            self.assertGreater(len(meta["m1_months"]), 0, f"{sym} must have 1m monthly chunks")

    def test_daily_tier_parity_and_integrity(self):
        for prefix, sym_name in [("ng", "NATURALGAS"), ("ngm", "NATGASMINI")]:
            daily_path = os.path.join(DEEP_DIR, f"{prefix}_daily.json")
            self.assertTrue(os.path.exists(daily_path), f"{prefix}_daily.json must exist")
            with open(daily_path, "r", encoding="utf-8") as f:
                bars = json.load(f)

            self.assertIsInstance(bars, list)
            self.assertGreater(len(bars), 500, f"{sym_name} daily bars must be substantial")

            # Check chronological sort and schema
            prev_t = 0
            for b in bars:
                self.assertIn("time", b)
                self.assertIn("open", b)
                self.assertIn("high", b)
                self.assertIn("low", b)
                self.assertIn("close", b)
                self.assertIn("volume", b)
                self.assertGreater(b["time"], prev_t, f"Bars in {daily_path} must be strictly increasing in time")
                self.assertGreater(b["high"], 0)
                self.assertGreaterEqual(b["high"], b["low"])
                prev_t = b["time"]

    def test_15m_tier_parity_and_integrity(self):
        for prefix, sym_name in [("ng", "NATURALGAS"), ("ngm", "NATGASMINI")]:
            m15_path = os.path.join(DEEP_DIR, f"{prefix}_15m.json")
            self.assertTrue(os.path.exists(m15_path), f"{prefix}_15m.json must exist")
            with open(m15_path, "r", encoding="utf-8") as f:
                bars = json.load(f)

            self.assertIsInstance(bars, list)
            self.assertGreater(len(bars), 20000, f"{sym_name} 15m bars must exceed 20,000")

            # Verify sorting and positive pricing
            prev_t = 0
            for b in bars:
                self.assertGreater(b["time"], prev_t, f"Bars in {m15_path} must be strictly increasing")
                self.assertGreater(b["close"], 0)
                prev_t = b["time"]

    def test_1m_monthly_microstructure_parity(self):
        ng_1m_dir = os.path.join(DEEP_DIR, "1m")
        ngm_1m_dir = os.path.join(DEEP_DIR, "1m_ngm")

        self.assertTrue(os.path.isdir(ng_1m_dir), "docs/data/deep/1m must exist")
        self.assertTrue(os.path.isdir(ngm_1m_dir), "docs/data/deep/1m_ngm must exist")

        ng_files = set(os.listdir(ng_1m_dir))
        ngm_files = set(os.listdir(ngm_1m_dir))

        common_files = ng_files.intersection(ngm_files)
        self.assertGreaterEqual(len(common_files), 10, "NG and NGM must share monthly chunks")

        for fname in common_files:
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(ngm_1m_dir, fname), "r", encoding="utf-8") as f:
                bars = json.load(f)
            self.assertIsInstance(bars, list)
            self.assertGreater(len(bars), 1000, f"Chunk {fname} in 1m_ngm must have bars")
            # Bar format: [epoch, o, h, l, c, v]
            first_bar = bars[0]
            self.assertEqual(len(first_bar), 6, f"Bar in {fname} must have 6 elements [epoch, o, h, l, c, v]")
            self.assertGreater(first_bar[0], 1500000000)
            self.assertGreater(first_bar[4], 0)


    def test_dynamic_calendar_spread_output(self):
        spread_generic = os.path.join(REPO_DIR, "docs", "data", "market", "calendar_spread.json")
        spread_legacy = os.path.join(REPO_DIR, "docs", "data", "market", "calendar_spread_nov26_oct26.json")
        self.assertTrue(os.path.exists(spread_generic), "calendar_spread.json must exist")
        self.assertTrue(os.path.exists(spread_legacy), "calendar_spread_nov26_oct26.json legacy alias must exist")

        with open(spread_generic, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("pair", data)
        self.assertIn("front_contract", data)
        self.assertIn("next_contract", data)
        self.assertIn("latest_spread", data)
        self.assertIn("data", data)
        self.assertGreater(len(data["data"]["dt"]), 100)

    def test_dynamic_options_chain_output(self):
        options_generic = os.path.join(REPO_DIR, "docs", "data", "options_chain.json")
        options_legacy = os.path.join(REPO_DIR, "docs", "data", "options_chain_oct26.json")
        self.assertTrue(os.path.exists(options_generic), "options_chain.json must exist")
        self.assertTrue(os.path.exists(options_legacy), "options_chain_oct26.json legacy alias must exist")

        with open(options_generic, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("metadata", data)
        self.assertIn("indicators", data)
        self.assertIn("chain", data)
        self.assertGreater(len(data["chain"]), 5)
        self.assertIn("underlying_futures", data["metadata"])
        self.assertIn("expiry_date", data["metadata"])

    def test_dynamic_lod_pyramid_helpers(self):
        import sys
        sys.path.insert(0, os.path.join(REPO_DIR, "scripts"))
        from build_lod_pyramid import find_vault_parquet, find_contract_wise_parquets

        v_ng = find_vault_parquet("NATURALGAS")
        self.assertTrue(v_ng.exists(), "find_vault_parquet must resolve existing parquet")

        cw_ng = find_contract_wise_parquets("NATURALGAS")
        self.assertGreater(len(cw_ng), 0, "find_contract_wise_parquets must find contract parquets")

    def test_resolve_active_contracts_future_years(self):
        from datetime import datetime
        import sys
        sys.path.insert(0, os.path.join(REPO_DIR, "scripts"))
        from auto_market_snapshot import resolve_active_contracts

        class DummyFyers:
            def quotes(self, data):
                return {"s": "error"}

        dummy = DummyFyers()

        # 1. Test mid-month October 2026 (day < 26)
        dt_oct = datetime(2026, 10, 15)
        c_oct = resolve_active_contracts(dummy, dt_oct)
        self.assertEqual(len(c_oct), 12)  # 6 forward months * 2 symbols (NG, NGM)
        # Front contract should be 26OCT
        front_c = [c for c in c_oct if c[4] and c[0] == "NATURALGAS"][0]
        self.assertEqual(front_c[1], "26OCT")
        self.assertEqual(front_c[2], "MCX:NATURALGAS26OCTFUT")

        # 2. Test near-month-end October 2026 (day >= 26) -> Rollover to 26NOV
        dt_roll = datetime(2026, 10, 27)
        c_roll = resolve_active_contracts(dummy, dt_roll)
        front_roll = [c for c in c_roll if c[4] and c[0] == "NATURALGAS"][0]
        self.assertEqual(front_roll[1], "26NOV")
        self.assertEqual(front_roll[2], "MCX:NATURALGAS26NOVFUT")

        # 3. Test Year-End transition (December 2026 -> 2027)
        dt_dec = datetime(2026, 12, 10)
        c_dec = resolve_active_contracts(dummy, dt_dec)
        expiries = [c[1] for c in c_dec if c[0] == "NATURALGAS"]
        # Expected sequence starting Dec 2026: 26DEC, 27JAN, 27FEB, 27MAR, 27APR, 27MAY
        self.assertEqual(expiries, ["26DEC", "27JAN", "27FEB", "27MAR", "27APR", "27MAY"])

        # 4. Test Year-End rollover on Dec 28 -> Rolls to 27JAN
        dt_dec_roll = datetime(2026, 12, 28)
        c_dec_roll = resolve_active_contracts(dummy, dt_dec_roll)
        front_dec_roll = [c for c in c_dec_roll if c[4] and c[0] == "NATURALGAS"][0]
        self.assertEqual(front_dec_roll[1], "27JAN")
        self.assertEqual(front_dec_roll[2], "MCX:NATURALGAS27JANFUT")

        # 5. Test Far Future Date (November 2027 -> 2028)
        dt_2027 = datetime(2027, 11, 15)
        c_2027 = resolve_active_contracts(dummy, dt_2027)
        expiries_2027 = [c[1] for c in c_2027 if c[0] == "NATURALGAS"]
        self.assertEqual(expiries_2027, ["27NOV", "27DEC", "28JAN", "28FEB", "28MAR", "28APR"])

    def test_all_exported_market_and_deep_json_clean(self):
        import glob
        market_dir = os.path.join(REPO_DIR, "docs", "data", "market")
        deep_dir = os.path.join(REPO_DIR, "docs", "data", "deep")

        # Check all NG/NGM 15m and 1m files in market_dir
        for fpath in glob.glob(os.path.join(market_dir, "*.json")):
            fname = os.path.basename(fpath)
            if fname.startswith(("NG_", "NGM_")) and ("_15m.json" in fname or "_1m.json" in fname):
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                dts = data.get("data", {}).get("dt", [])
                closes = data.get("data", {}).get("c", [])
                self.assertGreater(len(dts), 0, f"{fname} must contain bars")
                self.assertEqual(len(dts), len(closes), f"{fname} dts and closes length must match")
                for i in range(1, len(dts)):
                    self.assertGreater(dts[i], dts[i-1], f"{fname} must be strictly ascending at index {i}")
                for c in closes:
                    self.assertLess(c, 1000.0, f"{fname} cross-commodity contamination detected: {c}")

        # Check deep LOD files
        for fname in ["ng_daily.json", "ngm_daily.json", "ng_15m.json", "ngm_15m.json"]:
            fpath = os.path.join(deep_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    bars = json.load(f)
                for b in bars:
                    self.assertLess(b["close"], 1000.0, f"{fname} cross-commodity contamination detected: {b['close']}")


if __name__ == "__main__":
    unittest.main()
