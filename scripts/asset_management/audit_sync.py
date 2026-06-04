#!/usr/bin/env python3
"""
Audit + safe-auto sync for the documentation asset inventory.

Two read-mostly operations that need NO R2 credentials (they only read the CSV
and scan the docs tree):

  audit  - read-only. Scans src/content/docs for screenshots.tallyfy.com image
           URLs, cross-references documentation_assets.csv, and reports:
             * referenced-in-docs-but-not-in-inventory  (the real gap to close)
             * dead URLs (url_exists=False / source_type=missing)
             * orphaned rows (source_type=orphaned, not referenced anywhere)
             * rows missing AI captions
           Writes a markdown report; mutates nothing.

  sync   - safe-auto only. For every image URL referenced in docs but absent
           from the inventory, appends a SKELETON row (no caption yet) so the
           Large-Job caption pass can fill it. HEAD-checks each URL, dedupes by
           normalized URL, refreshes article_ids on existing referenced rows.
           Destructive items (dead URLs, orphans) are REPORT-ONLY - never
           deleted here. Supports --dry-run. One atomic CSV write.

Run from the asset_management directory:
    python3 audit_sync.py audit  --out /path/report.md
    python3 audit_sync.py sync   --dry-run
    python3 audit_sync.py sync
"""

import os
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import requests

from config import config
from asset_inventory import AssetInventory

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
PUBLIC_BASE = config.r2_public_url.rstrip('/')          # https://screenshots.tallyfy.com
DOCS_DIR = config.inventory_csv.parent / 'src' / 'content' / 'docs'

# Match a screenshots.tallyfy.com URL; stop at whitespace / markdown / quote delims.
_URL_RE = re.compile(re.escape(PUBLIC_BASE) + r'/[^\s"\'<>)\]\\]+')


def normalize_url(url: str) -> str:
    """Canonical form for matching/dedup: unquote %2F etc, strip trailing slash/punct."""
    if not url:
        return ''
    u = unquote(url.strip())
    u = u.rstrip('.,;')          # trailing sentence punctuation that can cling to a URL
    u = u.rstrip('/')
    return u


def _iter_doc_files(docs_dir: Path):
    for ext in ('*.md', '*.mdx'):
        yield from docs_dir.rglob(ext)


_ID_RE = re.compile(r'^id:\s*([A-Za-z0-9]+)\s*$', re.MULTILINE)


def _frontmatter_id(text: str) -> str:
    """Extract the frontmatter `id:` (Starlight article id) if present."""
    if not text.startswith('---'):
        return ''
    end = text.find('\n---', 3)
    if end == -1:
        return ''
    m = _ID_RE.search(text[:end])
    return m.group(1) if m else ''


def scan_references(docs_dir: Path = DOCS_DIR) -> dict:
    """
    Scan all docs for screenshots.tallyfy.com URLs.

    Returns: { normalized_url: {'raw': <as-found, slash-stripped>,
                                 'files': set[str], 'ids': set[str]} }
    """
    refs: dict = {}
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs dir not found: {docs_dir}")

    for path in _iter_doc_files(docs_dir):
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        urls = _URL_RE.findall(text)
        if not urls:
            continue
        art_id = _frontmatter_id(text)
        rel = str(path.relative_to(docs_dir))
        for raw in urls:
            raw_clean = raw.rstrip('.,;').rstrip('/')
            norm = normalize_url(raw_clean)
            entry = refs.setdefault(norm, {'raw': raw_clean, 'files': set(), 'ids': set()})
            entry['files'].add(rel)
            if art_id:
                entry['ids'].add(art_id)
    return refs


def _is_image(file_type: str) -> bool:
    return (file_type or '').lower() in IMAGE_EXTS


def _row_dead(row: dict) -> bool:
    return row.get('source_type') == 'missing' or str(row.get('url_exists', '')).lower() == 'false'


def _row_needs_caption(row: dict) -> bool:
    return (
        _is_image(row.get('file_type', ''))
        and row.get('source_type') != 'missing'
        and not (row.get('ai_caption_alt') or '').strip()
    )


def audit(inv: AssetInventory, docs_dir: Path = DOCS_DIR) -> dict:
    rows = inv.read_inventory()
    csv_norms = {normalize_url(r.get('production_url', '')) for r in rows if r.get('production_url')}
    refs = scan_references(docs_dir)

    referenced_not_in_inv = sorted(n for n in refs if n not in csv_norms)
    # An image-extension URL referenced in docs but not inventoried is the caption gap.
    ref_missing_images = [n for n in referenced_not_in_inv
                          if Path(unquote(n)).suffix.lower() in IMAGE_EXTS]

    dead = [r for r in rows if _row_dead(r)]
    orphaned = [r for r in rows if r.get('source_type') == 'orphaned']
    missing_caption = [r for r in rows if _row_needs_caption(r)]
    referenced_rows = [r for r in rows
                       if normalize_url(r.get('production_url', '')) in refs]

    return {
        'docs_dir': str(docs_dir),
        'total_rows': len(rows),
        'distinct_urls_in_docs': len(refs),
        'referenced_not_in_inventory': referenced_not_in_inv,
        'referenced_not_in_inventory_images': ref_missing_images,
        'dead_rows': dead,
        'orphaned_rows': orphaned,
        'missing_caption_rows': missing_caption,
        'referenced_rows_count': len(referenced_rows),
        'refs': refs,
    }


