#!/usr/bin/env python3
"""
Update all Mermaid diagrams in documentation to use improved text wrapping syntax.
This script converts regular text in Mermaid nodes to use markdown strings for better rendering.
"""

import os
import re
from pathlib import Path

def update_mermaid_diagram(content):
    """Update Mermaid diagram syntax for better text wrapping."""
    
    # Pattern to find Mermaid code blocks
    mermaid_pattern = r'```mermaid\n(.*?)\n```'
    
    def process_diagram(match):
        diagram = match.group(1)
        lines = diagram.split('\n')
        updated_lines = []
        
        for line in lines:
            # Skip empty lines and certain diagram types
            if not line.strip() or line.strip().startswith('%%') or line.strip().startswith('Note'):
                updated_lines.append(line)
                continue
            
            # Pattern to match node definitions with text
            # Matches patterns like: NodeID[Text with spaces]
            node_pattern = r'(\w+)\[(.*?)\]'
            
            def update_node(match):
                node_id = match.group(1)
                node_text = match.group(2)
                
                # Skip if already using markdown strings
                if node_text.startswith('"`') and node_text.endswith('`"'):
                    return match.group(0)
                
                # Skip if it's a link or special syntax
                if node_text.startswith('(') or node_text.startswith('{'):
                    return match.group(0)
                
                # Convert <br/> to newlines in markdown strings
                if '<br/>' in node_text:
                    parts = node_text.split('<br/>')
                    # Make the first part bold if it looks like a title
                    if len(parts) > 1:
                        formatted_text = f'**{parts[0]}**'
                        if len(parts) > 1:
                            formatted_text += '\n' + '\n'.join(parts[1:])
                    else:
                        formatted_text = node_text.replace('<br/>', '\n')
                    return f'{node_id}["`{formatted_text}`"]'
                
                # If text has multiple words, wrap it for better rendering
                if ' ' in node_text and len(node_text) > 15:
                    # Make it bold for better visibility
                    return f'{node_id}["`**{node_text}**`"]'
                
                return match.group(0)
            
            # Update nodes in the line
            updated_line = re.sub(node_pattern, update_node, line)
            
            # Update edge labels
            edge_label_pattern = r'-->\|(.*?)\|'
            def update_edge_label(match):
                label = match.group(1)
                # Skip if already using markdown strings
                if not (label.startswith('"`') and label.endswith('`"')):
                    return f'-->|"`{label}`"|'
                return match.group(0)
            
            updated_line = re.sub(edge_label_pattern, update_edge_label, updated_line)
            
            updated_lines.append(updated_line)
        
        return f'```mermaid\n{chr(10).join(updated_lines)}\n```'
    
    # Update all Mermaid blocks in the content
    updated_content = re.sub(mermaid_pattern, process_diagram, content, flags=re.DOTALL)
    
    return updated_content

def process_file(file_path):
    """Process a single MDX file to update Mermaid diagrams."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file contains Mermaid diagrams
        if '```mermaid' not in content:
            return False
        
        # Update the content
        updated_content = update_mermaid_diagram(content)
        
        # Only write if content changed
        if updated_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"✅ Updated: {file_path}")
            return True
        else:
            print(f"⏭️  No changes needed: {file_path}")
            return False
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all MDX files."""
    docs_dir = Path('/Users/amit/Documents/GitHub/documentation/src/content/docs')
    
    if not docs_dir.exists():
        print(f"Error: Documentation directory not found at {docs_dir}")
        return
    
    # Find all MDX files
    mdx_files = list(docs_dir.glob('**/*.mdx'))
    print(f"Found {len(mdx_files)} MDX files")
    
    # Filter to only files with Mermaid diagrams
    mermaid_files = []
    for file_path in mdx_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            if '```mermaid' in f.read():
                mermaid_files.append(file_path)
    
    print(f"Found {len(mermaid_files)} files with Mermaid diagrams")
    
    # Process each file
    updated_count = 0
    for file_path in mermaid_files:
        if process_file(file_path):
            updated_count += 1
    
    print(f"\n📊 Summary: Updated {updated_count} out of {len(mermaid_files)} files with Mermaid diagrams")

if __name__ == '__main__':
    main()