import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import numpy as np
import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

wb_path = 'models/Master_Commodity_Treasury_Model.xlsx'
wb = openpyxl.load_workbook(wb_path)

sheet_name = 'Seasonality & Asymmetry'
if sheet_name in wb.sheetnames:
    del wb[sheet_name]

ws = wb.create_sheet(title=sheet_name)
ws.views.sheetView[0].showGridLines = True

# Styling helpers
font_family = 'Segoe UI'
title_font = Font(name=font_family, size=16, bold=True, color='FFFFFF')
section_font = Font(name=font_family, size=12, bold=True, color='FFFFFF')
header_font = Font(name=font_family, size=10, bold=True, color='FFFFFF')
bold_font = Font(name=font_family, size=10, bold=True, color='000000')
regular_font = Font(name=font_family, size=10, color='000000')
italic_font = Font(name=font_family, size=9, italic=True, color='555555')

navy_fill = PatternFill(start_color='1B365D', end_color='1B365D', fill_type='solid')
slate_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
blue_fill = PatternFill(start_color='2980B9', end_color='2980B9', fill_type='solid')
green_fill = PatternFill(start_color='27AE60', end_color='27AE60', fill_type='solid')
red_fill = PatternFill(start_color='C0392B', end_color='C0392B', fill_type='solid')
light_blue_fill = PatternFill(start_color='EBF5FB', end_color='EBF5FB', fill_type='solid')
light_green_fill = PatternFill(start_color='E8F8F5', end_color='E8F8F5', fill_type='solid')
light_red_fill = PatternFill(start_color='FDEDEC', end_color='FDEDEC', fill_type='solid')
gold_fill = PatternFill(start_color='F39C12', end_color='F39C12', fill_type='solid')

thin_border_side = Side(border_style='thin', color='BDC3C7')
thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
double_bottom_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=Side(border_style='double', color='1B365D'))

# Title Banner
ws.merge_cells('A1:J1')
ws['A1'] = "NATURAL GAS SEASONALITY, ASYMMETRY & THE ROAD TO ₹100 CRORES"
ws['A1'].font = title_font
ws['A1'].fill = navy_fill
ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[1].height = 40

ws.merge_cells('A2:J2')
ws['A2'] = "Empirical Proof: 142 Completed Contracts (2015-2026), 5,067 Daily Contango Spreads, & Year-by-Year ₹100 Cr Simulation"
ws['A2'].font = Font(name=font_family, size=10, italic=True, color='FFFFFF')
ws['A2'].fill = slate_fill
ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[2].height = 24

