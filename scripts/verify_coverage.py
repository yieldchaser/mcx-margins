import json
from pathlib import Path

with open("docs/data/market/contract_index.json", "r", encoding="utf-8") as f:
    mkt_idx = json.load(f)

with open("docs/data/contract_index.json", "r", encoding="utf-8") as f:
    mrg_idx = json.load(f)

commodities = ["gold", "silver", "crudeoil", "copper", "zinc", "ng", "ngm"]
print("=== MULTI-YEAR CONTRACT COVERAGE ===")
for c in commodities:
    mrg_exp = [x["expiry"] for x in mrg_idx.get(c, [])]
    mkt_exp = [x["expiry"] for x in mkt_idx.get(c, [])]
    mrg_years = sorted(set(int(e[-4:]) for e in mrg_exp if len(e) >= 7 and e[-4:].isdigit()))
    mkt_years = sorted(set(int(e[-4:]) for e in mkt_exp if len(e) >= 7 and e[-4:].isdigit()))
    print(f"\n{c.upper()}:")
    print(f"  Margins ({len(mrg_exp)} contracts): {min(mrg_years) if mrg_years else 'N/A'} to {max(mrg_years) if mrg_years else 'N/A'} (Years: {mrg_years})")
    print(f"  Prices  ({len(mkt_exp)} contracts): {min(mkt_years) if mkt_years else 'N/A'} to {max(mkt_years) if mkt_years else 'N/A'} (Years: {mkt_years})")
