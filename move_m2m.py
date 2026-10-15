import codecs

def find_idx(lines, search_str):
    for i, l in enumerate(lines):
        if search_str in l: return i
    raise ValueError(f"Not found: {search_str}")

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'r', 'utf-8') as f:
    lines = f.readlines()

# 1. Remove from Fees Panel
# We look for the start of the panel: '<div id="calcFeesPanel" class="calc-fees-panel" aria-hidden="true">'
# It should be followed by the label, input, and hint.
idx_fees = find_idx(lines, '<div id="calcFeesPanel" class="calc-fees-panel" aria-hidden="true">')

# We know the next lines from my previous script:
# idx_fees + 1: <label class="has-tooltip" data-tooltip-key="calc-m2m-mode">
# idx_fees + 2:   <span>Dynamic M2M capital accounting <span class="calc-mode-badge" id="calcM2MBadge">ON</span></span>
# idx_fees + 3:   <input type="checkbox" id="calcM2MEnabled" checked>
# idx_fees + 4: </label>
# idx_fees + 5: <div id="calcM2MHint" ...>
# idx_fees + 6:   Real-world mode: ...
# idx_fees + 7: </div>
# We can just blank them out.
for i in range(1, 8):
    lines[idx_fees + i] = ""

# 2. Add to Scope Row
# We look for '<span class="scope-chip"><strong>Sizing</strong> <span data-fill="lotmode">Max</span></span>'
idx_sizing = find_idx(lines, '<span class="scope-chip"><strong>Sizing</strong> <span data-fill="lotmode">Max</span></span>')

new_chip = '            <label class="scope-chip has-tooltip" data-tooltip-key="calc-m2m-mode" style="cursor:pointer; display:inline-flex; align-items:center; gap:6px;">\n              <strong>M2M Capital</strong>\n              <input type="checkbox" id="calcM2MEnabled" checked style="margin:0; cursor:pointer;">\n              <span class="calc-mode-badge" id="calcM2MBadge" style="margin-left:0;">ON</span>\n            </label>\n'

# insert after sizing
lines.insert(idx_sizing + 1, new_chip)

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'w', 'utf-8') as f:
    f.writelines(lines)

print("Moved M2M toggle to Scope Row cleanly.")
