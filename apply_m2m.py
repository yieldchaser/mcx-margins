import codecs

def find_idx(lines, search_str):
    for i, l in enumerate(lines):
        if search_str in l: return i
    raise ValueError(f"Not found: {search_str}")

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'r', 'utf-8') as f:
    lines = f.readlines()

# 1. CSS
idx1 = find_idx(lines, '.calc-fees-panel input[type="checkbox"] { accent-color: var(--accent); }')
lines[idx1] = '.calc-fees-panel input[type="checkbox"] { accent-color: var(--accent); }\n.calc-mode-badge {\n  display: inline-block;\n  font-size: 9px; font-weight: 700; letter-spacing: 0.07em;\n  padding: 1px 5px; border-radius: 3px;\n  background: rgba(56,139,253,0.18); color: var(--accent);\n  margin-left: 5px; vertical-align: middle;\n  transition: background 0.2s, color 0.2s;\n}\n.calc-mode-badge.is-off {\n  background: rgba(139,148,158,0.15); color: var(--text-muted);\n}\n'

# 2. HTML Panel
idx2 = find_idx(lines, '              <div id="calcFeesPanel" class="calc-fees-panel" aria-hidden="true">')
lines[idx2] = '              <div id="calcFeesPanel" class="calc-fees-panel" aria-hidden="true">\n                <label class="has-tooltip" data-tooltip-key="calc-m2m-mode">\n                  <span>Dynamic M2M capital accounting <span class="calc-mode-badge" id="calcM2MBadge">ON</span></span>\n                  <input type="checkbox" id="calcM2MEnabled" checked>\n                </label>\n                <div id="calcM2MHint" style="margin-bottom:8px;padding:6px 8px;background:rgba(56,139,253,0.07);border:1px solid rgba(56,139,253,0.18);border-radius:4px;font-size:10px;line-height:1.5;color:var(--text-muted);">\n                  Real-world mode: daily M2M profits/losses adjust your available capital. Margin calls are measured against your live ledger balance, not the fixed initial deposit.\n                </div>\n'

# 3. JS Event
idx3 = find_idx(lines, '  document.getElementById(\'calcFeeBrokerage\')?.addEventListener(\'input\', () => window.updateCalc());')
lines[idx3] = '  document.getElementById(\'calcFeeBrokerage\')?.addEventListener(\'input\', () => window.updateCalc());\n  document.getElementById(\'calcM2MEnabled\')?.addEventListener(\'change\', () => {\n    const on = !!document.getElementById(\'calcM2MEnabled\')?.checked;\n    const badge = document.getElementById(\'calcM2MBadge\');\n    if (badge) { badge.textContent = on ? \'ON\' : \'OFF\'; badge.classList.toggle(\'is-off\', !on); }\n    const hint = document.getElementById(\'calcM2MHint\');\n    if (hint) hint.style.display = on ? \'block\' : \'none\';\n    window.updateCalc();\n  });\n'

# 4. JS Loop Header
idx4 = find_idx(lines, '  const cumPL = [], dailyPL = [], drawdownPath = [], marginPath = [], marginUtilPath = [], labels = [];')
lines[idx4] = '  // isM2M: real-world mode \u2014 daily M2M settlement adjusts the available ledger balance each day\n  const isM2M = !!document.getElementById(\'calcM2MEnabled\')?.checked;\n  const cumPL = [], dailyPL = [], drawdownPath = [], marginPath = [], marginUtilPath = [], labels = [];\n'
idx5 = find_idx(lines, '  let marginCallDate = null, marginCallReq = 0;')
lines[idx5] = '  let marginCallDate = null, marginCallReq = 0, marginCallAvail = 0;\n'

# 5. JS Loop Body
idx6 = find_idx(lines, '      marginPath.push(curMargin);')
lines[idx6] = '      // Dynamic M2M: available capital = initial capital +/- cumulative P/L settled to date.\n      // Math.max(0,...) clamps to zero \u2014 a real broker would have squared off before a negative balance.\n      const availableCapital = isM2M ? Math.max(0, capital + pl) : capital;\n      marginPath.push(curMargin);\n'
idx7 = find_idx(lines, '      const util = capital > 0 ? (curMargin / capital) * 100 : 0;')
lines[idx7] = '      const util = availableCapital > 0 ? (curMargin / availableCapital) * 100 : 999;\n'
idx8 = find_idx(lines, '      if (!marginCallDate && curMargin > capital) {')
lines[idx8] = '      if (!marginCallDate && curMargin > availableCapital) {\n'
idx9 = find_idx(lines, '        marginCallReq = curMargin;')
lines[idx9] = '        marginCallReq = curMargin;\n        marginCallAvail = availableCapital; // snapshot live ledger balance at breach\n'

# 6. mcNotice
idx10 = find_idx(lines, '    mcNotice.innerHTML = `<span class="calc-status__title">Margin call would have triggered on ${marginCallDate}</span><div class="calc-status__detail">Required margin \u20b9${fmtNum(marginCallReq, 0)} exceeded available capital \u20b9${fmtNum(capital, 0)}.</div>`;')
lines[idx10] = '    const callCapStr = isM2M\n      ? `live M2M ledger \u20b9${fmtNum(marginCallAvail, 0)} (initial \u20b9${fmtNum(capital, 0)} ${marginCallAvail < capital ? \'− loss absorbed\' : \'+ profit added\'})`\n      : `available capital \u20b9${fmtNum(capital, 0)}`;\n    mcNotice.innerHTML = `<span class="calc-status__title">Margin call would have triggered on ${marginCallDate}</span><div class="calc-status__detail">Required margin \u20b9${fmtNum(marginCallReq, 0)} exceeded ${callCapStr}.</div>`;\n'

# 7. calcInfo
idx11 = find_idx(lines, '  const metaRow = document.getElementById(\'calcMetaRow\');')
lines[idx11] = '  // Dynamic mode footnote \u2014 updates on every recalc to reflect active capital model\n  const infoEl = document.getElementById(\'calcInfo\');\n  if (infoEl) {\n    const modeNote = isM2M\n      ? \'Dynamic M2M: margin calls measured against your live ledger balance.\'\n      : \'Static capital: margin calls measured against fixed initial deposit.\';\n    infoEl.innerHTML = `<span>Backtest only \u00b7 entry/exit at exchange close \u00b7 gross figures unless costs are applied. <em>${modeNote}</em></span>`;\n  }\n\n  const metaRow = document.getElementById(\'calcMetaRow\');\n'

# 8. TOOLTIPS
idx12 = find_idx(lines, '  "calc-fees": {')
lines[idx12] = """  "calc-m2m-mode": {
    title: "Dynamic M2M Capital Accounting",
    body: `Controls how margin calls are evaluated in the backtest:<br><br><strong>ON \u2014 Real-world (default)</strong><br>Each day, cumulative M2M profit/loss is applied to your ledger. A losing streak shrinks your available capital, so margin calls can fire earlier \u2014 exactly as they would on a live MCX/Zerodha account.<br><br><strong>OFF \u2014 Conservative (stress-test)</strong><br>Margin is always checked against your fixed initial capital regardless of daily P/L. The more pessimistic model; useful for worst-case position sizing.<br><br><em>Lot sizing is always fixed at entry in both modes \u2014 intra-trade gains don't auto-buy more lots.</em>`
  },
  "calc-fees": {
"""

with codecs.open(r'c:\Users\Dell\Github\mcx-margins\docs\index.html', 'w', 'utf-8') as f:
    f.writelines(lines)

print("Done. All patches applied cleanly.")
