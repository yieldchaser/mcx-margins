import codecs

def find_idx(lines, search_str):
    for i, l in enumerate(lines):
        if search_str in l: return i
    raise ValueError(f"Not found: {search_str}")

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'r', 'utf-8') as f:
    lines = f.readlines()

# 1. Update CSS for stat value and unit
idx_value = find_idx(lines, '.calc-stat__value {')
# We replace the whole block to be safe
lines[idx_value] = '.calc-stat__value {\n  font-size: 22px; font-weight: 700; letter-spacing: -0.02em;\n  margin-top: 4px;\n  font-variant-numeric: tabular-nums;\n  font-feature-settings: "tnum";\n  color: var(--text);\n  line-height: 1.15;\n  transition: color 0.25s ease;\n  display: flex; align-items: baseline; gap: 4px;\n}\n.calc-stat__unit {\n  font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; opacity: 0.8;\n}\n'
# Remove the following lines of the old block (lines 292-299)
for i in range(1, 8):
    if idx_value + i < len(lines) and '}' not in lines[idx_value + i]:
        lines[idx_value + i] = ""
    elif idx_value + i < len(lines) and '}' in lines[idx_value + i]:
        lines[idx_value + i] = ""
        break

# 2. Update setStat to use innerHTML
idx_setstat = find_idx(lines, 'const setStat = (id, text, opts) => {')
idx_textcont = find_idx(lines[idx_setstat:], 'el.textContent = text;') + idx_setstat
lines[idx_textcont] = '      el.innerHTML = text;\n'
idx_textcheck = find_idx(lines[idx_setstat:], 'if (el.textContent !== text) {') + idx_setstat
lines[idx_textcheck] = '    if (el.innerHTML !== text) {\n'

# 3. Update resLots call
idx_reslots = find_idx(lines, "setStat('resLots', lots + ' Lots');")
lines[idx_reslots] = "  setStat('resLots', `${lots}<span class=\"calc-stat__unit\">Lots</span>`);\n"

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'w', 'utf-8') as f:
    f.writelines(lines)

print("Fixed '6 Lots' formatting and improved stat card aesthetics.")
