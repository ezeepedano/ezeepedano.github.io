import os

def replace_in_file(filepath, target, replacement):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if target in content or target.lower() in content.lower(): # Case insensitive check for efficiency
             # We want to preserve case if possible, but the requirement is "replace ... with Propel"
             # Let's do a case insensitive replacement logic carefully, or just standard replace if we know the exact casing.
             # grep found "Propel" mostly. User said "todo rastro".
             
             new_content = content.replace('Propel', replacement)
             new_content = new_content.replace('Propel', replacement)
             new_content = new_content.replace('Propel', replacement) 
             
             if new_content != content:
                 with open(filepath, 'w', encoding='utf-8') as f:
                     f.write(new_content)
                 print(f"Updated: {filepath}")
                 
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

def main():
    target_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Scanning directory: {target_dir}")
    
    extensions = ['.html', '.py', '.txt', '.md', '.bat', '.js']
    skip_dirs = ['venv', '.git', '.github', '.vscode', '__pycache__', 'venv_broken', '.cursor']
    
    count = 0
    for root, dirs, files in os.walk(target_dir):
        # Skip hidden/virtual dirs
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                replace_in_file(filepath, 'Propel', 'Propel') # Dummy call? No.
                # Actually perform the replacement
                replace_in_file(filepath, 'Propel', 'Propel')
                count += 1
                
    print(f"Scanned {count} files.")

if __name__ == "__main__":
    main()
