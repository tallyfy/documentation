#!/usr/bin/env python3
"""
Fix all Mermaid diagrams for true mobile-first vertical layouts.
This script identifies hub-and-spoke patterns and converts them to sequential vertical flows.
"""

import os
import re
from pathlib import Path

def analyze_diagram_pattern(diagram_content):
    """Analyze if a diagram has hub-and-spoke or problematic horizontal pattern."""
    lines = diagram_content.split('\n')
    
    # Count connections per node
    node_connections = {}
    for line in lines:
        # Look for connection patterns
        if '-->' in line or '-.->|' in line or '-->|' in line:
            parts = re.split(r'-->|-.->|-->\|', line)
            if len(parts) >= 2:
                source = parts[0].strip().split('[')[0].strip()
                if source:
                    node_connections[source] = node_connections.get(source, 0) + 1
    
    # Check if any node has more than 3 outgoing connections (hub pattern)
    for node, count in node_connections.items():
        if count > 3:
            return True, node  # Hub-and-spoke detected
    
    # Check if all nodes connect to single target (reverse hub)
    target_connections = {}
    for line in lines:
        if '-->' in line:
            parts = line.split('-->')
            if len(parts) >= 2:
                target = parts[-1].strip().split('[')[0].strip()
                if target:
                    target_connections[target] = target_connections.get(target, 0) + 1
    
    for node, count in target_connections.items():
        if count > 3:
            return True, node  # Reverse hub detected
    
    return False, None

def needs_mobile_fix(content):
    """Check if the Mermaid diagram needs mobile-first fixes."""
    # Extract Mermaid blocks
    mermaid_pattern = r'```mermaid\n(.*?)\n```'
    matches = re.findall(mermaid_pattern, content, re.DOTALL)
    
    for diagram in matches:
        # Skip sequence diagrams (they're already vertical)
        if 'sequenceDiagram' in diagram:
            continue
        
        # Check for problematic patterns
        has_hub, hub_node = analyze_diagram_pattern(diagram)
        if has_hub:
            return True, hub_node
            
        # Check for LR (left-right) orientation
        if 'flowchart LR' in diagram or 'graph LR' in diagram:
            return True, 'LR orientation'
    
    return False, None

def get_files_needing_fixes():
    """Find all MDX files with Mermaid diagrams that need mobile fixes."""
    docs_dir = Path('/Users/amit/Documents/GitHub/documentation/src/content/docs')
    files_to_fix = []
    
    for mdx_file in docs_dir.glob('**/*.mdx'):
        try:
            with open(mdx_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if '```mermaid' in content:
                needs_fix, reason = needs_mobile_fix(content)
                if needs_fix:
                    files_to_fix.append((mdx_file, reason))
        except Exception as e:
            print(f"Error checking {mdx_file}: {e}")
    
    return files_to_fix

def main():
    """Main function to identify files needing mobile-first fixes."""
    print("🔍 Analyzing Mermaid diagrams for mobile-first issues...")
    
    files_to_fix = get_files_needing_fixes()
    
    if not files_to_fix:
        print("✅ No diagrams need mobile-first fixes!")
        return
    
    print(f"\n📊 Found {len(files_to_fix)} files with diagrams needing mobile-first restructuring:\n")
    
    for file_path, reason in files_to_fix:
        relative_path = file_path.relative_to(Path('/Users/amit/Documents/GitHub/documentation'))
        print(f"  • {relative_path}")
        print(f"    Issue: {reason}")
    
    print(f"\n💡 These files have hub-and-spoke or horizontal patterns that need conversion to vertical sequential flows.")
    print("   Each should be manually reviewed and restructured for mobile readability.")
    
    # Group by directory for easier batch fixing
    by_dir = {}
    for file_path, reason in files_to_fix:
        dir_path = file_path.parent
        if dir_path not in by_dir:
            by_dir[dir_path] = []
        by_dir[dir_path].append((file_path, reason))
    
    print(f"\n📁 Files grouped by directory ({len(by_dir)} directories):")
    for dir_path, files in by_dir.items():
        relative_dir = dir_path.relative_to(Path('/Users/amit/Documents/GitHub/documentation'))
        print(f"\n  {relative_dir}/ ({len(files)} files)")

if __name__ == '__main__':
    main()