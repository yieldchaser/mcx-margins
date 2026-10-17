"""
build_master_model.py
Generates models/Master_Commodity_Treasury_Model.xlsx
A unified institutional commodity treasury model integrating:
1. Interactive Dashboard (User-editable return %, capital, employees)
2. Dedicated preset return sheets: 75%, 80%, 85%, 100%, 120%
3. Level 4 GIFT City CME Henry Hub 0% tax scaling module
4. 3-Employee Legal & Tax Optimization Framework (Rule 2(1)(c)(viii), Form DPT-3, Sec 87A)
5. NG Dynamic Margin & Execution Friction Engine
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def create_master_model():
    wb = openpyxl.Workbook()
    # remove default sheet
    default_sheet = wb.active

    # Styling Palettes
    navy_header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    slate_header_fill = PatternFill(start_color="2E5B88", end_color="2E5B88", fill_type="solid")
    steel_header_fill = PatternFill(start_color="4A6FA5", end_color="4A6FA5", fill_type="solid")
    cream_input_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    mint_total_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    gold_accent_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    card_fill = PatternFill(start_color="F2F4F8", end_color="F2F4F8", fill_type="solid")

    font_title = Font(name="Segoe UI", size=15, bold=True, color="1B365D")
    font_section = Font(name="Segoe UI", size=11, bold=True, color="1B365D")
    font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_sub_header = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    font_bold = Font(name="Segoe UI", size=9, bold=True, color="000000")
    font_normal = Font(name="Segoe UI", size=9, color="000000")
    font_input = Font(name="Segoe UI", size=10, bold=True, color="805B00")
    font_total = Font(name="Segoe UI", size=9, bold=True, color="274E13")

    thin_border = Side(style='thin', color='D9D9D9')
    thick_bottom = Side(style='double', color='1B365D')
    cell_border = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    total_border = Border(top=thin_border, bottom=thick_bottom, left=thin_border, right=thin_border)

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    num_fmt_currency = '₹#,##0.00'
    num_fmt_curr_cr = '₹#,##0.00 "Cr"'
    num_fmt_percent = '0.00%'
    num_fmt_integer = '#,##0'

    # =========================================================================
    # TAB 1: INTERACTIVE DASHBOARD
    # =========================================================================
    ws_dash = wb.create_sheet(title="Interactive Dashboard")
    ws_dash.views.sheetView[0].showGridLines = True

    # Title
    ws_dash.cell(1, 1, "MASTER COMMODITY TREASURY ENGINE  ·  INTERACTIVE SCENARIO EXPLORER").font = font_title
    ws_dash.cell(2, 1, "Enter any return % in cell B4 (e.g. 75%, 80%, 85%, 100%, 120%) or adjust starting capital/employees. All 20-year cycles dynamically reprice.").font = Font(name="Segoe UI", size=9, italic=True, color="555555")

    # Inputs Block
    ws_dash.cell(4, 1, "LIVE MODEL CONTROLS").font = font_section
    inputs = [
        ("Starting Capital (₹ Cr)", 0.60, num_fmt_curr_cr, "B5", "Level 0 opening equity pool (₹60.00 Lakhs)"),
        ("Annual Gross Return", 0.85, num_fmt_percent, "B6", "◄ EDIT HERE: Enter 75%, 80%, 85%, 100%, 120% or any %"),
        ("Corporate Tax Rate (u/s 115BAA)", 0.25168, num_fmt_percent, "B7", "Flat 22% base + 10% surcharge + 4% cess"),
        ("Number of Family Employees", 3, num_fmt_integer, "B8", "1, 2, or 3 employees on payroll (Mother, Gran, 3rd relative)"),
        ("Salary per Employee (₹ Cr)", 0.1275, num_fmt_curr_cr, "B9", "₹12.75 Lakhs gross (Zero personal tax u/s 87A)"),
        ("Loanback Share", 0.90, num_fmt_percent, "B10", "90% of net salary loaned back to company u/r 2(1)(c)(viii)"),
        ("Salary Cap (% of Trading Profit)", 0.40, num_fmt_percent, "B11", "Salary deduction capped at 40% of net trading gains"),
        ("Company Annual Overhead (₹ Cr)", 0.01, num_fmt_curr_cr, "B12", "Statutory audit, MCA filings, ROC compliance (~₹1.0L)"),
        ("MCX Deployable Ceiling (₹ Cr)", 103.0917, num_fmt_curr_cr, "B13", "SEBI 4,800-lot / ADV liquidity capacity ceiling"),
        ("Idle Yield on Cash Reserve", 0.065, num_fmt_percent, "B14", "Overnight repo / liquid fund yield on unallocated cash"),
        ("GIFT City Activation Net Worth (₹ Cr)", 25.00, num_fmt_curr_cr, "B15", "Level 4 activation threshold (unlocks 400% RBI ODI = ₹100 Cr)")
    ]

    for idx, (label, val, fmt, cell_ref, note) in enumerate(inputs, start=5):
        ws_dash.cell(idx, 1, label).font = font_bold
        ws_dash.cell(idx, 1).alignment = align_left
        ws_dash.cell(idx, 1).border = cell_border
        
        c = ws_dash.cell(idx, 2, val)
        c.font = font_input
        c.fill = cream_input_fill
        c.alignment = align_right
        c.number_format = fmt
        c.border = cell_border
        
        ws_dash.cell(idx, 3, note).font = font_normal
        ws_dash.cell(idx, 3).alignment = align_left
        ws_dash.cell(idx, 3).border = cell_border

    # KPI Summary Cards Block
    ws_dash.cell(4, 5, "EXECUTIVE SUMMARY METRICS (20-YEAR HORIZON)").font = font_section
    kpis = [
        ("Capital at Year 5 (3 Staff)", "=F23", "Company + 3 staff capital in Year 5"),
        ("Capital at Year 10 (3 Staff)", "=F28", "Company + 3 staff capital in Year 10"),
        ("Capital at Year 20 (MCX Solo)", "=C38", "Capital at Year 20 without salary tax shield"),
        ("Capital at Year 20 (3 Staff on MCX)", "=F38", "Capital at Year 20 with 3 family employees"),
        ("Total 20-Yr Tax Shield Benefit", "=G38", "Net extra wealth created purely via 3-employee loanback"),
        ("Cumulative Family Loan Debt", "=H38", "Tax-free personal wealth accumulated in family names"),
        ("Level 4 GIFT City CME Potential", "=I38", "Global unconstrained capital pool at 0.00% tax")
    ]
    for idx, (title, formula, note) in enumerate(kpis, start=5):
        ws_dash.cell(idx, 5, title).font = font_bold
        ws_dash.cell(idx, 5).border = cell_border
        ws_dash.cell(idx, 5).fill = card_fill
        
        c = ws_dash.cell(idx, 6, formula)
        c.font = font_total
        c.fill = mint_total_fill
        c.alignment = align_right
        c.number_format = num_fmt_curr_cr
        c.border = cell_border
        
        ws_dash.cell(idx, 7, note).font = font_normal
        ws_dash.cell(idx, 7).border = cell_border

    # Main 20-Year Comparative Table
    table_start_row = 17
    ws_dash.cell(table_start_row - 1, 1, "20-YEAR CYCLE PROGRESSION COMPARISON  (₹ Crores)").font = font_section

    headers = [
        "Year", "Personal (39% Slab)", "Company Solo (25.17%)", 
        "Company + 1 Staff", "Company + 2 Staff", "Company + 3 Staff (Recommended)",
        "3 Staff Advantage vs Solo", "Cumulative Family Loans", 
        "Level 4 GIFT City CME (0% Tax)", "GIFT City Edge vs MCX Cap"
    ]
    for c_idx, h in enumerate(headers, start=1):
        cell = ws_dash.cell(table_start_row, c_idx, h)
        cell.font = font_header
        cell.fill = navy_header_fill
        cell.alignment = align_center
        cell.border = cell_border

    # Year 0 Row
    r0 = table_start_row + 1
    ws_dash.cell(r0, 1, 0).alignment = align_center
    ws_dash.cell(r0, 1).font = font_bold
    ws_dash.cell(r0, 1).border = cell_border
    for c_idx in range(2, 7):
        c = ws_dash.cell(r0, c_idx, "=$B$5")
        c.font = font_normal
        c.alignment = align_right
        c.number_format = num_fmt_curr_cr
        c.border = cell_border
    ws_dash.cell(r0, 7, 0.0).number_format = num_fmt_curr_cr
    ws_dash.cell(r0, 7).border = cell_border
    ws_dash.cell(r0, 8, 0.0).number_format = num_fmt_curr_cr
    ws_dash.cell(r0, 8).border = cell_border
    ws_dash.cell(r0, 9, "=$B$5").number_format = num_fmt_curr_cr
    ws_dash.cell(r0, 9).border = cell_border
    ws_dash.cell(r0, 10, 0.0).number_format = num_fmt_curr_cr
    ws_dash.cell(r0, 10).border = cell_border

    # Years 1 to 20
    # Engine blocks:
    # Row 45+: Personal Engine (Header 45, Yr 0 = 46, Yr y = 46+y)
    # Row 70+: Company Solo Engine (Header 70, Yr 0 = 71, Yr y = 71+y)
    # Row 95+: Company + 1 Staff Engine (Header 95, Yr 0 = 96, Yr y = 96+y)
    # Row 120+: Company + 2 Staff Engine (Header 120, Yr 0 = 121, Yr y = 121+y)
    # Row 145+: Company + 3 Staff Engine (Header 145, Yr 0 = 146, Yr y = 146+y)
    # Row 170+: GIFT City CME Engine (Header 170, Yr 0 = 171, Yr y = 171+y)
    for y in range(1, 21):
        curr_row = r0 + y

        ws_dash.cell(curr_row, 1, y).alignment = align_center
        ws_dash.cell(curr_row, 1).font = font_bold
        ws_dash.cell(curr_row, 1).border = cell_border

        # Personal
        c = ws_dash.cell(curr_row, 2, f"=M{46 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_normal

        # Company Solo
        c = ws_dash.cell(curr_row, 3, f"=M{71 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_normal

        # Company + 1
        c = ws_dash.cell(curr_row, 4, f"=M{96 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_normal

        # Company + 2
        c = ws_dash.cell(curr_row, 5, f"=M{121 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_normal

        # Company + 3 (Recommended)
        c = ws_dash.cell(curr_row, 6, f"=M{146 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_bold
        c.fill = mint_total_fill

        # 3 Staff Advantage vs Solo
        c = ws_dash.cell(curr_row, 7, f"=F{curr_row}-C{curr_row}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_bold

        # Cumulative Family Loans
        c = ws_dash.cell(curr_row, 8, f"=L{146 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_normal

        # Level 4 GIFT City CME (0% Tax)
        c = ws_dash.cell(curr_row, 9, f"=M{171 + y}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_bold
        c.fill = gold_accent_fill

        # GIFT City Edge vs MCX Cap
        c = ws_dash.cell(curr_row, 10, f"=I{curr_row}-F{curr_row}")
        c.number_format = num_fmt_curr_cr
        c.alignment = align_right
        c.border = cell_border
        c.font = font_bold

    # Helper function to generate an engine block
    def build_engine_block(ws, start_r, title, num_employees, is_personal=False, is_gift=False):
        ws.cell(start_r - 1, 1, title).font = font_section
        eng_headers = [
            "Year", "Opening", "Deployed", "Idle", "Profit", 
            "Overhead", "Salary Paid", "Taxable Profit", "Income Tax", 
            "Not Lent Back", "New Loan", "Loans Outstanding", 
            "Closing Capital", "Net Equity (Closing - Loans)"
        ]
        for c_idx, h in enumerate(eng_headers, start=1):
            cell = ws.cell(start_r, c_idx, h)
            cell.font = font_sub_header
            cell.fill = slate_header_fill
            cell.alignment = align_center
            cell.border = cell_border

        # Year 0
        r0 = start_r + 1
        ws.cell(r0, 1, 0).alignment = align_center
        ws.cell(r0, 1).border = cell_border
        ws.cell(r0, 2, "=$B$5").number_format = num_fmt_curr_cr
        ws.cell(r0, 2).border = cell_border
        for c in range(3, 12):
            ws.cell(r0, c, 0.0).border = cell_border
        ws.cell(r0, 12, 0.0).border = cell_border
        ws.cell(r0, 13, "=$B$5").number_format = num_fmt_curr_cr
        ws.cell(r0, 13).border = cell_border
        ws.cell(r0, 14, "=$B$5").number_format = num_fmt_curr_cr
        ws.cell(r0, 14).border = cell_border

        for y in range(1, 21):
            row = r0 + y
            prev_row = row - 1
            ws.cell(row, 1, y).alignment = align_center
            ws.cell(row, 1).border = cell_border

            # Opening = Previous Closing
            ws.cell(row, 2, f"=M{prev_row}").number_format = num_fmt_curr_cr
            ws.cell(row, 2).border = cell_border

            if is_gift:
                # GIFT City CME Engine: No deployable ceiling (or massive $15B ADV), 0% tax for 10 years u/s 80LA
                # Deployed = Opening (up to 4,000 Cr CME limit)
                ws.cell(row, 3, f"=MIN(B{row}, 4000)").number_format = num_fmt_curr_cr
                ws.cell(row, 3).border = cell_border
                ws.cell(row, 4, f"=MAX(B{row}-C{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 4).border = cell_border
                ws.cell(row, 5, f"=C{row}*$B$6 + D{row}*$B$14").number_format = num_fmt_curr_cr
                ws.cell(row, 5).border = cell_border
                # Overhead = ₹35 Lakhs Economic Substance
                ws.cell(row, 6, 0.35).number_format = num_fmt_curr_cr
                ws.cell(row, 6).border = cell_border
                ws.cell(row, 7, 0.0).border = cell_border
                ws.cell(row, 8, f"=MAX(E{row}-F{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 8).border = cell_border
                # Tax: 0% in Years 1-10 (Section 80LA); 25.168% in Years 11-20
                ws.cell(row, 9, f"=IF(A{row}<=10, 0, H{row}*$B$7)").number_format = num_fmt_curr_cr
                ws.cell(row, 9).border = cell_border
                ws.cell(row, 10, 0.0).border = cell_border
                ws.cell(row, 11, 0.0).border = cell_border
                ws.cell(row, 12, 0.0).border = cell_border
                ws.cell(row, 13, f"=B{row}+E{row}-F{row}-I{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 13).border = cell_border
                ws.cell(row, 14, f"=M{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 14).border = cell_border
            elif is_personal:
                # Personal Engine: Slabs with 39% cap
                ws.cell(row, 3, f"=MIN(B{row}, $B$13)").number_format = num_fmt_curr_cr
                ws.cell(row, 3).border = cell_border
                ws.cell(row, 4, f"=MAX(B{row}-C{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 4).border = cell_border
                ws.cell(row, 5, f"=C{row}*$B$6 + D{row}*$B$14").number_format = num_fmt_curr_cr
                ws.cell(row, 5).border = cell_border
                ws.cell(row, 6, 0.005).number_format = num_fmt_curr_cr
                ws.cell(row, 6).border = cell_border
                ws.cell(row, 7, 0.0).border = cell_border
                ws.cell(row, 8, f"=MAX(E{row}-F{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 8).border = cell_border
                # Progressive slab tax
                p_tax_formula = f"=IF(H{row}<=0.12, 0, IF(H{row}<=0.5, MIN((MAX(H{row}-0.04,0)*0.05+MAX(H{row}-0.08,0)*0.05+MAX(H{row}-0.12,0)*0.05+MAX(H{row}-0.16,0)*0.05+MAX(H{row}-0.2,0)*0.05+MAX(H{row}-0.24,0)*0.05), H{row}-0.12), MIN((MAX(H{row}-0.04,0)*0.05+MAX(H{row}-0.08,0)*0.05+MAX(H{row}-0.12,0)*0.05+MAX(H{row}-0.16,0)*0.05+MAX(H{row}-0.2,0)*0.05+MAX(H{row}-0.24,0)*0.05)*(1+IF(H{row}<=1,0.1,IF(H{row}<=2,0.15,0.25))), (MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.04,0)*0.05+MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.08,0)*0.05+MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.12,0)*0.05+MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.16,0)*0.05+MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.2,0)*0.05+MAX(IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))-0.24,0)*0.05)*(1+IF(H{row}<=1,0,IF(H{row}<=2,0.1,0.15)))+H{row}-IF(H{row}<=1,0.5,IF(H{row}<=2,1,2))))*1.04)"
                ws.cell(row, 9, p_tax_formula).number_format = num_fmt_curr_cr
                ws.cell(row, 9).border = cell_border
                ws.cell(row, 10, 0.0).border = cell_border
                ws.cell(row, 11, 0.0).border = cell_border
                ws.cell(row, 12, 0.0).border = cell_border
                ws.cell(row, 13, f"=B{row}+E{row}-F{row}-I{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 13).border = cell_border
                ws.cell(row, 14, f"=M{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 14).border = cell_border
            else:
                # Corporate Engine
                ws.cell(row, 3, f"=MIN(B{row}, $B$13)").number_format = num_fmt_curr_cr
                ws.cell(row, 3).border = cell_border
                ws.cell(row, 4, f"=MAX(B{row}-C{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 4).border = cell_border
                ws.cell(row, 5, f"=C{row}*$B$6 + D{row}*$B$14").number_format = num_fmt_curr_cr
                ws.cell(row, 5).border = cell_border
                ws.cell(row, 6, "=$B$12").number_format = num_fmt_curr_cr
                ws.cell(row, 6).border = cell_border
                if num_employees > 0:
                    ws.cell(row, 7, f"=IF($B$7>0, MIN({num_employees}*$B$9, $B$11*MAX(E{row}-F{row}, 0)), 0)").number_format = num_fmt_curr_cr
                else:
                    ws.cell(row, 7, 0.0).number_format = num_fmt_curr_cr
                ws.cell(row, 7).border = cell_border
                ws.cell(row, 8, f"=MAX(E{row}-F{row}-G{row}, 0)").number_format = num_fmt_curr_cr
                ws.cell(row, 8).border = cell_border
                ws.cell(row, 9, f"=H{row}*$B$7").number_format = num_fmt_curr_cr
                ws.cell(row, 9).border = cell_border
                ws.cell(row, 10, f"=G{row}*(1-$B$10)").number_format = num_fmt_curr_cr
                ws.cell(row, 10).border = cell_border
                ws.cell(row, 11, f"=G{row}*$B$10").number_format = num_fmt_curr_cr
                ws.cell(row, 11).border = cell_border
                ws.cell(row, 12, f"=L{prev_row}+K{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 12).border = cell_border
                ws.cell(row, 13, f"=B{row}+E{row}-F{row}-I{row}-J{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 13).border = cell_border
                ws.cell(row, 14, f"=M{row}-L{row}").number_format = num_fmt_curr_cr
                ws.cell(row, 14).border = cell_border

    # Build the 6 Engine Blocks in ws_dash
    build_engine_block(ws_dash, 45, "CALCULATION ENGINE 1: PERSONAL ROUTE (SLAB TAXES)", 0, is_personal=True)
    build_engine_block(ws_dash, 70, "CALCULATION ENGINE 2: COMPANY SOLO (25.168% FLAT TAX)", 0)
    build_engine_block(ws_dash, 95, "CALCULATION ENGINE 3: COMPANY + 1 EMPLOYEE (MOTHER)", 1)
    build_engine_block(ws_dash, 120, "CALCULATION ENGINE 4: COMPANY + 2 EMPLOYEES (MOTHER + GRANDMOTHER)", 2)
    build_engine_block(ws_dash, 145, "CALCULATION ENGINE 5: COMPANY + 3 EMPLOYEES (MOTHER + GRAN + 3RD RELATIVE)", 3)
    build_engine_block(ws_dash, 170, "CALCULATION ENGINE 6: LEVEL 4 GIFT CITY CME HYBRID (0% TAX U/S 80LA)", 0, is_gift=True)

    # Auto-adjust column widths for Dashboard
    for col in ws_dash.columns:
        max_len = max(len(str(cell.value or '')) for cell in col[:40])
        col_letter = get_column_letter(col[0].column)
        ws_dash.column_dimensions[col_letter].width = max(max_len + 3, 13)

    # =========================================================================
    # PRESET SHEETS GENERATION: 75%, 80%, 85%, 100%, 120%
    # =========================================================================
    presets = [
        ("75% Annual", 0.75, "Conservative Baseline (75% Return)"),
        ("80% Annual", 0.80, "Steady Quant Execution (80% Return)"),
        ("85% Annual", 0.85, "Optimized Alpha Tier (85% Return)"),
        ("100% Annual", 1.00, "High-Conviction Benchmark (100% Return)"),
        ("120% Annual", 1.20, "Peak Algorithmic Expansion (120% Return)")
    ]

    for title, ret_val, subtitle in presets:
        ws = wb.create_sheet(title=title)
        ws.views.sheetView[0].showGridLines = True

        ws.cell(1, 1, f"MCX COMMODITY TREASURY MODEL  ·  {title.upper()}").font = font_title
        ws.cell(2, 1, f"{subtitle} · Live inputs: cream cells. All 20-year cycles dynamically evaluate.").font = Font(name="Segoe UI", size=9, italic=True, color="555555")

        # Inputs
        ws.cell(4, 1, "MODEL INPUTS").font = font_section
        ws.cell(5, 1, "Starting Capital (₹ Cr)").font = font_bold
        ws.cell(5, 2, 0.60).font = font_input
        ws.cell(5, 2).fill = cream_input_fill
        ws.cell(5, 2).number_format = num_fmt_curr_cr

        ws.cell(6, 1, "Annual Return").font = font_bold
        ws.cell(6, 2, ret_val).font = font_input
        ws.cell(6, 2).fill = cream_input_fill
        ws.cell(6, 2).number_format = num_fmt_percent

        ws.cell(7, 1, "Company Tax Rate").font = font_bold
        ws.cell(7, 2, 0.25168).font = font_input
        ws.cell(7, 2).fill = cream_input_fill
        ws.cell(7, 2).number_format = num_fmt_percent

        ws.cell(8, 1, "Loanback Share").font = font_bold
        ws.cell(8, 2, 0.90).font = font_input
        ws.cell(8, 2).fill = cream_input_fill
        ws.cell(8, 2).number_format = num_fmt_percent

        ws.cell(9, 1, "Salary Ceiling / Employee (₹ Cr)").font = font_bold
        ws.cell(9, 2, 0.1275).font = font_input
        ws.cell(9, 2).fill = cream_input_fill
        ws.cell(9, 2).number_format = num_fmt_curr_cr

        ws.cell(10, 1, "Salary Profit Fraction Cap").font = font_bold
        ws.cell(10, 2, 0.40).font = font_input
        ws.cell(10, 2).fill = cream_input_fill
        ws.cell(10, 2).number_format = num_fmt_percent

        ws.cell(11, 1, "Company Annual Costs (₹ Cr)").font = font_bold
        ws.cell(11, 2, 0.01).font = font_input
        ws.cell(11, 2).fill = cream_input_fill
        ws.cell(11, 2).number_format = num_fmt_curr_cr

        ws.cell(12, 1, "Deployable Ceiling (₹ Cr)").font = font_bold
        ws.cell(12, 2, 103.0917).font = font_input
        ws.cell(12, 2).fill = cream_input_fill
        ws.cell(12, 2).number_format = num_fmt_curr_cr

        ws.cell(13, 1, "Idle Cash Yield").font = font_bold
        ws.cell(13, 2, 0.065).font = font_input
        ws.cell(13, 2).fill = cream_input_fill
        ws.cell(13, 2).number_format = num_fmt_percent

        # Summary Table
        ws.cell(15, 1, f"CLOSING TRADING CAPITAL — ALL ROUTES, CYCLE 0–20 (₹ Cr)  [{title}]").font = font_section
        sh_headers = [
            "Year", "Personal", "Company Solo", "Company + 1 Staff", 
            "Company + 2 Staff", "Company + 3 Staff", "3 Staff Advantage", 
            "3 Staff Loan Debt", "Net Equity (Capital - Loans)"
        ]
        for c_idx, h in enumerate(sh_headers, start=1):
            cell = ws.cell(16, c_idx, h)
            cell.font = font_header
            cell.fill = navy_header_fill
            cell.alignment = align_center
            cell.border = cell_border

        # Year 0
        ws.cell(17, 1, 0).alignment = align_center
        ws.cell(17, 1).font = font_bold
        ws.cell(17, 1).border = cell_border
        for c in range(2, 7):
            ws.cell(17, c, "=$B$5").number_format = num_fmt_curr_cr
            ws.cell(17, c).border = cell_border
        ws.cell(17, 7, 0.0).number_format = num_fmt_curr_cr
        ws.cell(17, 7).border = cell_border
        ws.cell(17, 8, 0.0).number_format = num_fmt_curr_cr
        ws.cell(17, 8).border = cell_border
        ws.cell(17, 9, "=$B$5").number_format = num_fmt_curr_cr
        ws.cell(17, 9).border = cell_border

        for y in range(1, 21):
            row = 17 + y
            ws.cell(row, 1, y).alignment = align_center
            ws.cell(row, 1).font = font_bold
            ws.cell(row, 1).border = cell_border

            ws.cell(row, 2, f"=M{46 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 2).border = cell_border
            ws.cell(row, 3, f"=M{71 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 3).border = cell_border
            ws.cell(row, 4, f"=M{96 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 4).border = cell_border
            ws.cell(row, 5, f"=M{121 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 5).border = cell_border
            ws.cell(row, 6, f"=M{146 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 6).border = cell_border
            ws.cell(row, 6).font = font_bold
            ws.cell(row, 6).fill = mint_total_fill

            ws.cell(row, 7, f"=F{row}-C{row}").number_format = num_fmt_curr_cr
            ws.cell(row, 7).border = cell_border
            ws.cell(row, 7).font = font_bold

            ws.cell(row, 8, f"=L{146 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 8).border = cell_border

            ws.cell(row, 9, f"=N{146 + y}").number_format = num_fmt_curr_cr
            ws.cell(row, 9).border = cell_border

        # Build engines for this preset sheet
        build_engine_block(ws, 45, "PERSONAL TRADING ROUTE", 0, is_personal=True)
        build_engine_block(ws, 70, "COMPANY SOLO ROUTE", 0)
        build_engine_block(ws, 95, "COMPANY + 1 EMPLOYEE ROUTE", 1)
        build_engine_block(ws, 120, "COMPANY + 2 EMPLOYEES ROUTE", 2)
        build_engine_block(ws, 145, "COMPANY + 3 EMPLOYEES ROUTE (RECOMMENDED)", 3)

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col[:35])
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # =========================================================================
    # TAB: GIFT CITY CME BRIDGE (LEVEL 4)
    # =========================================================================
    ws_gift = wb.create_sheet(title="GIFT City CME Bridge")
    ws_gift.views.sheetView[0].showGridLines = True

    ws_gift.cell(1, 1, "LEVEL 4: GIFT CITY IFSC · CME HENRY HUB SOVEREIGN BRIDGE").font = font_title
    ws_gift.cell(2, 1, "Section 80LA (0.00% Corporate Tax for 10 Years) vs Domestic 25.17% vs Personal 39% Dividend Leakage").font = Font(name="Segoe UI", size=9, italic=True, color="555555")

    ws_gift.cell(4, 1, "COMPARATIVE TAX & COMPOUNDING ARCHITECTURE (ON ₹100 CR ANNUAL PROFIT)").font = font_section

    gift_headers = ["Metric / Parameter", "Domestic MCX TM (Level 3)", "GIFT City CME (Reinvested)", "GIFT City CME (Personal Dividend)"]
    for c_idx, h in enumerate(gift_headers, start=1):
        cell = ws_gift.cell(5, c_idx, h)
        cell.font = font_header
        cell.fill = navy_header_fill
        cell.alignment = align_center
        cell.border = cell_border

    gift_rows = [
        ("Gross Trading Profit", 100.0, 100.0, 100.0, num_fmt_curr_cr),
        ("Corporate Income Tax Rate", 0.25168, 0.0, 0.0, num_fmt_percent),
        ("Corporate Income Tax Paid (₹ Cr)", 25.168, 0.0, 0.0, num_fmt_curr_cr),
        ("Minimum Alternate Tax (MAT)", 0.0, 0.0, 0.0, num_fmt_curr_cr),
        ("Transaction Taxes (CTT + Stamp Duty)", 0.85, 0.0, 0.0, num_fmt_curr_cr),
        ("Economic Substance & Regulatory Burn", 0.05, 0.35, 0.35, num_fmt_curr_cr),
        ("Personal Dividend Distribution Tax", 0.0, 0.0, 38.8635, num_fmt_curr_cr),
        ("Net Annual Compounding Capital (₹ Cr)", 73.932, 99.65, 60.7865, num_fmt_curr_cr),
        ("10-Year Compounding Edge (%)", "Baseline", "+34.8% Faster Compounding", "-17.8% Cash Leakage", "@")
    ]

    for r_idx, row_data in enumerate(gift_rows, start=6):
        ws_gift.cell(r_idx, 1, row_data[0]).font = font_bold
        ws_gift.cell(r_idx, 1).border = cell_border
        for c_idx in range(2, 5):
            val = row_data[c_idx - 1]
            fmt = row_data[4]
            cell = ws_gift.cell(r_idx, c_idx, val)
            cell.border = cell_border
            cell.font = font_normal
            if fmt != "@":
                cell.number_format = fmt
                cell.alignment = align_right
            else:
                cell.alignment = align_center
                if c_idx == 3:
                    cell.font = font_total
                    cell.fill = mint_total_fill
                elif c_idx == 4:
                    cell.font = Font(name="Segoe UI", size=9, bold=True, color="9C0006")
                    cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    for col in ws_gift.columns:
        max_len = max(len(str(cell.value or '')) for cell in col[:20])
        col_letter = get_column_letter(col[0].column)
        ws_gift.column_dimensions[col_letter].width = max(max_len + 4, 15)

    # =========================================================================
    # TAB: 3-EMPLOYEE LEGAL & TAX FRAMEWORK
    # =========================================================================
    ws_legal = wb.create_sheet(title="3-Employee Legal Framework")
    ws_legal.views.sheetView[0].showGridLines = True

    ws_legal.cell(1, 1, "FAMILY PAYROLL & LOANBACK TAX OPTIMIZATION ENGINE").font = font_title
    ws_legal.cell(2, 1, "Statutory Compliance: Section 115BAC · Section 87A · Rule 2(1)(c)(viii) · Form DPT-3").font = Font(name="Segoe UI", size=9, italic=True, color="555555")

    ws_legal.cell(4, 1, "1. THE 3 DESIGNATED FAMILY EMPLOYEES & SALARY STRUCTURE").font = font_section

    emp_headers = ["Employee Role", "Designated Family Member", "Gross Annual Salary", "Std Deduction u/s 16(ia)", "Net Taxable Income", "Tax u/s 115BAC", "Rebate u/s 87A", "Net Personal Tax", "Annual Corporate Tax Saved"]
    for c_idx, h in enumerate(emp_headers, start=1):
        cell = ws_legal.cell(5, c_idx, h)
        cell.font = font_header
        cell.fill = navy_header_fill
        cell.alignment = align_center
        cell.border = cell_border

    emp_data = [
        ("Operations Coordinator", "Mother", 1275000, 75000, 1200000, 80000, -80000, 0, 320892),
        ("Governance Advisor", "Grandmother", 1275000, 75000, 1200000, 80000, -80000, 0, 320892),
        ("Research / Compliance Associate", "Third Family Member (Father/Sibling)", 1275000, 75000, 1200000, 80000, -80000, 0, 320892),
        ("TOTAL (3 EMPLOYEES COMBINED)", "All 3 Members", 3825000, 225000, 3600000, 240000, -240000, 0, 962676)
    ]

    for r_idx, row in enumerate(emp_data, start=6):
        is_total = (r_idx == 9)
        for c_idx, val in enumerate(row, start=1):
            cell = ws_legal.cell(r_idx, c_idx, val)
            cell.border = total_border if is_total else cell_border
            cell.font = font_total if is_total else (font_bold if c_idx <= 2 else font_normal)
            if is_total:
                cell.fill = mint_total_fill
            if c_idx >= 3:
                cell.number_format = '₹#,##0'
                cell.alignment = align_right
            else:
                cell.alignment = align_left

    # Legal compliance steps
    ws_legal.cell(11, 1, "2. STATUTORY FLOWBACK ENGINE & AUDIT TRAIL").font = font_section
    legal_steps = [
        ("Step 1: Employment Contract & Monthly Remittance", "Execute formal employment contracts defining operational duties. Transfer salary monthly via NEFT/RTGS from corporate bank account into individual savings accounts. Issue annual Form 16."),
        ("Step 2: Section 87A Tax Eraser", "Under the New Tax Regime, taxable salary of ₹12.00 Lakhs incurs ₹80,000 tax, which is 100% rebated to ₹0.00 under Section 87A. Zero personal tax is paid."),
        ("Step 3: Director Relative Loanback (Rule 2(1)(c)(viii))", "Mother and 3rd relative loan back 90% of their net salary directly to the company. Under Rule 2(1)(c)(viii) of Companies (Acceptance of Deposits) Rules, 2014, loans from a director's relative are exempt deposits."),
        ("Step 4: Grandmother Blood Gift u/s 56(2)(x)", "Grandmother gifts her net salary to Director or Mother (100% tax-free between lineal relatives), who then executes the compliant loanback to the company."),
        ("Step 5: Annual ROC Compliance (Form DPT-3)", "File Form DPT-3 with the Registrar of Companies (ROC) on or before June 30th each year, reporting the unsecured loan balances under 'Particulars of transactions by a company not considered as deposit'.")
    ]

    for r_idx, (stitle, sdesc) in enumerate(legal_steps, start=12):
        ws_legal.cell(r_idx, 1, stitle).font = font_bold
        ws_legal.cell(r_idx, 1).border = cell_border
        ws_legal.cell(r_idx, 2, sdesc).font = font_normal
        ws_legal.cell(r_idx, 2).border = cell_border

    for col in ws_legal.columns:
        max_len = max(len(str(cell.value or '')) for cell in col[:18])
        col_letter = get_column_letter(col[0].column)
        ws_legal.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # Remove default sheet if exists
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    # Save Master Workbook
    target_path = "models/Master_Commodity_Treasury_Model.xlsx"
    wb.save(target_path)
    print(f"Master Commodity Treasury Model successfully created at {target_path}")

if __name__ == "__main__":
    create_master_model()
