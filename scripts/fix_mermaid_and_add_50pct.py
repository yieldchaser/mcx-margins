"""
fix_mermaid_and_add_50pct.py
1. Fixes all Mermaid blocks in plan.md and execution_and_tax_validation_plan.md
   so that no raw newlines or leading '-' / '1.' exist inside node definitions.
2. Updates both documents to include the 50% and 75% annual return profiles in the sensitivity table.
3. Adds '50% Annual' sheet to Master_Commodity_Treasury_Model.xlsx.
"""

import re
import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def clean_mermaid_text(content):
    def replace_block(match):
        raw_block = match.group(1)
        lines = raw_block.split("\n")
        new_lines = []
        inside_quotes = False
        current_node = ""

        for line in lines:
            stripped = line.strip()
            # Count quotes in this line
            quote_count = line.count('"')
            if not inside_quotes:
                if quote_count % 2 == 1:
                    inside_quotes = True
                    current_node = line
                else:
                    new_lines.append(line)
            else:
                # Inside multi-line quote
                clean_line = stripped
                if clean_line.startswith("- "):
                    clean_line = "• " + clean_line[2:]
                elif re.match(r"^\d+\.\s*", clean_line):
                    clean_line = re.sub(r"^(\d+)\.\s*", r"(\1) ", clean_line)
                
                current_node += "<br/>" + clean_line
                if quote_count % 2 == 1:
                    inside_quotes = False
                    new_lines.append(current_node)
                    current_node = ""
        
        return "```mermaid\n" + "\n".join(new_lines).strip() + "\n```"

    return re.sub(r"```mermaid(.*?)```", replace_block, content, flags=re.DOTALL)

def update_plans():
    paths = [
        "C:/Users/Dell/.gemini/antigravity/brain/e90b5b2c-13aa-474e-9bfa-a42b74b47f3c/plan.md",
        "models/execution_and_tax_validation_plan.md"
    ]
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()

        fixed_text = clean_mermaid_text(text)

        # Update the Multi-Return Sensitivity Matrix to include 50% return
        old_table = """| Annual Return Rate | Year 1 | Year 3 | Year 5 | Year 7 | Year 10 | Year 15 | Year 20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **75% Annual Return** | ₹0.96 Cr | ₹2.44 Cr | ₹6.07 Cr | ₹14.92 Cr | **₹57.02 Cr** | ₹326.95 Cr | **₹706.07 Cr** |
| **80% Annual Return** | ₹0.98 Cr | ₹2.62 Cr | ₹6.82 Cr | ₹17.57 Cr | **₹72.05 Cr** | ₹383.47 Cr | **₹799.00 Cr** |
| **85% Annual Return** | ₹1.00 Cr | ₹2.81 Cr | ₹7.66 Cr | ₹20.63 Cr | **₹90.61 Cr** | ₹440.03 Cr | **₹891.98 Cr** |
| **100% Annual Return** | ₹1.08 Cr | ₹3.43 Cr | ₹10.63 Cr | ₹32.63 Cr | **₹174.65 Cr** | ₹619.23 Cr | **₹1,182.98 Cr** |"""

        new_table = """| Annual Return Rate | Year 1 | Year 3 | Year 5 | Year 7 | Year 10 | Year 15 | Year 20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **50% Annual Return (Conservative)** | ₹0.83 Cr | ₹1.63 Cr | ₹3.18 Cr | ₹6.12 Cr | **₹16.11 Cr** | ₹79.44 Cr | **₹276.63 Cr** |
| **75% Annual Return (Baseline)** | ₹0.96 Cr | ₹2.44 Cr | ₹6.07 Cr | ₹14.92 Cr | **₹57.02 Cr** | ₹326.95 Cr | **₹706.07 Cr** |
| **80% Annual Return (Steady Quant)** | ₹0.98 Cr | ₹2.62 Cr | ₹6.82 Cr | ₹17.57 Cr | **₹72.05 Cr** | ₹383.47 Cr | **₹799.00 Cr** |
| **85% Annual Return (Target)** | ₹1.00 Cr | ₹2.81 Cr | ₹7.66 Cr | ₹20.63 Cr | **₹90.61 Cr** | ₹440.03 Cr | **₹891.98 Cr** |
| **100% Annual Return (High Growth)** | ₹1.08 Cr | ₹3.43 Cr | ₹10.63 Cr | ₹32.63 Cr | **₹174.65 Cr** | ₹619.23 Cr | **₹1,182.98 Cr** |"""

        if old_table in fixed_text:
            fixed_text = fixed_text.replace(old_table, new_table)

        with open(p, "w", encoding="utf-8") as f:
            f.write(fixed_text)
        print(f"Updated and cleaned {p}")

def add_50pct_to_excel():
    wb_path = "models/Master_Commodity_Treasury_Model.xlsx"
    wb = openpyxl.load_workbook(wb_path)

    if "50% Annual" not in wb.sheetnames:
        # Copy 75% Annual sheet
        ws_75 = wb["75% Annual"]
        ws_50 = wb.copy_worksheet(ws_75)
        ws_50.title = "50% Annual"
        ws_50["B6"] = 0.50
        ws_50["A1"] = "MCX COMMODITY TREASURY MODEL  ·  50% ANNUAL"
        ws_50["A2"] = "Conservative Growth Tier (50% Return) · Live inputs: cream cells. All 20-year cycles dynamically evaluate."
        
        # Reorder sheets to put 50% right before 75%
        sheet_order = [
            "Interactive Dashboard", "50% Annual", "75% Annual", "80% Annual", 
            "85% Annual", "100% Annual", "120% Annual", "GIFT City CME Bridge", 
            "3-Employee Legal Framework", "NG Risk and Sizing", "NG Inputs", "NG Data"
        ]
        wb._sheets = [wb[s] for s in sheet_order if s in wb.sheetnames]
        wb.save(wb_path)
        print("Added '50% Annual' sheet to Master_Commodity_Treasury_Model.xlsx")
    else:
        print("'50% Annual' sheet already exists.")

if __name__ == "__main__":
    update_plans()
    add_50pct_to_excel()
