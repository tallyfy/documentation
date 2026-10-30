#!/usr/bin/env python3
"""
validate-internal-links.py
Validates that all internal links in MDX files point to existing pages.
Run before committing to catch broken links early.

Usage:
    python scripts/validate-internal-links.py --dir src/content/docs
    python scripts/validate-internal-links.py --dir src/content/docs --strict-anchors
    python scripts/validate-internal-links.py --self-test

A link with a #anchor is checked like any other: its page must exist (#434; before
that, the pattern stopped at '#' and every anchored link was skipped, page and all).
The anchor is then looked up in the target page: its headings, slugged the way the
site slugs them (Astro's github-slugger: lowercase, punctuation dropped except '-'
and '_', each space a '-', a repeat gets -1, -2, then one trailing '-' dropped, as
Astro does without experimentalHeadingIdCompat), plus any id="..." in the page,
plus Starlight's _top. A missing anchor is a WARNING and does not change the exit code,
unless --strict-anchors is given. The page still opens when its anchor is missing,
so it is a weaker failure than a missing page.

Exit codes: 0 every page exists (and, with --strict-anchors, every anchor),
1 a broken link or an invalid --dir, or a failed --self-test case, 2 a usage error.
"""

import re
import os
import sys
import argparse
import tempfile
import unicodedata
from pathlib import Path
from collections import defaultdict
from urllib.parse import unquote


def split_anchor(url):
    """Split '/products/a/b/#c' into ('/products/a/b/', 'c'). The anchor is '' if none."""
    page, _, anchor = url.partition('#')
    return page, anchor


def url_to_file_paths(url, base_dir):
    """Convert a /products/ URL to possible file paths."""
    # Remove any anchor fragment first, so a trailing slash before it is stripped too
    url = split_anchor(url)[0]

    # Remove /products/ prefix
    if url.startswith('/products/'):
        path = url[len('/products/'):]
    else:
        return []

    # Remove trailing slash for path construction
    path = path.rstrip('/')

    # Generate possible file paths
    possible_paths = [
        os.path.join(base_dir, path, 'index.mdx'),  # /path/ -> path/index.mdx
        os.path.join(base_dir, f"{path}.mdx"),       # /path/ -> path.mdx
    ]

    return possible_paths


def extract_internal_links(content):
    """Extract all internal /products/ links from MDX content, anchored or not."""
    links = set()

    # Markdown link pattern: [text](/products/path/) or [text](/products/path/#anchor)
    md_pattern = r'\[.*?\]\((/products/[^)\s]+)\)'
    links.update(re.findall(md_pattern, content))

    # href attribute pattern: href="/products/path/" or href="/products/path/#anchor"
    href_pattern = r'href="(/products/[^"]+)"'
    links.update(re.findall(href_pattern, content))

    return links


def slugify(text):
    """github-slugger's slug for one heading: lowercase, drop every character that is
    not a letter, number, mark, space, '-' or '_', then turn each space into '-'."""
    kept = []
    for ch in text.lower():
        if ch in ' -_' or unicodedata.category(ch)[0] in 'LNM':
            kept.append(ch)
    return ''.join(kept).replace(' ', '-')


def heading_text(raw):
    """The text a reader sees in a markdown heading, which is what gets slugged."""
    text = re.sub(r'\[\^[^\]]+\]', '', raw)                 # footnote references
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)  # links and images keep their text
    text = re.sub(r'<[^>]+>', '', text)                     # inline HTML or JSX tags
    text = text.replace('`', '')
    text = re.sub(r'(\*\*|__|\*)', '', text)                # bold and italic markers
    return text.strip()


_anchor_cache = {}


