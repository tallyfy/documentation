#!/usr/bin/env python3
"""
Audit + safe-auto sync for the documentation asset inventory.

Two read-mostly operations that need NO R2 credentials (they only read the CSV
and scan the docs tree):

  audit  - read-only. Scans src/content/docs for screenshots.tallyfy.com image
           URLs and for repository image paths (/screenshots/...), cross-references
           documentation_assets.csv (URLs by production_url, paths by repo_path),
           and reports:
             * referenced-in-docs-but-not-in-inventory  (the real gap to close)
             * repository image paths with no row (the support-docs build fails on these)
             * dead URLs (url_exists=False / source_type=missing)
             * orphaned rows (source_type=orphaned, not referenced anywhere)
             * rows missing AI captions
           Writes a markdown report; mutates nothing.

  sync   - safe-auto only. For every image URL referenced in docs but absent
           from the inventory, appends a SKELETON row (no caption yet) for the
           caption workflow to fill (`worklist`, then `orchestrator.py caption
           --url` in a Claude Code session, or `set-caption`). HEAD-checks
           each URL, dedupes by normalized URL, refreshes article_ids on
           existing referenced rows. It leaves repository image paths
           (/screenshots/...) alone: the job that uploads those owns their rows.
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

# Match an image committed to this repository and linked by its root-relative path, as in
# ![alt](/screenshots/launchbrightly/x.png) or src="/screenshots/...". The support-docs build
# swaps it for the row's production_url, looked up by repo_path (#462). The lookbehind keeps
# it to a path that starts a link target or attribute, so it never matches inside a URL.
_REPO_PATH_RE = re.compile(r'(?<=[(<"\'])/screenshots/[^\s"\'<>)\]\\]+')

# scan_references tags each entry with one of these.
KIND_URL = 'url'
KIND_REPO_PATH = 'repo_path'


def normalize_url(url: str) -> str:
    """Canonical form for matching/dedup: unquote %2F etc, strip trailing slash/punct."""
    if not url:
        return ''
    u = unquote(url.strip())
    u = u.rstrip('.,;')          # trailing sentence punctuation that can cling to a URL
    u = u.rstrip('/')
    return u


def normalize_repo_path(path: str) -> str:
    """Canonical form of a repository image path: decoded, one leading slash, no trailing punct."""
    if not path:
        return ''
    p = unquote(path.strip()).rstrip('.,;').rstrip('/')
    return '/' + p.lstrip('/') if p else ''


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
    Scan all docs for screenshots.tallyfy.com URLs and /screenshots/ repository paths.

    Returns: { normalized: {'raw': <as-found, slash-stripped>, 'kind': KIND_URL or
                            KIND_REPO_PATH, 'files': set[str], 'ids': set[str]} }
    A URL key starts with https://, a repository path key with /screenshots/, so the two
    never collide.
    """
    refs: dict = {}
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs dir not found: {docs_dir}")

    for path in _iter_doc_files(docs_dir):
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        found = ([(KIND_URL, raw) for raw in _URL_RE.findall(text)]
                 + [(KIND_REPO_PATH, raw) for raw in _REPO_PATH_RE.findall(text)])
        if not found:
            continue
        art_id = _frontmatter_id(text)
        rel = str(path.relative_to(docs_dir))
        for kind, raw in found:
            raw_clean = raw.rstrip('.,;').rstrip('/')
            norm = normalize_url(raw_clean) if kind == KIND_URL else normalize_repo_path(raw_clean)
            entry = refs.setdefault(norm, {'raw': raw_clean, 'kind': kind, 'files': set(), 'ids': set()})
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
    csv_repo_paths = {normalize_repo_path(r.get('repo_path', '')) for r in rows if r.get('repo_path')}
    refs = scan_references(docs_dir)
    url_refs = {n for n, e in refs.items() if e['kind'] == KIND_URL}
    repo_path_refs = {n for n, e in refs.items() if e['kind'] == KIND_REPO_PATH}

    referenced_not_in_inv = sorted(n for n in url_refs if n not in csv_norms)
    # An image-extension URL referenced in docs but not inventoried is the caption gap.
    ref_missing_images = [n for n in referenced_not_in_inv
                          if Path(unquote(n)).suffix.lower() in IMAGE_EXTS]
    # A repository image path is mapped by repo_path, never by URL. One with no row breaks
    # the support-docs build, and sync does not add it, so it is listed on its own.
    repo_paths_not_in_inv = sorted(n for n in repo_path_refs if n not in csv_repo_paths)

    dead = [r for r in rows if _row_dead(r)]
    orphaned = [r for r in rows if r.get('source_type') == 'orphaned']
    missing_caption = [r for r in rows if _row_needs_caption(r)]
    referenced_rows = [r for r in rows
                       if normalize_url(r.get('production_url', '')) in url_refs
                       or (r.get('repo_path') and normalize_repo_path(r['repo_path']) in repo_path_refs)]

    return {
        'docs_dir': str(docs_dir),
        'total_rows': len(rows),
        'distinct_urls_in_docs': len(url_refs),
        'distinct_repo_paths_in_docs': len(repo_path_refs),
        'referenced_not_in_inventory': referenced_not_in_inv,
        'referenced_not_in_inventory_images': ref_missing_images,
        'repo_paths_not_in_inventory': repo_paths_not_in_inv,
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
    L.append(f"- Distinct repository image paths (/screenshots/...) referenced in docs: "
             f"**{a['distinct_repo_paths_in_docs']}**")
    L.append(f"- Inventory rows actually referenced in docs: **{a['referenced_rows_count']}**")
    L.append(f"- Referenced in docs but NOT in inventory: **{len(a['referenced_not_in_inventory'])}** "
             f"({len(a['referenced_not_in_inventory_images'])} are images -> caption these)")
    L.append(f"- Repository image paths with no row (repo_path): **{len(a['repo_paths_not_in_inventory'])}** "
             f"[the support-docs build fails on these; sync does not add them]")
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
    block("Repository image paths with no row (the job that uploads screenshots/ owns these rows)",
          a['repo_paths_not_in_inventory'], lambda n: f"`{n}`")
    block("Dead / 404 rows (GATED - human decides delete vs fix-reference)",
          a['dead_rows'], lambda r: f"`{r.get('production_url','')}` (source_type={r.get('source_type')})")
    block("Orphaned rows - not referenced anywhere (GATED - human decides cleanup)",
          a['orphaned_rows'], lambda r: f"`{r.get('filename','')}` ({r.get('file_type','')})")
    block("Image rows missing captions (caption them in batches: worklist, then orchestrator.py caption --url)",
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

    # Repository image paths (/screenshots/...) are skipped in both steps below: the job that
    # uploads those images owns their rows, and a skeleton row here would carry no repo_path
    # and no hash, so it could only contradict that job (#462).
    refs = {n: e for n, e in refs.items() if e['kind'] != KIND_REPO_PATH}

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
        # _fill_defaults gives the skeleton source=legacy-unknown: nobody recorded who made
        # an image that turned up in the docs with no row.
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


def _self_test() -> int:
    """Prove audit maps /screenshots/ paths by repo_path and sync leaves them alone (#462).

    Works on a docs folder and a CSV it builds in a temporary directory, with no network
    (sync runs without its HEAD check). Never reads or writes documentation_assets.csv.
    Returns 0 when every case passes, 1 when one fails.
    """
    import csv
    import tempfile

    results = []

    def check(name, ok, detail=''):
        results.append(ok)
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ''))

    known = f'{PUBLIC_BASE}/tallyfy/pro/known.png'
    unknown = f'{PUBLIC_BASE}/tallyfy/pro/unknown.png'
    mapped_url = f'{PUBLIC_BASE}/launchbrightly/mapped.0123456789ab.png'
    article_id = 'a' * 32
    page = (f"---\nid: {article_id}\ntitle: Test\n---\n\n"
            f"![Known]({known})\n\n"
            f"![Unknown]({unknown})\n\n"
            f"![Mapped](/screenshots/launchbrightly/mapped.png)\n\n"
            f'<img src="/screenshots/launchbrightly/unmapped.png" alt="Unmapped" />\n\n'
            f"See https://tallyfy.com/products/screenshots/not-a-repo-path.png for the old page.\n")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docs = tmp / 'docs'
        docs.mkdir()
        (docs / 'page.mdx').write_text(page, encoding='utf-8')
        csv_path = tmp / 'inventory.csv'
        rows = [
            {'filename': 'known.png', 'r2_key': 'tallyfy/pro/known.png', 'production_url': known,
             'file_type': '.png', 'source': 'legacy-unknown'},
            {'filename': 'mapped.0123456789ab.png', 'r2_key': 'launchbrightly/mapped.0123456789ab.png',
             'production_url': mapped_url, 'file_type': '.png', 'article_ids': 'old',
             'article_count': '1', 'source': 'launchbrightly',
             'repo_path': '/screenshots/launchbrightly/mapped.png'},
        ]
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=AssetInventory.COLUMNS, lineterminator='\n')
            writer.writeheader()
            writer.writerows(dict({c: '' for c in AssetInventory.COLUMNS}, **r) for r in rows)
        inv = AssetInventory(csv_path)

        a = audit(inv, docs)
        check('audit finds both /screenshots/ paths', a['distinct_repo_paths_in_docs'] == 2,
              str(a['distinct_repo_paths_in_docs']))
        check('audit finds both https URLs and nothing else as a URL', a['distinct_urls_in_docs'] == 2,
              str(a['distinct_urls_in_docs']))
        check('audit maps a /screenshots/ path to its row by repo_path, and lists only the unmapped one',
              a['repo_paths_not_in_inventory'] == ['/screenshots/launchbrightly/unmapped.png'],
              str(a['repo_paths_not_in_inventory']))
        check('audit keeps /screenshots/ paths out of the list sync would add',
              a['referenced_not_in_inventory'] == [unknown], str(a['referenced_not_in_inventory']))
        check('audit counts the repo_path row as referenced', a['referenced_rows_count'] == 2,
              str(a['referenced_rows_count']))

        s = sync(inv, docs, dry_run=False, head_check=False)
        after = inv.read_inventory()
        by_url = {r['production_url']: r for r in after}
        check('sync adds a row for the unknown URL only', s['added'] == 1 and unknown in by_url
              and len(after) == 3, f"added={s['added']} rows={len(after)}")
        check('sync adds no row for a /screenshots/ path',
              not any('unmapped' in (r.get('r2_key', '') + r.get('production_url', '')) for r in after))
        check("sync's skeleton row says source=legacy-unknown",
              by_url.get(unknown, {}).get('source') == 'legacy-unknown', str(by_url.get(unknown, {}).get('source')))
        check('sync leaves the repo_path row alone', by_url[mapped_url].get('article_ids') == 'old',
              str(by_url[mapped_url].get('article_ids')))
        check('sync still refreshes a URL row', by_url[known].get('article_ids') == article_id,
              str(by_url[known].get('article_ids')))

    passed = sum(results)
    print(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: "
          f"{passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


def main():
    # Checked before argparse, which would otherwise demand a command first.
    if '--self-test' in sys.argv[1:]:
        sys.exit(_self_test())

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
        print(f"Repository image paths: {a['distinct_repo_paths_in_docs']} referenced, "
              f"{len(a['repo_paths_not_in_inventory'])} with no row")
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
