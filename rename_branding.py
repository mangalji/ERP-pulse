import os
import re

# Define replacement mapping (case-insensitive)
replacements = [
    ("AGSuite ERP", "AGSuite ERP"),
    ("AGSuite-ERP", "AGSuite-ERP"),
    ("AGSuite_ERP", "AGSuite_ERP"),
    ("agsuite-erp", "agsuite-erp"),
    ("agsuite_erp", "agsuite_erp"),
    ("AGSuiteERP", "AGSuiteERP"),
    ("agsuiterp", "agsuiterp"),
    ("agsuite erp", "agsuite erp"),
]

# Files to skip (binary/generated)
skip_extensions = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".zip", ".tar", ".gz", ".jpg", ".png", ".ico", ".svg"}
skip_dirs = {".venv", "node_modules", ".git", "__pycache__", "dist", "build"}

# Count replacements
stats = {}

for root, dirs, files in os.walk("C:\\Users\\Raj Mangal\\OneDrive\\Desktop\\agsuite-erp\\ERP-pulse"):
    # Skip binary/generated directories
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in skip_extensions:
            continue
        
        # Only process text files
        if ext not in {".jsx", ".js", ".ts", ".tsx", ".html", ".css", ".scss", ".md", ".txt", ".yaml", ".yml", ".json", ".env", ".example", ".render", ".py", ".rb", ".java", ".c", ".cpp", ".h"}:
            continue
            
        filepath = os.path.join(root, file)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError):
            continue
        
        original = content
        modified = False
        
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                modified = True
                stats[old] = stats.get(old, 0) + content.count(old) + content.count(new)
        
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated: {filepath}")

print("\nReplacement stats:", stats)