def page_anchors(file_path):
    """Every anchor a page offers: slugged headings outside code fences, id="..." values,
    and Starlight's _top."""
    if file_path in _anchor_cache:
        return _anchor_cache[file_path]
    anchors = {'_top'}
    seen = {}
    in_fence = False
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for line in content.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r'^(#{1,6})\s+(.*?)\s*#*\s*$', line)
        if m:
            slug = slugify(heading_text(m.group(2)))
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            anchor = slug if n == 0 else f"{slug}-{n}"
            if anchor.endswith('-'):
                anchor = anchor[:-1]    # Astro drops one trailing '-' (rehype-collect-headings)
            anchors.add(anchor)
    anchors.update(re.findall(r'''\bid=["']([^"']+)["']''', content))
    _anchor_cache[file_path] = anchors
    return anchors


def validate_file(file_path, base_dir):
    """Validate all internal links in a file.
    Returns (broken_links, missing_anchors): links whose page does not exist, and links
    whose page exists but does not offer the anchor."""
    broken_links = []
    missing_anchors = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    links = extract_internal_links(content)

    for link in links:
        possible_paths = url_to_file_paths(link, base_dir)

        # Check if any of the possible paths exist
        target = next((p for p in possible_paths if os.path.isfile(p)), None)

        if target is None:
            broken_links.append(link)
            continue

        anchor = split_anchor(link)[1]
        if anchor and unquote(anchor) not in page_anchors(target):
            missing_anchors.append(link)

    return broken_links, missing_anchors


def run(base_dir, strict_anchors=False, out=print):
    """Check every .mdx under base_dir. Returns (exit code, broken by file, missing anchors
    by file, links checked, anchored links checked)."""
    base_dir = Path(base_dir)
    if not base_dir.is_dir():
        out(f"Error: Invalid directory: {base_dir}")
        return 1, {}, {}, 0, 0

    # Find all MDX files
    mdx_files = list(base_dir.rglob('*.mdx'))

    # Track broken links and missing anchors by file
    broken_by_file = defaultdict(list)
    missing_by_file = defaultdict(list)
    total_links_checked = 0
    anchored_links_checked = 0

    for mdx_file in mdx_files:
        with open(mdx_file, 'r', encoding='utf-8') as f:
            content = f.read()

        links = extract_internal_links(content)
        total_links_checked += len(links)
        anchored_links_checked += sum(1 for link in links if '#' in link)

        broken, missing = validate_file(mdx_file, base_dir)
        relative_path = str(mdx_file.relative_to(base_dir))
        if broken:
            broken_by_file[relative_path] = broken
        if missing:
            missing_by_file[relative_path] = missing

    total_missing = sum(len(v) for v in missing_by_file.values())
    anchor_line = (f"Links with an anchor: {anchored_links_checked}. "
                   f"Anchors not found on their page: {total_missing}"
                   + ("" if strict_anchors else " (a warning; --strict-anchors makes it a failure)")
                   + ".")

    if missing_by_file:
        out(f"\nAnchors not found on an existing page ({total_missing} in {len(missing_by_file)} files):\n")
        for file_path, links in sorted(missing_by_file.items()):
            out(f"▶ {file_path}")
            for link in sorted(links):
                out(f"  └─ {link}")

    # Report results
    if broken_by_file:
        total_broken = sum(len(v) for v in broken_by_file.values())
        out(f"\n❌ Found {total_broken} broken links in {len(broken_by_file)} files:\n")
        for file_path, links in sorted(broken_by_file.items()):
            out(f"▶ {file_path}")
            for link in sorted(links):
                out(f"  └─ {link}")
        out(f"\nTotal links checked: {total_links_checked}")
        out(anchor_line)
        return 1, broken_by_file, missing_by_file, total_links_checked, anchored_links_checked

    out(anchor_line)
    if strict_anchors and missing_by_file:
        out(f"\n❌ {total_missing} anchors not found, and --strict-anchors is set "
            f"({total_links_checked} links checked in {len(mdx_files)} files)")
        return 1, broken_by_file, missing_by_file, total_links_checked, anchored_links_checked

    out(f"✓ All internal links valid ({total_links_checked} links checked in {len(mdx_files)} files)")
    return 0, broken_by_file, missing_by_file, total_links_checked, anchored_links_checked


