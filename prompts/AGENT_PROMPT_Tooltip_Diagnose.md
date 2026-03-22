# Tooltip Investigation — Diagnose First, Then Fix

## Step 1 — Gather evidence. Do not touch any file yet.

```bash
cd mcx-margins && git pull origin main
```

Run each of these commands and paste the full output before doing anything else:

```bash
# 1. Count every reference to the tooltip overlay element
grep -n "tooltipOverlay\|_ttEl\|ttOverlay\|overlay" docs/index.html | grep -v "<!--"

# 2. Count every variable declaration that could conflict
grep -n "const overlay\|const ttOverlay\|const _ttEl\|let hideTimer\|let ttHideTimer\|let _ttTimer" docs/index.html

# 3. Show the showTooltip function definition
grep -n -A 10 "function showTooltip" docs/index.html

# 4. Show the hideTooltip function definition  
grep -n -A 5 "function hideTooltip" docs/index.html

# 5. Show the attachTooltips function
grep -n -A 20 "function attachTooltips" docs/index.html

# 6. Show every place attachTooltips is called
grep -n "attachTooltips" docs/index.html

# 7. Show every place data-tooltip-key appears in HTML elements
grep -n "data-tooltip-key" docs/index.html

# 8. Count how many card-title elements have has-tooltip class
grep -c "card-title has-tooltip\|has-tooltip.*card-title" docs/index.html

# 9. Show the TOOLTIPS object keys
grep -n '^\s*"[A-Z]' docs/index.html | head -30

# 10. Check if there are any syntax errors by looking at script structure
grep -n "^  const\|^const\|^  let\|^let\|^  var\|^var" docs/index.html | head -40
```

## Step 2 — Based on the output above, identify which of these is the actual problem:

**Hypothesis A** — Variable still declared twice (two `const` pointing to same element ID)
→ Evidence: command 2 shows more than one declaration of the same variable name

**Hypothesis B** — `showTooltip` uses a variable name that doesn't match what was declared
→ Evidence: command 3 shows a variable name inside the function body that doesn't appear in command 2's output

**Hypothesis C** — `attachTooltips()` is never actually called, or called before the DOM element exists
→ Evidence: command 6 shows zero calls, or calls happen before the overlay div is in the HTML

**Hypothesis D** — `data-tooltip-key` attributes were never added to the HTML card-title elements
→ Evidence: command 7 shows few or no results, command 8 shows 0

**Hypothesis E** — The TOOLTIPS object keys don't match the `data-tooltip-key` values in the HTML
→ Evidence: command 7 values don't appear in command 9 output

**Hypothesis F** — A JavaScript syntax error earlier in the script is killing execution before tooltip code runs
→ Evidence: open browser F12 → Console → red error with line number

## Step 3 — Report findings

Write out exactly which hypothesis is confirmed by the evidence. Then state:
- The exact line numbers where the problem exists
- The exact change needed to fix it

Do not make any edits until the diagnosis is written out.

## Step 4 — Fix only what the diagnosis identifies

Make the minimum surgical edit(s) needed. No rewrites, no refactoring.

```bash
git add docs/index.html
git commit -m "fix: tooltips — [describe exact fix based on diagnosis]"
git push
```

## Step 5 — Verify

Open `https://yieldchaser.github.io/mcx-margins/` after deploy.
Open F12 → Console — must show zero red errors.
Hover any card title with ? badge on Overview tab → overlay must appear.
Click Term Structure tab → hover a card title → overlay must appear there too.
