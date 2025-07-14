#!/usr/bin/env python3
"""
Script to automatically update DOCUMENTATION_STRUCTURE.md when files are added/removed.
Run this after any documentation changes to keep the structure map current.
"""

import os
import glob
import re
from pathlib import Path
from datetime import datetime

# Paths
DOCS_DIR = "/Users/amit/Documents/GitHub/documentation/src/content/docs"
STRUCTURE_FILE = "/Users/amit/Documents/GitHub/documentation/DOCUMENTATION_STRUCTURE.md"
CLAUDE_FILE = "/Users/amit/Documents/GitHub/documentation/CLAUDE.md"

def count_files_by_directory():
    """Count .mdx files in each directory."""
    all_files = glob.glob(os.path.join(DOCS_DIR, "**/*.mdx"), recursive=True)
    
    # Count by top-level directories
    counts = {}
    for file_path in all_files:
        rel_path = os.path.relpath(file_path, DOCS_DIR)
        top_dir = rel_path.split('/')[0]
        counts[top_dir] = counts.get(top_dir, 0) + 1
    
    total_files = len(all_files)
    return total_files, counts

def update_structure_file(total_files, dir_counts):
    """Update DOCUMENTATION_STRUCTURE.md with current file counts."""
    if not os.path.exists(STRUCTURE_FILE):
        print(f"Structure file not found: {STRUCTURE_FILE}")
        return False
    
    with open(STRUCTURE_FILE, 'r') as f:
        content = f.read()
    
    # Update total count
    content = re.sub(
        r'\*\*Total\*\*: \d+ \.mdx files',
        f'**Total**: {total_files} .mdx files',
        content
    )
    
    # Update individual directory counts
    for dir_name, count in dir_counts.items():
        # Update patterns like "├── answers/         (16 files)"
        pattern = rf'(├── {re.escape(dir_name)}/\s+)\(\d+ files\)'
        replacement = rf'\g<1>({count} files)'
        content = re.sub(pattern, replacement, content)
        
        # Update patterns like "- **Tallyfy Pro** ... (512 files)"
        if dir_name == 'pro':
            pattern = r'(\- \*\*Tallyfy Pro\*\*.*?)\(\d+ files'
            replacement = rf'\g<1>({count} files'
            content = re.sub(pattern, replacement, content)
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "Last updated:" not in content:
        content = f"<!-- Last updated: {timestamp} -->\n" + content
    else:
        content = re.sub(
            r'<!-- Last updated: .+ -->',
            f'<!-- Last updated: {timestamp} -->',
            content
        )
    
    with open(STRUCTURE_FILE, 'w') as f:
        f.write(content)
    
    return True

def update_claude_file(total_files, dir_counts):
    """Update CLAUDE.md with current file counts."""
    if not os.path.exists(CLAUDE_FILE):
        print(f"CLAUDE.md not found: {CLAUDE_FILE}")
        return False
    
    with open(CLAUDE_FILE, 'r') as f:
        content = f.read()
    
    # Update main reference
    content = re.sub(
        r'(\*\*📁 COMPLETE DOCUMENTATION STRUCTURE\*\*.*?)\d+ \.mdx files',
        rf'\g<1>{total_files} .mdx files',
        content
    )
    
    # Update critical context sections
    content = re.sub(
        r'(- Tallyfy documentation:) \d+ \.mdx files',
        rf'\g<1> {total_files} .mdx files',
        content
    )
    
    # Update pro count specifically
    if 'pro' in dir_counts:
        content = re.sub(
            r'(pro/ \()\d+ files(\))',
            rf'\g<1>{dir_counts["pro"]} files\g<2>',
            content
        )
    
    with open(CLAUDE_FILE, 'w') as f:
        f.write(content)
    
    return True

def main():
    """Main function to update documentation structure."""
    print("🔄 Updating documentation structure map...")
    
    # Count current files
    total_files, dir_counts = count_files_by_directory()
    
    print(f"📊 Found {total_files} total .mdx files:")
    for dir_name, count in sorted(dir_counts.items()):
        print(f"   {dir_name}/: {count} files")
    
    # Update structure file
    if update_structure_file(total_files, dir_counts):
        print(f"✅ Updated {STRUCTURE_FILE}")
    else:
        print(f"❌ Failed to update {STRUCTURE_FILE}")
    
    # Update CLAUDE.md
    if update_claude_file(total_files, dir_counts):
        print(f"✅ Updated {CLAUDE_FILE}")
    else:
        print(f"❌ Failed to update {CLAUDE_FILE}")
    
    print("🎯 Documentation structure map updated successfully!")
    
    # Show summary
    print(f"\n📋 Summary:")
    print(f"   Total documentation files: {total_files}")
    print(f"   Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()