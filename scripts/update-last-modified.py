#!/usr/bin/env python3
"""
Update lastUpdated field in MDX frontmatter based on Git history.
This script reads the Git last modified date for each MDX file and updates
the frontmatter accordingly. Runs in the documentation repository where 
content is authored.
"""

import os
import argparse
import frontmatter
import subprocess
from pathlib import Path
from datetime import datetime

def get_git_last_modified(file_path):
    """Get the last modified date from Git history for a file."""
    try:
        # Get the last commit date for this file
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%aI', '--', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stdout.strip():
            # Parse the ISO format date from git
            git_date = result.stdout.strip()
            # Convert to datetime and back to ensure valid format
            dt = datetime.fromisoformat(git_date.replace('+00:00', '+00:00'))
            # Return as date only (YYYY-MM-DD) for cleaner display
            return dt.date().isoformat()
        else:
            return None
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        print(f"Error getting git date for {file_path}: {e}")
        return None

def update_file_last_modified(file_path):
    """Update the lastUpdated field in a file's frontmatter."""
    try:
        # Read the file with frontmatter
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        
        # Get Git last modified date
        git_date = get_git_last_modified(file_path)
        
        if git_date:
            # For Astro, we need to write the date as an unquoted YAML date
            # python-frontmatter will write date objects without quotes
            from datetime import datetime
            date_obj = datetime.strptime(git_date, '%Y-%m-%d').date()
            
            # Check if we need to update
            current_last_updated = post.get('lastUpdated')
            
            # Force update if current is a string (needs to be date object for Astro)
            # or if the date value has changed
            if isinstance(current_last_updated, str):
                # Always update strings to date objects for proper YAML formatting
                needs_update = True
            elif hasattr(current_last_updated, 'date'):
                needs_update = current_last_updated.date() != date_obj
            else:
                needs_update = current_last_updated != date_obj
            
            if needs_update:
                # Update the lastUpdated field with date object
                # This will be written as: lastUpdated: 2025-08-15 (without quotes)
                post['lastUpdated'] = date_obj
                
                # Write the file back - frontmatter.dumps will write dates without quotes
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(frontmatter.dumps(post))
                
                print(f"✅ Updated {file_path}: lastUpdated = {git_date}")
                return True
            else:
                print(f"⏭️  Skipped {file_path}: already up-to-date")
                return False
        else:
            print(f"⚠️  No git history for {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def process_directory(dir_path):
    """Process all MDX files in a directory recursively."""
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    # Files to skip
    skip_list = ["404.mdx"]
    
    # Walk through all MDX files
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.mdx') and file not in skip_list:
                file_path = os.path.join(root, file)
                result = update_file_last_modified(file_path)
                
                if result is True:
                    updated_count += 1
                elif result is False:
                    skipped_count += 1
                else:
                    error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Update lastUpdated dates in MDX frontmatter from Git history'
    )
    
    # Add arguments
    parser.add_argument(
        '--dir', 
        type=str, 
        default='src/content/docs',
        help='Directory path containing MDX files (default: src/content/docs)'
    )
    
    args = parser.parse_args()
    
    # Resolve the directory path
    dir_path = Path(args.dir).resolve()
    
    if not dir_path.exists():
        print(f"❌ Directory not found: {dir_path}")
        return 1
    
    print(f"📁 Processing MDX files in: {dir_path}")
    print("=" * 60)
    
    # Process all files
    updated, skipped, errors = process_directory(str(dir_path))
    
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Updated: {updated} files")
    print(f"   ⏭️  Skipped: {skipped} files")
    if errors > 0:
        print(f"   ❌ Errors: {errors} files")
    
    # Return non-zero exit code if there were errors
    return 1 if errors > 0 else 0

if __name__ == "__main__":
    exit(main())