#!/usr/bin/env python3
"""
Update lastUpdated field in MDX frontmatter based on Git history.
This script reads the Git last modified date for each MDX file and updates
the frontmatter accordingly. Runs in the documentation repository where 
content is authored.

    python scripts/update-last-modified.py --dir=src/content/docs
    python scripts/update-last-modified.py --self-test

--self-test proves the date parser reads every form git prints, on the Python
the pipeline pins (3.10), and refreshes a page in a scratch git repository.
Exit 0 passed, 1 a case failed.
"""

import os
import sys
import argparse
import tempfile
import frontmatter
import subprocess
from pathlib import Path
from datetime import datetime

def parse_git_date(git_date):
    """The YYYY-MM-DD date of a `git log --format=%aI` value.

    Git prints a UTC date with a trailing `Z` (2026-09-23T01:40:52Z) and any other
    offset in full (2026-09-22T20:37:48-05:00). The pipeline pins Python 3.10, whose
    datetime.fromisoformat rejects the `Z`; 3.11 and later accept it. So the `Z` is
    rewritten to +00:00 first. Before this, every page whose newest commit was dated in
    UTC was skipped with "Invalid isoformat string" and kept a stale lastUpdated: 587
    such lines in each of staging runs 35813737212 and 35813745697 on 2026-09-23
    (tallyfy/documentation#295). The date is the author's own calendar date, as before.
    Raises ValueError on anything that is not an ISO 8601 date.
    """
    text = git_date.strip()
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).date().isoformat()

def get_git_last_modified(file_path):
    """Get the last modified date from Git history for a file."""
    try:
        # Get the last commit date for this file. Run from the file's own folder, so
        # the answer comes from the repository the file is in, whatever the caller's
        # working directory is.
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%aI', '--', os.path.abspath(file_path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.dirname(os.path.abspath(file_path))
        )
        
        if result.stdout.strip():
            # Return as date only (YYYY-MM-DD) for cleaner display
            return parse_git_date(result.stdout)
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
    
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Prove the git date parser and the page refresh work, then exit'
    )
    
    args = parser.parse_args()
    
    if args.self_test:
        return self_test()
    
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

# ---------------------------------------------------------------------------
# Self-test (tallyfy/documentation#295).
#
# The pipeline pins Python 3.10, and only 3.10 rejects git's `Z`. A test run on
# 3.11 or later would pass on the broken code too, so the parse arms run against
# a datetime that refuses a trailing `Z` exactly as 3.10 does. On 3.10 that is
# what the real one already does; on later versions it is what keeps the arms
# able to fail.
# ---------------------------------------------------------------------------

class _Py310Datetime(datetime):
    @classmethod
    def fromisoformat(cls, date_string):
        if date_string[-1:] in ("Z", "z"):
            raise ValueError(f"Invalid isoformat string: {date_string!r}")
        return super().fromisoformat(date_string)


def _git(repo, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Self Test", GIT_AUTHOR_EMAIL="self-test@example.com",
               GIT_COMMITTER_NAME="Self Test", GIT_COMMITTER_EMAIL="self-test@example.com")
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(['git', '-c', 'commit.gpgsign=false', *args], cwd=repo, env=env,
                          capture_output=True, text=True, check=True).stdout


def self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        print(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    def parsed(value):
        try:
            return parse_git_date(value)
        except Exception as exc:  # noqa: BLE001 - an exception is a result here
            return f"raised {exc!r}"

    print(f"Self-test on Python {sys.version.split()[0]}: git dates parse the way 3.10 needs.")
    module = sys.modules[__name__]
    real = module.datetime
    module.datetime = _Py310Datetime
    try:
        got = parsed("2026-09-23T01:40:52Z")
        case("a UTC date ending in Z parses under Python 3.10 rules", got == "2026-09-23", got)
        got = parsed("2026-09-22T20:37:48-05:00")
        case("an offset date keeps the author's own calendar date", got == "2026-09-22", got)
        got = parsed("2026-09-23T01:40:52+00:00\n")
        case("+00:00, which git 2.43 prints for UTC (2.55 prints Z), still parses", got == "2026-09-23", got)
        got = parsed("2026-13-45T99:00:00Z")
        case("a malformed date raises ValueError rather than returning a date",
             got.startswith("raised ValueError"), got)
    finally:
        module.datetime = real

    # A real page in a scratch repository, refreshed through the script's own path.
    with tempfile.TemporaryDirectory() as tmp:
        _git(tmp, 'init', '-q')
        utc_page = Path(tmp, 'utc.mdx')
        offset_page = Path(tmp, 'offset.mdx')
        utc_page.write_text("---\ntitle: UTC\nlastUpdated: 2020-01-01\n---\n\nBody.\n", encoding='utf-8')
        offset_page.write_text("---\ntitle: Offset\nlastUpdated: 2020-01-01\n---\n\nBody.\n", encoding='utf-8')
        _git(tmp, 'add', 'offset.mdx')
        _git(tmp, 'commit', '-q', '-m', 'offset page', date="2026-09-22T20:37:48-05:00")
        _git(tmp, 'add', 'utc.mdx')
        _git(tmp, 'commit', '-q', '-m', 'utc page', date="2026-09-23T01:40:52+00:00")
        printed = _git(tmp, 'log', '-1', '--format=%aI', '--', 'utc.mdx').strip()
        module.datetime = _Py310Datetime
        try:
            refreshed = update_file_last_modified(str(utc_page))
            refreshed_offset = update_file_last_modified(str(offset_page))
        finally:
            module.datetime = real
        utc_now = frontmatter.load(str(utc_page)).get('lastUpdated')
        offset_now = frontmatter.load(str(offset_page)).get('lastUpdated')
        case("a page whose newest commit is dated in UTC gets its lastUpdated refreshed",
             refreshed is True and str(utc_now) == "2026-09-23",
             f"git printed {printed}, lastUpdated is now {utc_now}")
        case("a page whose newest commit carries an offset is refreshed to that date",
             refreshed_offset is True and str(offset_now) == "2026-09-22",
             f"lastUpdated is now {offset_now}")

    failed = cases.count(False)
    if failed:
        print(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0

if __name__ == "__main__":
    exit(main())