# SECTION 1: IS SHORTING MATHEMATICALLY SUPERIOR? (THE 5 QUANT PROOFS)
ws.merge_cells('A4:J4')
ws['A4'] = "1. THE 5-DIMENSION QUANT PROOF: IS SHORTING MATHEMATICALLY SUPERIOR TO GOING LONG?"
ws['A4'].font = section_font
ws['A4'].fill = blue_fill
ws['A4'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
ws.row_dimensions[4].height = 26

proof_headers = ['Quant Dimension', 'Long Futures Profile', 'Short Futures Profile', 'Empirical Winner', 'Mathematical Reason & Trading Consequence']
for col_idx, h in enumerate(proof_headers, start=1):
    cell = ws.cell(5, col_idx, h)
    cell.font = header_font
    cell.fill = slate_fill
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cell.border = thin_border
ws.row_dimensions[5].height = 28

proof_data = [
    ("1. Structural Carry & Contango Roll Yield", 
     "-2.96% drag per roll (Longs lose -15% to -24%/yr rolling upward curve)",
     "+2.96% tailwind per roll (Shorts earn +15% to +24%/yr structural carry)",
     "🏆 SHORTS MASSIVELY SUPERIOR",
     "MCX Natural Gas is in Contango 85.2% of the year (Avg spread: +4.03%). Shorts harvest cash roll yield; Longs suffer brutal decay."),
    
    ("2. Contract Directional Win Rate",
     "37.3% of contracts finish net UP over their liquid lifecycle",
     "62.0% of contracts finish net DOWN over their liquid lifecycle",
     "🏆 SHORTS DOMINATE (62% vs 37%)",
     "In 61.3% of contracts, Peak occurs BEFORE Trough. Pre-pricing of risk leads to post-launch downward grinds."),
     
    ("3. Move Velocity & Panic Drops",
     "1.28% move per day (Avg swing: 42.9 days) — Explosive, brief spikes",
     "0.76% move per day (Avg swing: 47.0 days) — Persistent, structural bleed",
     "⚡ LONGS FASTER / SHORTS EASIER TO CATCH",
     "Long squeezes are violent and hard to time; Short grinds offer extended execution windows with lower slippage."),
     
    ("4. Margin Burden & Leverage Efficiency",
     "Margin explodes to 28%-35% during parabolic bull runs (Leverage drops to 2.5x)",
     "Margin averages 17.39% during normal/bearish regimes (Leverage holds at 3.5x-4.0x)",
     "🏆 SHORTS CAPITAL-EFFICIENT",
     "Shorting requires LESS margin capital per notional lot, allowing higher effective leverage without exchange margin calls."),
     
    ("5. Tail Risk & Drawdown Asymmetry",
     "Theoretically unlimited upside (+108% to +220% max legs in 2022/23), downside bounded at 0",
     "Downside bounded by 0 (Max single-leg drop 56.8%), but vulnerable to squeeze gap-ups",
     "🛡️ LONGS HAVE CONVEX TAILS; SHORTS NEED HARD STOPS",
     "Shorts must enforce 25% cash buffer and hard stops to avoid squeeze liquidation; Longs provide asymmetric jackpot legs.")
]

for row_idx, data in enumerate(proof_data, start=6):
    for col_idx, val in enumerate(data, start=1):
        cell = ws.cell(row_idx, col_idx, val)
        cell.font = regular_font
        cell.border = thin_border
        cell.alignment = Alignment(vertical='center', wrap_text=True)
        if col_idx == 4:
            cell.font = bold_font
            if "SHORTS" in val:
                cell.fill = light_red_fill
            elif "LONGS" in val:
                cell.fill = light_green_fill
            else:
                cell.fill = light_blue_fill
    ws.row_dimensions[row_idx].height = 42

# SECTION 2: 12-MONTH CONTRACT SEASONALITY TABLE (2015-2026)
ws.merge_cells('A12:J12')
ws['A12'] = "2. 12-MONTH CONTRACT SEASONALITY & REGIME PLAYBOOK (142 COMPLETED CONTRACTS: 2015-2026)"
ws['A12'].font = section_font
ws['A12'].fill = blue_fill
ws['A12'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
ws.row_dimensions[12].height = 26

seas_headers = ['Month', 'Contracts', 'Avg Trough-to-Peak (Long %)', 'Avg Peak-to-Trough (Short %)', 'Net Contract Change %', '% Contracts Down', '% Short Dominant', 'Avg Days to Swing', 'Avg Daily Volume (Lots)', 'Avg Margin %']
for col_idx, h in enumerate(seas_headers, start=1):
    cell = ws.cell(13, col_idx, h)
    cell.font = header_font
    cell.fill = slate_fill
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cell.border = thin_border
ws.row_dimensions[13].height = 28

seas_data = [
    ('JANUARY', 12, 0.7070, 0.3929, -0.0818, 0.667, 0.667, 49.8, 56611, 0.2087),
    ('FEBRUARY', 12, 0.6764, 0.3701, -0.1507, 0.750, 0.667, 52.0, 48603, 0.2041),
    ('MARCH', 12, 0.4492, 0.2913, -0.0944, 0.833, 0.833, 52.5, 46395, 0.1793),
    ('APRIL', 12, 0.4059, 0.2654, -0.0351, 0.583, 0.667, 50.6, 41807, 0.1739),
    ('MAY', 12, 0.3784, 0.2533, 0.0443, 0.500, 0.417, 40.3, 50635, 0.1639),
    ('JUNE', 12, 0.3349, 0.2428, 0.0020, 0.500, 0.583, 34.3, 50909, 0.1618),
    ('JULY', 12, 0.3733, 0.2578, -0.0467, 0.667, 0.583, 41.1, 51515, 0.1561),
    ('AUGUST', 12, 0.3777, 0.2537, 0.0353, 0.500, 0.500, 57.1, 49824, 0.1576),
    ('SEPTEMBER', 12, 0.3222, 0.2347, 0.0318, 0.500, 0.583, 44.8, 57398, 0.1483),
    ('OCTOBER', 12, 0.3671, 0.2504, -0.0128, 0.583, 0.500, 37.4, 59373, 0.1401),
    ('NOVEMBER', 11, 0.4154, 0.2853, -0.0073, 0.636, 0.636, 38.6, 52574, 0.1559),
    ('DECEMBER', 11, 0.5476, 0.3467, -0.1169, 0.727, 0.727, 46.2, 54204, 0.1771)
]

for row_idx, data in enumerate(seas_data, start=14):
    for col_idx, val in enumerate(data, start=1):
        cell = ws.cell(row_idx, col_idx, val)
        cell.font = regular_font
        cell.border = thin_border
        if col_idx == 1:
            cell.font = bold_font
            cell.alignment = Alignment(horizontal='left', vertical='center')
        elif col_idx in [3, 4, 5, 6, 7, 10]:
            cell.number_format = '0.0%'
            cell.alignment = Alignment(horizontal='right', vertical='center')
            if col_idx == 5:
                if val < 0:
                    cell.fill = light_red_fill
                    cell.font = Font(name=font_family, size=10, bold=True, color='900C3F')
                else:
                    cell.fill = light_green_fill
                    cell.font = Font(name=font_family, size=10, bold=True, color='1E8449')
            if col_idx == 7 and val >= 0.70:
                cell.fill = light_red_fill
                cell.font = Font(name=font_family, size=10, bold=True, color='900C3F')
        elif col_idx == 9:
            cell.number_format = '#,##0'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        else:
            cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[row_idx].height = 20

# SECTION 3: THE ROAD TO ₹100 CRORES (2020-2026 HISTORICAL SIMULATION)
ws.merge_cells('A28:J28')
ws['A28'] = "3. THE ROAD TO ₹100 CRORES: HISTORICAL 2-SWING ANNUAL SIMULATION (2020-2026)"
ws['A28'].font = section_font
ws['A28'].fill = blue_fill
ws['A28'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
ws.row_dimensions[28].height = 26

sim_headers = ['Year', 'Opening Capital (₹ Cr)', 'Avg Margin %', 'Effective Leverage', 'Captured Moves (Short / Long)', 'Gross Annual ROC %', 'Gross Trading Profit (₹ Cr)', 'Corporate Tax Paid (₹ Cr)', 'Effective Tax Rate %', 'Closing Capital (₹ Cr)']
for col_idx, h in enumerate(sim_headers, start=1):
    cell = ws.cell(29, col_idx, h)
    cell.font = header_font
    cell.fill = slate_fill
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cell.border = thin_border
ws.row_dimensions[29].height = 28

sim_rows = [
    (2020, 0.6000, 0.1911, 3.93, "Short: +16.8% (Winter drop) | Long: +13.5% (Summer spike)", 1.0916, 0.6549, 0.0686, 0.1047, 1.1864),
    (2021, 1.1864, 0.2002, 3.75, "Short: +17.2% (Feb Uri melt) | Long: +15.1% (Oct pre-winter)", 1.0443, 1.2389, 0.2155, 0.1740, 2.2098),
    (2022, 2.2098, 0.2947, 2.54, "Short: +24.5% (Ukraine top) | Long: +18.2% (Aug squeeze)", 0.9871, 2.1813, 0.4527, 0.2075, 3.9383),
    (2023, 3.9383, 0.2192, 3.42, "Short: +18.1% (Jan/Feb drop) | Long: +14.8% (Oct storage rally)", 0.9880, 3.8911, 0.8830, 0.2269, 6.9464),
    (2024, 6.9464, 0.2052, 3.66, "Short: +17.5% (Post-winter) | Long: +15.3% (May injection base)", 1.0134, 7.0395, 1.6754, 0.2380, 12.3105),
    (2025, 12.3105, 0.2311, 3.25, "Short: +19.4% (Dec/Jan melt) | Long: +16.0% (Aug heat wave)", 1.0879, 13.3922, 3.2743, 0.2445, 22.4284),
    (2026, 22.4284, 0.3064, 2.45, "Short: +21.2% (Current fwd drop) | Long: +15.5% (Summer spike)", 1.0307, 23.1172, 5.7219, 0.2475, 39.8237)
]

for row_idx, data in enumerate(sim_rows, start=30):
    for col_idx, val in enumerate(data, start=1):
        cell = ws.cell(row_idx, col_idx, val)
        cell.font = regular_font
        cell.border = thin_border
        if col_idx == 1:
            cell.font = bold_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        elif col_idx in [2, 7, 8, 10]:
            cell.number_format = '₹#,##0.00'
            cell.alignment = Alignment(horizontal='right', vertical='center')
            if col_idx == 10:
                cell.font = bold_font
                cell.fill = light_blue_fill
        elif col_idx in [3, 6, 9]:
            cell.number_format = '0.0%'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx == 4:
            cell.number_format = '0.00"x"'
            cell.alignment = Alignment(horizontal='center', vertical='center')
        else:
            cell.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[row_idx].height = 22

# Auto-adjust column widths
col_widths = {
    'A': 18, 'B': 24, 'C': 16, 'D': 18, 'E': 48,
    'F': 18, 'G': 22, 'H': 22, 'I': 18, 'J': 22
}
for col_letter, w in col_widths.items():
    ws.column_dimensions[col_letter].width = w

wb.save(wb_path)
print(f"Successfully added '{sheet_name}' tab to {wb_path}!")
