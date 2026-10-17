import re
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def update_docs():
    with open('scratch/section7_content.md', 'r', encoding='utf-8') as f:
        section7_text = f.read()
        
    paths = [
        "C:/Users/Dell/.gemini/antigravity/brain/e90b5b2c-13aa-474e-9bfa-a42b74b47f3c/plan.md",
        "models/execution_and_tax_validation_plan.md"
    ]
    
    pattern = re.compile(r'## 7\..*?## 8\. GIFT City IFSC Setup Reality, Approvals & Expenses', re.DOTALL)
    
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        
        replacement = section7_text.strip() + "\n\n---\n\n## 8. GIFT City IFSC Setup Reality, Approvals & Expenses"
        new_content = pattern.sub(lambda m: replacement, content)
        
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated Section 7 in {p}")

if __name__ == "__main__":
    update_docs()
