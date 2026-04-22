#!/usr/bin/env python3
"""
Generate contract_index.json + individual docs/data/contract/ files.
- contract_index.json: lightweight index {ng: [{expiry, obs, first_date, last_date},...], ngm: [...]}
  Used by the dropdown — loads instantly.
- docs/data/contract/<expiry>.json: one tiny file per contract, loaded on demand when selected.
  Avoids shipping 34 MB in one shot.
"""
import os, sys
sys.path.insert(0, '.')
from export_json import save, get_conn, compute_dte, json
from pathlib import Path

conn = get_conn()
cur = conn.cursor()

# Ensure per-contract dir exists
contract_dir = Path('docs/data/contract')
contract_dir.mkdir(parents=True, exist_ok=True)

index = {'ng': [], 'ngm': []}

SYM_MAP = {'NATURALGAS': 'ng', 'NATGASMINI': 'ngm'}

for sym, sym_key in SYM_MAP.items():
    cur.execute(
        """
        SELECT date, expiry, initial_margin_pct, total_margin_pct, elm_pct,
               tender_margin_pct, daily_volatility, annualized_volatility
        FROM margins
        WHERE symbol=? AND initial_margin_pct IS NOT NULL
        ORDER BY expiry ASC, date ASC
        """,
        (sym,)
    )

    # Group rows by expiry
    by_expiry = {}
    for row in cur.fetchall():
        exp = row[1]
        if exp not in by_expiry:
            by_expiry[exp] = []
        dv = row[6]
        av = row[7]
        dte = compute_dte(exp, row[0])
        by_expiry[exp].append({
            'date': row[0],
            'dte': dte,
            'initial_margin_pct': row[2],
            'total_margin_pct': row[3],
            'elm_pct': row[4],
            'tender_margin_pct': row[5],
            'daily_volatility': round(dv * 100, 4) if dv is not None else None,
            'annualized_volatility': round(av * 100, 4) if av is not None else None,
        })

    for exp, rows in by_expiry.items():
        # Write individual contract file
        out_path = contract_dir / f'{exp}.json'
        with open(out_path, 'w') as f:
            json.dump({'expiry': exp, 'symbol': sym, 'rows': rows}, f, separators=(',', ':'))

        dates = [r['date'] for r in rows]
        index[sym_key].append({
            'expiry': exp,
            'obs': len(rows),
            'first_date': min(dates),
            'last_date': max(dates),
        })

    # Sort by expiry date ascending
    index[sym_key].sort(key=lambda x: x['expiry'])
    print(f'[{sym_key}] {len(index[sym_key])} contracts written')

# Save the lightweight index
save('contract_index.json', index)

# Report file sizes
idx_size = os.path.getsize('docs/data/contract_index.json')
files = list(contract_dir.glob('*.json'))
sizes = [os.path.getsize(f) for f in files]
print(f'contract_index.json: {idx_size/1024:.1f} KB')
print(f'Per-contract files: {len(files)} files, avg {sum(sizes)/len(sizes)/1024:.1f} KB, max {max(sizes)/1024:.1f} KB')
conn.close()
print('DONE')
