import os
import re

css_path = "src/index.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

# Add :root variables
if "--color-accent: #059669;" not in css:
    css = css.replace(":root {", ":root {\n        --color-accent: #059669;")

# Add .dark variables
if "--color-accent: #00ff88;" not in css:
    css = css.replace(".dark {", ".dark {\n        --color-accent: #00ff88;")

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css)

def replace_in_file(filepath, replacements):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist.")
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

# File replacements

replace_in_file("src/pages/Dashboard.js", [
    ("text-[#00FF41]", "text-[var(--color-accent)]"),
    ("border-[#00FF41]", "border-[var(--color-accent)]"),
    ("bg-[#00FF41]", "bg-[var(--color-accent)]"),
    ("#00FF41 transparent", "var(--color-accent) transparent")
])

replace_in_file("src/components/AIChatbot.js", [
    ("border: 1px solid rgba(0, 255, 136, 0.15)", "border: 1px solid rgba(var(--color-accent), 0.15)"),
    ("box-shadow: 0 0 40px rgba(0, 255, 136, 0.05)", "box-shadow: 0 0 40px rgba(var(--color-accent), 0.05)"),
    ("box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4)", "box-shadow: 0 0 0 0 rgba(var(--color-accent), 0.4)"),
    ("box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.8)", "box-shadow: 0 0 0 0 rgba(var(--color-accent), 0.8)"),
    ("box-shadow: 0 0 0 6px rgba(0, 255, 136, 0)", "box-shadow: 0 0 0 6px rgba(var(--color-accent), 0)"),
    ("rgba(0, 255, 136, 0)", "rgba(var(--color-accent), 0)"),
    ("border-left: 3px solid #00ff88", "border-left: 3px solid var(--color-accent)"),
    ("color: #00ff88", "color: var(--color-accent)"),
    ("color: #009955", "color: var(--color-accent)"),
    ("background: rgba(0, 255, 136, 0.15)", "background: rgba(var(--color-accent), 0.15)"),
    ("background: #00ff88", "background: var(--color-accent)"),
    ("shadow-[0_0_40px_rgba(0,255,136,0.05)]", "shadow-[0_0_40px_var(--color-accent)]"),
    ("text-[#00d035]", "text-[var(--color-accent)]"),
    ("bg-[#00d035]", "bg-[var(--color-accent)]"),
    ("text-[#00ff88]", "text-[var(--color-accent)]"),
    ("bg-primary", "bg-[var(--color-accent)] text-white"), # This is tricky, primary is green but wait, primary in light mode is emerald
])

# For Navbar etc., wait. I will just do a standard regex search and replace for #00ff88, #00FF41, #00FF00 if possible, but manual is safer.

print("Applied light mode CSS overrides.")