def write_report(a: dict, out_path: Path):
    L = []
    L.append(f"# Documentation asset audit - {datetime.now().isoformat(timespec='seconds')}")
    L.append("")
    L.append(f"- Inventory rows: **{a['total_rows']}**")
    L.append(f"- Distinct screenshots.tallyfy.com URLs referenced in docs: **{a['distinct_urls_in_docs']}**")
    L.append(f"- Inventory rows actually referenced in docs: **{a['referenced_rows_count']}**")
    L.append(f"- Referenced in docs but NOT in inventory: **{len(a['referenced_not_in_inventory'])}** "
             f"({len(a['referenced_not_in_inventory_images'])} are images -> caption these)")
    L.append(f"- Dead rows (404 / source_type=missing): **{len(a['dead_rows'])}**  [GATED - report only]")
    L.append(f"- Orphaned rows (source_type=orphaned): **{len(a['orphaned_rows'])}**  [GATED - report only]")
    L.append(f"- Image rows missing AI captions: **{len(a['missing_caption_rows'])}**  [caption these]")
    L.append("")

    def block(title, items, fmt, limit=40):
        L.append(f"## {title} ({len(items)})")
        if not items:
            L.append("_none_"); L.append(""); return
        for it in items[:limit]:
            L.append(f"- {fmt(it)}")
        if len(items) > limit:
            L.append(f"- ... and {len(items) - limit} more")
        L.append("")

    block("Referenced in docs but NOT in inventory (SAFE-AUTO: sync adds skeleton rows)",
          a['referenced_not_in_inventory'], lambda n: f"`{n}`")
    block("Dead / 404 rows (GATED - human decides delete vs fix-reference)",
          a['dead_rows'], lambda r: f"`{r.get('production_url','')}` (source_type={r.get('source_type')})")
    block("Orphaned rows - not referenced anywhere (GATED - human decides cleanup)",
          a['orphaned_rows'], lambda r: f"`{r.get('filename','')}` ({r.get('file_type','')})")
    block("Image rows missing captions (Large-Job caption pass fills these)",
          a['missing_caption_rows'], lambda r: f"`{r.get('production_url','')}`")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(L), encoding='utf-8')


def sync(inv: AssetInventory, docs_dir: Path = DOCS_DIR, dry_run: bool = True,
         head_check: bool = True) -> dict:
    """Safe-auto: add skeleton rows for referenced-not-in-inventory URLs; refresh refs."""
    rows = inv.read_inventory()
    refs = scan_references(docs_dir)
    norm_to_row = {normalize_url(r.get('production_url', '')): r for r in rows if r.get('production_url')}

    added, refreshed = [], 0

    # 1) Refresh article_ids/article_count on existing referenced rows (safe-auto).
    for norm, entry in refs.items():
        row = norm_to_row.get(norm)
        if row is None:
            continue
        if entry['ids']:
            existing_ids = set(filter(None, (row.get('article_ids') or '').split(',')))
            merged = existing_ids | entry['ids']
            new_val = ','.join(sorted(merged))
            if new_val != (row.get('article_ids') or '') or row.get('article_count') != str(len(merged)):
                row['article_ids'] = new_val
                row['article_count'] = str(len(merged))
                refreshed += 1

    # 2) Add skeleton rows for the not-in-inventory URLs.
    for norm, entry in sorted(refs.items()):
        if norm in norm_to_row:
            continue
        raw = entry['raw']
        decoded = unquote(raw)
        r2_key = decoded[len(PUBLIC_BASE) + 1:] if decoded.startswith(PUBLIC_BASE + '/') else decoded
        suffix = Path(decoded).suffix.lower()
        url_ok = True
        if head_check:
            try:
                resp = requests.head(raw, timeout=6, allow_redirects=True)
                url_ok = resp.status_code == 200
            except requests.exceptions.RequestException:
                url_ok = False
        is_img = suffix in IMAGE_EXTS
        skel = {
            'filename': Path(r2_key).name,
            'r2_key': r2_key,
            'production_url': raw,                       # as-found form -> build plugin matches
            'source_type': 'native' if url_ok else 'missing',
            'file_type': suffix or 'unknown',
            'file_size': '',
            'file_size_bytes': '0',
            'url_exists': 'True' if url_ok else 'False',
            'article_ids': ','.join(sorted(entry['ids'])),
            'article_count': str(len(entry['ids'])),
            'last_modified': '',
            'etag': '',
            'ai_caption_alt': '',
            'ai_caption_descriptive': '',
            'ai_caption_seo': '',
            'needs_caption': 'yes' if (is_img and url_ok) else 'no',
        }
        rows.append(inv._fill_defaults(skel))
        norm_to_row[norm] = skel
        added.append({'url': raw, 'url_ok': url_ok, 'is_image': is_img})

    summary = {
        'added': len(added),
        'added_images_live': sum(1 for a in added if a['is_image'] and a['url_ok']),
        'added_dead': sum(1 for a in added if not a['url_ok']),
        'refreshed_refs': refreshed,
        'dry_run': dry_run,
        'sample_added': added[:15],
    }
    if not dry_run and (added or refreshed):
        inv.write_inventory(rows)
    return summary


