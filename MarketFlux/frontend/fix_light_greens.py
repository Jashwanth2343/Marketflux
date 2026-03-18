import os
import re

def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.js') or file.endswith('.jsx'):
                filepath = os.path.join(root, file)
                fix_file(filepath)

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Standard tailwind classes replacements
    replacements = [
        (r'text-\[#00FF41\]', r'dark:text-[#00FF41] text-[#059669]'),
        (r'text-\[#00ff88\]', r'dark:text-[#00ff88] text-[#059669]'),
        (r'bg-\[#00FF41\]', r'dark:bg-[#00FF41] bg-[#059669]'),
        (r'bg-\[#00ff88\]', r'dark:bg-[#00ff88] bg-[#059669]'),
        (r'border-\[#00FF41\]', r'dark:border-[#00FF41] border-[#059669]'),
        (r'border-\[#00ff88\]', r'dark:border-[#00ff88] border-[#059669]'),
    ]

    for old, new in replacements:
        content = re.sub(old, new, content)
        
    # We must also handle opacity modifiers, e.g. text-[#00FF41]/20 -> dark:text-[#00FF41]/20 text-[#059669]/20
    modifiers_replacements = [
        (r'text-\[#00FF41\]/(\d+)', r'dark:text-[#00FF41]/\1 text-[#059669]/\1'),
        (r'text-\[#00ff88\]/(\d+)', r'dark:text-[#00ff88]/\1 text-[#059669]/\1'),
        (r'bg-\[#00FF41\]/(\d+)', r'dark:bg-[#00FF41]/\1 bg-[#059669]/\1'),
        (r'bg-\[#00ff88\]/(\d+)', r'dark:bg-[#00ff88]/\1 bg-[#059669]/\1'),
        (r'border-\[#00FF41\]/(\d+)', r'dark:border-[#00FF41]/\1 border-[#059669]/\1'),
        (r'border-\[#00ff88\]/(\d+)', r'dark:border-[#00ff88]/\1 border-[#059669]/\1'),
    ]

    for old, new in modifiers_replacements:
        content = re.sub(old, new, content)
        
    # Fix Dashboard specific active tab highlight
    # Previous Dashboard.js tab logic: 
    # ${activeTab === 'gainers' ? 'border-b-2 dark:border-[#00FF41] border-[#059669] dark:text-[#00FF41] text-[#059669]'
    # Since we replaced text-[#00FF41] blindly, let's fix if we introduced duplicates like dark:dark:
    content = content.replace("dark:dark:", "dark:")
    
    # CSS generic fixes
    # "color: #00ff88" inside style tags or string templates (AIChatbot)
    content = content.replace("color: #00ff88", "color: var(--color-accent)")
    content = content.replace("color: #009955", "color: var(--color-accent)")
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

if __name__ == '__main__':
    process_directory('src')

    # Add the CSS variable to index.css
    with open('src/index.css', 'r', encoding='utf-8') as f:
        css = f.read()
    
    # Add :root variables
    if "--color-accent: #059669;" not in css:
        css = css.replace(":root {", ":root {\\n        --color-accent: #059669;")
    # Add .dark variables
    if "--color-accent: #00ff88;" not in css:
        css = css.replace(".dark {", ".dark {\\n        --color-accent: #00ff88;")
        
    with open('src/index.css', 'w', encoding='utf-8') as f:
        f.write(css)
    print("Updated src/index.css")
