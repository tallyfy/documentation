#!/usr/bin/env python3
"""
validate-internal-links.py
Validates that all internal links in MDX files point to existing pages.
Run before committing to catch broken links early.

Usage:
    python scripts/validate-internal-links.py --dir src/content/docs
"""

import re
import os
import argparse
from pathlib import Path
from collections import defaultdict


def url_to_file_paths(url, base_dir):
    """Convert a /products/ URL to possible file paths."""
    # Remove /products/ prefix
    if url.startswith('/products/'):
        path = url[len('/products/'):]
    else:
        return []

    # Remove trailing slash for path construction
    path = path.rstrip('/')

    # Remove any anchor fragments
    path = path.split('#')[0]

    # Generate possible file paths
    possible_paths = [
        os.path.join(base_dir, path, 'index.mdx'),  # /path/ -> path/index.mdx
        os.path.join(base_dir, f"{path}.mdx"),       # /path/ -> path.mdx
    ]

    return possible_paths


def extract_internal_links(content):
    """Extract all internal /products/ links from MDX content."""
    links = set()

    # Markdown link pattern: [text](/products/path/)
    md_pattern = r'\[.*?\]\((/products/[^)#\s]+)\)'
    links.update(re.findall(md_pattern, content))

    # href attribute pattern: href="/products/path/"
    href_pattern = r'href="(/products/[^"#]+)"'
    links.update(re.findall(href_pattern, content))

    return links


def validate_file(file_path, base_dir):
    """Validate all internal links in a file."""
    broken_links = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    links = extract_internal_links(content)

    for link in links:
        possible_paths = url_to_file_paths(link, base_dir)

        # Check if any of the possible paths exist
        exists = any(os.path.isfile(p) for p in possible_paths)

        if not exists:
            broken_links.append(link)

    return broken_links


def main():
    parser = argparse.ArgumentParser(
        description='Validate internal links in MDX files'
    )
    parser.add_argument(
        '--dir',
        type=str,
        required=True,
        help='Base directory containing MDX files'
    )
    args = parser.parse_args()

    base_dir = Path(args.dir)
    if not base_dir.is_dir():
        print(f"Error: Invalid directory: {args.dir}")
        return 1

    # Find all MDX files
    mdx_files = list(base_dir.rglob('*.mdx'))

    # Track broken links by file
    broken_by_file = defaultdict(list)
    total_links_checked = 0

    for mdx_file in mdx_files:
        with open(mdx_file, 'r', encoding='utf-8') as f:
            content = f.read()

        links = extract_internal_links(content)
        total_links_checked += len(links)

        broken = validate_file(mdx_file, base_dir)
        if broken:
            relative_path = mdx_file.relative_to(base_dir)
            broken_by_file[str(relative_path)] = broken

    # Report results
    if broken_by_file:
        total_broken = sum(len(v) for v in broken_by_file.values())
        print(f"\n❌ Found {total_broken} broken links in {len(broken_by_file)} files:\n")
        for file_path, links in sorted(broken_by_file.items()):
            print(f"▶ {file_path}")
            for link in sorted(links):
                print(f"  └─ {link}")
        print(f"\nTotal links checked: {total_links_checked}")
        return 1
    else:
        print(f"✓ All internal links valid ({total_links_checked} links checked in {len(mdx_files)} files)")
        return 0


if __name__ == "__main__":
    exit(main())
