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


if __name__ == "__main__":
    unittest.main()
