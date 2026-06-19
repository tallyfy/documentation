#!/usr/bin/env python3
"""
Accessibility lint for documentation content (.mdx).

Guards three WCAG-relevant content rules at the SOURCE level, before the pipeline
syncs content to support-docs (where Astro/Starlight renders it). Pairs with the
dist-level assertion in support-docs (scripts/a11y-dist-assert.mjs) which guards
the rendered output. Filed under tallyfy/documentation#72 (epic #66).

Rules:
  1. WCAG 1.3.1 (Info and Relationships) - heading structure.
     Starlight renders the frontmatter `title` as the page <h1>, so the first
     CONTENT heading must be <h2> (an H1->H3 jump is a skip), no level may be
     skipped going deeper (e.g. H2 -> H4), and there must be no <h1> in the body.
  2. WCAG 1.1.1 (Non-text Content) - image alternative text.
     Every markdown image ![](...) and raw <img> must have non-empty alt text,
     UNLESS (a) the image is a screenshots.tallyfy.com URL that has a caption in
     documentation_assets.csv (the support-docs remark plugin injects that alt at
     build time), or (b) a raw <img> is explicitly marked decorative
     (role="presentation"/"none" or aria-hidden="true") - empty alt is then correct.
  3. WCAG 2.2.2 (Pause, Stop, Hide) - D2 diagram animation.
     No ```d2 fence may declare style.animated (dot or block notation); animated
     "marching ants" connectors loop forever and cannot be paused (cf. #85, whose
     remark plugin strips them - this stops the anti-pattern at the source).

Scope/assumptions (validated against the current corpus, which has 0 of each):
  - Only markdown '#' headings are evaluated; raw <hN> content headings and Setext
    (underline) headings are not. The dist-level assertion is the rendered backstop.
  - Reference-style images (![][ref]) are not alt-checked (corpus uses none).
  - Fenced code (``` / ~~~), the frontmatter, and the auto-generated
    "## Related articles" section onward are ignored for headings/D2.

Exit 0 = clean, 1 = violations found (fails the pipeline).
"""
import argparse
import csv
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

