#!/usr/bin/env python3
"""
Fix broken hyperlinks in Mermaid diagrams by checking if target URLs exist.
"""

import os
import re
from pathlib import Path

def get_valid_urls():
    """Build a set of valid documentation URLs based on existing files."""
    docs_dir = Path('/Users/amit/Documents/GitHub/documentation/src/content/docs')
    valid_urls = set()
    
    for mdx_file in docs_dir.glob('**/*.mdx'):
        # Convert file path to URL
        relative_path = mdx_file.relative_to(docs_dir)
        url_path = str(relative_path).replace('.mdx', '/')
        valid_urls.add(f"/products/{url_path}")
        
        # Also add without trailing slash for flexibility
        valid_urls.add(f"/products/{url_path.rstrip('/')}")
    
    return valid_urls

def check_and_fix_mermaid_links(content, valid_urls):
    """Check and fix broken links in Mermaid diagrams."""
    
    # Pattern to find Mermaid blocks
    mermaid_pattern = r'```mermaid\n(.*?)\n```'
    
    def process_diagram(match):
        diagram = match.group(1)
        lines = diagram.split('\n')
        updated_lines = []
        
        for line in lines:
            # Pattern to match click directives
            click_pattern = r'click\s+(\w+)\s+"([^"]+)"\s+"([^"]+)"'
            
            def check_url(match):
                node_id = match.group(1)
                url = match.group(2)
                description = match.group(3)
                
                # Skip external URLs and anchors
                if url.startswith('http') or url.startswith('#'):
                    return match.group(0)
                
                # Check if URL exists
                if url not in valid_urls and url.rstrip('/') not in valid_urls:
                    # Try to find a similar URL
                    url_parts = url.split('/')
                    possible_fixes = []
                    
                    # Common patterns to try
                    if 'launch-triggers' in url:
                        # Fix old pattern to new pattern
                        fixed_url = url.replace('launch-triggers', 'triggers')
                        if fixed_url in valid_urls or fixed_url.rstrip('/') in valid_urls:
                            return f'click {node_id} "{fixed_url}" "{description}"'
                    
                    if 'form-submission' in url:
                        # Common broken link
                        fixed_url = '/products/pro/launching/how-to-launch-a-tallyfy-process-from-a-webform/'
                        if fixed_url in valid_urls:
                            return f'click {node_id} "{fixed_url}" "{description}"'
                    
                    if 'email-triggers' in url:
                        fixed_url = '/products/pro/launching/triggers/via-email/'
                        if fixed_url in valid_urls:
                            return f'click {node_id} "{fixed_url}" "{description}"'
                    
                    # Log broken link for manual review
                    print(f"  ⚠️  Broken link found: {url}")
                    # Comment out broken links rather than removing
                    return f'%% BROKEN: {match.group(0)}'
                
                return match.group(0)
            
            updated_line = re.sub(click_pattern, check_url, line)
            updated_lines.append(updated_line)
        
        return f'```mermaid\n{chr(10).join(updated_lines)}\n```'
    
    updated_content = re.sub(mermaid_pattern, process_diagram, content, flags=re.DOTALL)
    return updated_content

def process_file(file_path, valid_urls):
    """Process a single MDX file to fix broken Mermaid links."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file contains Mermaid diagrams with click directives
        if '```mermaid' not in content or 'click' not in content:
            return False
        
        print(f"\nChecking: {file_path}")
        
        # Fix the content
        updated_content = check_and_fix_mermaid_links(content, valid_urls)
        
        # Only write if content changed
        if updated_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"  ✅ Fixed broken links")
            return True
        else:
            print(f"  ✓ All links valid")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Main function to process all MDX files."""
    docs_dir = Path('/Users/amit/Documents/GitHub/documentation/src/content/docs')
    
    print("Building valid URL list...")
    valid_urls = get_valid_urls()
    print(f"Found {len(valid_urls)} valid documentation URLs")
    
    # Find all MDX files with Mermaid diagrams
    mdx_files = []
    for file_path in docs_dir.glob('**/*.mdx'):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if '```mermaid' in content and 'click' in content:
                mdx_files.append(file_path)
    
    print(f"\nFound {len(mdx_files)} files with Mermaid diagrams containing links")
    
    # Process each file
    fixed_count = 0
    for file_path in mdx_files:
        if process_file(file_path, valid_urls):
            fixed_count += 1
    
    print(f"\n📊 Summary: Fixed {fixed_count} files with broken Mermaid links")

if __name__ == '__main__':
    main()