import os
import json
import unittest
import pandas as pd
import duckdb

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VAULT_DIR = os.path.join(REPO_DIR, "data", "mcx_vault")
CONTRACT_DIR = os.path.join(VAULT_DIR, "contract_wise")
CATALOG_PATH = os.path.join(VAULT_DIR, "commodities_catalog.json")
DOCS_CATALOG_PATH = os.path.join(REPO_DIR, "docs", "data", "market", "commodities_catalog.json")
DUCKDB_PATH = os.path.join(VAULT_DIR, "mcx_quant.duckdb")


class CommodityHarvesterTests(unittest.TestCase):
    """Verifies that the multi-commodity harvester, catalog manifest, and DuckDB vault operate reliably."""

    def test_catalog_manifest_structure(self):
        self.assertTrue(os.path.exists(CATALOG_PATH), "commodities_catalog.json must exist in vault")
        self.assertTrue(os.path.exists(DOCS_CATALOG_PATH), "commodities_catalog.json must exist in docs/data/market")

        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        self.assertIn("generated_at", catalog)
        self.assertIn("total_contracts", catalog)
        self.assertIn("total_commodities", catalog)
        self.assertIn("total_bars", catalog)
        self.assertIn("commodities", catalog)
        self.assertIn("contracts", catalog)

        self.assertGreater(catalog["total_contracts"], 0, "Must contain archived contracts")
        self.assertGreater(catalog["total_bars"], 100000, "Archived bars must be substantial")

        # Verify individual contracts in catalog
        for entry in catalog["contracts"]:
            self.assertIn("symbol", entry)
            self.assertIn("commodity", entry)
            self.assertIn("expiry", entry)
            self.assertIn("status", entry)
            self.assertIn(entry["status"], ["active", "expired"])
            self.assertIn("total_bars", entry)
            self.assertIn("file", entry)

    def test_parquet_schema_and_zero_shrink_integrity(self):
        contract_files = [f for f in os.listdir(CONTRACT_DIR) if f.endswith(".parquet")]
        self.assertGreater(len(contract_files), 5, "Must have contract-wise parquet files")

        required_cols = {"epoch", "open", "high", "low", "close", "volume", "symbol", "commodity", "expiry", "ts_ist"}

        for cfile in contract_files[:10]:
            fpath = os.path.join(CONTRACT_DIR, cfile)
            df = pd.read_parquet(fpath)
            self.assertGreater(len(df), 0, f"{cfile} must have rows")
            col_set = set(df.columns)
            self.assertTrue(required_cols.issubset(col_set), f"{cfile} missing columns: {required_cols - col_set}")

            # Verify strictly chronological ordering
            epochs = df["epoch"].tolist()
            self.assertEqual(epochs, sorted(epochs), f"{cfile} must be chronologically sorted")
            # Verify no duplicate epochs
            self.assertEqual(len(epochs), len(set(epochs)), f"{cfile} must have zero duplicate epoch timestamps")

    def test_duckdb_quant_vault_views(self):
        self.assertTrue(os.path.exists(DUCKDB_PATH), "mcx_quant.duckdb must exist")
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
        try:
            cnt = con.execute("SELECT count(*) FROM mcx_all_futures_1m").fetchone()[0]
            self.assertGreater(cnt, 200000, "mcx_all_futures_1m view must return rows")

            commodities = [r[0] for r in con.execute("SELECT DISTINCT commodity FROM mcx_all_futures_1m").fetchall()]
            self.assertIn("NATURALGAS", commodities)
            self.assertIn("NATGASMINI", commodities)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