def _load_skip() -> set:
    """URLs to skip permanently (poison items: blank/broken captures a human must re-shoot).
    One normalized URL per line in caption-skip.txt beside this script; '#' comments allowed."""
    p = Path(__file__).parent / 'caption-skip.txt'
    if not p.exists():
        return set()
    return {normalize_url(ln) for ln in p.read_text(encoding='utf-8').splitlines()
            if ln.strip() and not ln.lstrip().startswith('#')}


def worklist(inv: AssetInventory, limit: int = 5) -> list:
    """Next image rows still needing captions (image, empty alt, not 404), minus the skip-list."""
    skip = _load_skip()
    out = []
    for r in inv.read_inventory():
        if _row_needs_caption(r) and normalize_url(r.get('production_url', '')) not in skip:
            out.append(r.get('production_url', ''))
            if len(out) >= limit:
                break
    return out


def set_caption(inv: AssetInventory, url: str, alt: str, descriptive: str, seo: str) -> bool:
    """Write the 3 captions for the row whose production_url matches (atomic)."""
    rows = inv.read_inventory()
    found = False
    for r in rows:
        if inv._urls_match(r.get('production_url', ''), url):
            r['ai_caption_alt'] = alt.strip()
            r['ai_caption_descriptive'] = descriptive.strip()
            r['ai_caption_seo'] = seo.strip()
            r['needs_caption'] = 'no'
            found = True
            break
    if found:
        inv.write_inventory(rows)
    return found


def main():
    p = argparse.ArgumentParser(description='Audit / safe-auto sync the documentation asset inventory')
    sub = p.add_subparsers(dest='cmd')

    ap = sub.add_parser('audit', help='Read-only audit + report (no mutation)')
    ap.add_argument('--out', help='Write markdown report to this path (default: stdout summary only)')

    sp = sub.add_parser('sync', help='Safe-auto: add skeleton rows + refresh refs')
    sp.add_argument('--dry-run', action='store_true', help='Show what would change, write nothing')
    sp.add_argument('--no-head-check', action='store_true', help='Skip HEAD url_exists checks (faster)')

    wp = sub.add_parser('worklist', help='Next uncaptioned image URLs')
    wp.add_argument('--limit', type=int, default=5)

    cp = sub.add_parser('set-caption', help='Write the 3 captions for one URL')
    cp.add_argument('--url', required=True)
    cp.add_argument('--alt', required=True)
    cp.add_argument('--descriptive', required=True)
    cp.add_argument('--seo', required=True)

    args = p.parse_args()
    if not args.cmd:
        p.print_help(); sys.exit(1)

    inv = AssetInventory()

    if args.cmd == 'worklist':
        for u in worklist(inv, args.limit):
            print(u)
        sys.exit(0)
    if args.cmd == 'set-caption':
        ok = set_caption(inv, args.url, args.alt, args.descriptive, args.seo)
        print("OK" if ok else "NOT_FOUND")
        sys.exit(0 if ok else 1)

    if args.cmd == 'audit':
        a = audit(inv)
        print(f"Inventory rows: {a['total_rows']}")
        print(f"URLs referenced in docs: {a['distinct_urls_in_docs']}")
        print(f"Referenced-not-in-inventory: {len(a['referenced_not_in_inventory'])} "
              f"({len(a['referenced_not_in_inventory_images'])} images)")
        print(f"Dead rows: {len(a['dead_rows'])}  |  Orphaned: {len(a['orphaned_rows'])}  |  "
              f"Missing captions: {len(a['missing_caption_rows'])}")
        if args.out:
            write_report(a, Path(args.out))
            print(f"Report written: {args.out}")
        sys.exit(0)

    if args.cmd == 'sync':
        s = sync(inv, dry_run=args.dry_run, head_check=not args.no_head_check)
        tag = 'DRY-RUN' if s['dry_run'] else 'APPLIED'
        print(f"[{tag}] added={s['added']} (live images={s['added_images_live']}, dead={s['added_dead']}) "
              f"refreshed_refs={s['refreshed_refs']}")
        for ex in s['sample_added']:
            print(f"  + {ex['url']}  ok={ex['url_ok']} img={ex['is_image']}")
        sys.exit(0)


if __name__ == '__main__':
    main()