def self_test():
    """Prove each rule can go red and go green, by running run() on small planted trees."""
    target_page = (
        "---\nid: t\n---\n\n"
        "## Real heading\n\ntext\n\n"
        "### Second (part) `code`\n\ntext\n\n"
        "## Price, in USD $\n\ntext\n\n"
        "## Real heading\n\nthe same heading again\n\n"
        "```markdown\n## Not a heading\n```\n\n"
        '<div id="custom-spot">x</div>\n'
    )
    other_page = "---\nid: o\n---\n\nplain page\n"
    good_links = (
        "[a](/products/real/) [b](/products/real/#real-heading) "
        "[c](/products/real/#real-heading-1) [d](/products/real/#second-part-code) "
        "[e](/products/real/#custom-spot) [f](/products/other/#_top) "
        "[h](/products/real/#price-in-usd) "
        '<a href="/products/other/#_top">g</a>\n'
    )
    cases = [
        # (name, source page body, strict, expected rc, expected broken, expected missing anchors)
        ("good links of every kind pass, strict too", good_links, True, 0, [], []),
        ("a planted anchored link to a missing page fails",
         "[x](/products/zq-missing-page/#x)\n", False, 1, ["/products/zq-missing-page/#x"], []),
        ("a plain link to a missing page still fails",
         "[x](/products/zq-missing-plain/)\n", False, 1, ["/products/zq-missing-plain/"], []),
        ("an anchored href to a missing page fails",
         '<a href="/products/zq-missing-href/#x">x</a>\n', False, 1, ["/products/zq-missing-href/#x"], []),
        ("a made-up anchor on a real page is a warning only",
         "[x](/products/real/#no-such-heading)\n", False, 0, [], ["/products/real/#no-such-heading"]),
        ("a made-up anchor on a real page fails with --strict-anchors",
         "[x](/products/real/#no-such-heading)\n", True, 1, [], ["/products/real/#no-such-heading"]),
        ("a heading inside a code fence is not an anchor",
         "[x](/products/real/#not-a-heading)\n", False, 0, [], ["/products/real/#not-a-heading"]),
        ("a third copy of a repeated heading is not an anchor",
         "[x](/products/real/#real-heading-2)\n", False, 0, [], ["/products/real/#real-heading-2"]),
    ]
    failed = 0
    for name, body, strict, want_rc, want_broken, want_missing in cases:
        _anchor_cache.clear()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'real'))
            with open(os.path.join(tmp, 'real', 'index.mdx'), 'w', encoding='utf-8') as f:
                f.write(target_page)
            with open(os.path.join(tmp, 'other.mdx'), 'w', encoding='utf-8') as f:
                f.write(other_page)
            with open(os.path.join(tmp, 'source.mdx'), 'w', encoding='utf-8') as f:
                f.write("---\nid: s\n---\n\n" + body)
            rc, broken, missing, total, anchored = run(tmp, strict_anchors=strict, out=lambda *_: None)
        got_broken = sorted(broken.get('source.mdx', []))
        got_missing = sorted(missing.get('source.mdx', []))
        ok = (rc == want_rc and got_broken == sorted(want_broken)
              and got_missing == sorted(want_missing) and total > 0)
        failed += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {name} - rc={rc} broken={got_broken} missing={got_missing}")
    _anchor_cache.clear()
    if failed:
        print(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Validate internal links in MDX files'
    )
    parser.add_argument(
        '--dir',
        type=str,
        help='Base directory containing MDX files'
    )
    parser.add_argument(
        '--strict-anchors',
        action='store_true',
        help='Fail when a link points at an anchor its page does not have'
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Prove every rule can fail and pass on planted pages, then exit'
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.dir:
        parser.error('--dir is required unless --self-test is given')

    return run(args.dir, strict_anchors=args.strict_anchors)[0]


if __name__ == "__main__":
    sys.exit(main())