SKIP_FILES = {"404.mdx"}
SKIP_DIR_PARTS = ["/changelog"]  # changelog is generated; matches markdown-lint.py

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)[^)]*\)")
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
# Attribute regexes require a preceding whitespace/tag boundary so a literal like
# data-x="alt='y'" cannot be mistaken for the alt attribute (regex, not a DOM parser).
ALT_ATTR_RE = re.compile(r"""(?:^|\s)alt\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
SRC_ATTR_RE = re.compile(r"""(?:^|\s)src\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
DECORATIVE_RE = re.compile(
    r"""(?:^|\s)(?:role\s*=\s*["'](?:presentation|none)["']|aria-hidden\s*=\s*["']true["'])""",
    re.IGNORECASE,
)
D2_ANIMATED_RE = re.compile(r"(?:\bstyle\.animated\b|\banimated\s*:\s*true\b)")


def attr_value(regex, tag):
    """Return the matched attribute value as a stripped string ("" if the
    attribute is absent OR present-but-empty). Handles empty double/single-quoted
    values without crashing (group can be "" which is falsy)."""
    m = regex.search(tag)
    if not m:
        return ""
    val = m.group(1) if m.group(1) is not None else m.group(2)
    return (val or "").strip()


def load_captioned_urls(csv_path):
    """Return set of production_url values (raw + URL-decoded) that have a non-empty
    ai_caption_alt (these get alt injected at build, so an empty source alt is OK)."""
    captioned = set()
    if not csv_path or not os.path.isfile(csv_path):
        return captioned
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            url = (row.get("production_url") or "").strip()
            alt = (row.get("ai_caption_alt") or "").strip()
            if url and alt:
                captioned.add(url)
                captioned.add(unquote(url))  # match refs that use literal slashes
    return captioned


def is_captioned(url, captioned):
    return url in captioned or unquote(url) in captioned


def iter_mdx(base_dir):
    for path, _subdirs, files in os.walk(base_dir):
        norm = path.replace(os.sep, "/")
        if any(part in norm for part in SKIP_DIR_PARTS):
            continue
        for fn in files:
            if fn.endswith(".mdx") and fn not in SKIP_FILES:
                yield os.path.join(path, fn)


def frontmatter_line_count(text):
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[: m.end()].count("\n") if m else 0


def lint_file(fp, captioned):
    """Return a list of (lineno, code, message) violations for one file."""
    text = Path(fp).read_text(encoding="utf-8", errors="replace")
    fm_lines = frontmatter_line_count(text)
    lines = text.splitlines()

    violations = []
    in_fence = False
    fence_char = None
    fence_len = 0
    fence_is_d2 = False
    prev_level = None
    first_heading_seen = False
    related_reached = False

    for i, line in enumerate(lines):
        lineno = i + 1

        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            marker_char = marker[0]
            if not in_fence:
                in_fence = True
                fence_char = marker_char
                fence_len = len(marker)
                fence_is_d2 = fence_match.group(2).strip().lower().startswith("d2")
                continue
            # closing fence (CommonMark): same char, length >= opening, nothing after
            if marker_char == fence_char and len(marker) >= fence_len and fence_match.group(2).strip() == "":
                in_fence = False
                fence_char = None
                fence_len = 0
                fence_is_d2 = False
                continue
            # otherwise a longer/info-bearing fence line inside the block - treat as content
        if in_fence:
            if fence_is_d2 and D2_ANIMATED_RE.search(line):
                violations.append(
                    (lineno, "2.2.2",
                     "D2 fence declares style.animated (infinite animation); remove it "
                     "(arrowheads convey direction). See #85.")
                )
            continue

        if lineno <= fm_lines:
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match and not related_reached:
            level = len(heading_match.group(1))
            heading_text = line.lstrip("#").strip().lower()
            if heading_text.startswith("related articles"):
                related_reached = True  # stop heading checks at the generated section
            else:
                if level == 1:
                    violations.append(
                        (lineno, "1.3.1",
                         "<h1> in body; the page title is already the H1. Start content at H2.")
                    )
                if not first_heading_seen:
                    first_heading_seen = True
                    if level != 2:
                        violations.append(
                            (lineno, "1.3.1",
                             f"first content heading is H{level}; it must be H2 "
                             f"(Starlight renders the title as H1, so H1->H{level} is a skip).")
                        )
                elif prev_level is not None and level > prev_level + 1:
                    violations.append(
                        (lineno, "1.3.1",
                         f"heading level skip H{prev_level} -> H{level}; do not skip levels.")
                    )
                prev_level = level

        # image alt text (markdown + raw <img>); checked everywhere, incl. after Related articles
        for m in MD_IMG_RE.finditer(line):
            alt = m.group(1).strip()
            url = m.group(2).strip().strip("<>")
            if not alt and not is_captioned(url, captioned):
                violations.append(
                    (lineno, "1.1.1",
                     f"image has empty alt text and no caption in documentation_assets.csv: {url}")
                )
        for tag_m in IMG_TAG_RE.finditer(line):
            tag = tag_m.group(0)
            if DECORATIVE_RE.search(tag):
                continue  # explicitly decorative: empty alt is correct, not a 1.1.1 failure
            alt = attr_value(ALT_ATTR_RE, tag)
            url = attr_value(SRC_ATTR_RE, tag)
            if not alt and not is_captioned(url, captioned):
                violations.append(
                    (lineno, "1.1.1",
                     f"<img> has empty/missing alt (and is not marked decorative) and no caption "
                     f"in documentation_assets.csv: {url or '<no src>'}")
                )

    return violations


def main():
    parser = argparse.ArgumentParser(description="Accessibility lint for documentation .mdx content")
    parser.add_argument("--dir", required=True, help="Base directory to scan (repo root or content dir)")
    parser.add_argument("--csv", default=None,
                        help="Path to documentation_assets.csv (default: auto-detect under --dir)")
    args = parser.parse_args()

    base_dir = Path(args.dir)
    if not base_dir.is_dir():
        print(f"Invalid directory path: {args.dir}")
        return 1

    csv_path = args.csv
    if not csv_path:
        for candidate in ("documentation_assets.csv",
                          os.path.join("..", "documentation_assets.csv")):
            p = base_dir / candidate
            if p.is_file():
                csv_path = str(p)
                break
    captioned = load_captioned_urls(csv_path)
    print(f"a11y-lint: scanning {base_dir}  (captioned-image URLs loaded: {len(captioned)})")

    total = 0
    bad_files = 0
    for fp in sorted(iter_mdx(str(base_dir))):
        violations = lint_file(fp, captioned)
        if violations:
            bad_files += 1
            print(f"\n{fp}")
            for lineno, code, msg in violations:
                total += 1
                print(f"  L{lineno} [WCAG {code}] {msg}")

    print(f"\na11y-lint: {total} violation(s) across {bad_files} file(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
