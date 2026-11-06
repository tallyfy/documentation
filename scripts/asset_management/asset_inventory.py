#!/usr/bin/env python3
"""
Asset inventory manager for documentation_assets.csv.

Provides CRUD operations and analysis for the master asset inventory.
"""

import csv
import os
import tempfile
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import unquote, quote

from config import config


class AssetInventory:
    """Manager for documentation asset inventory CSV."""

    # The 16 columns the inventory had until tallyfy/documentation#462. Their order is
    # fixed: the migration to the wider schema keeps these 16 fields of every row byte for
    # byte, and `migrate-columns --check` expects them first, in this order.
    LEGACY_COLUMNS = [
        'filename', 'r2_key', 'production_url', 'source_type', 'file_type',
        'file_size', 'file_size_bytes', 'url_exists', 'article_ids',
        'article_count', 'last_modified', 'etag', 'ai_caption_alt',
        'ai_caption_descriptive', 'ai_caption_seo', 'needs_caption'
    ]

    # Who made each image, where in the app it was taken, and when (#462). What each one
    # holds is listed in REFERENCE/claude-md/asset-management.md under "CSV Schema".
    PROVENANCE_COLUMNS = [
        'source', 'repo_path', 'app_screen', 'app_url', 'location_source',
        'captured_at', 'content_sha256', 'markdown_alt', 'source_description',
        'source_ref'
    ]

    # CSV column schema
    COLUMNS = LEGACY_COLUMNS + PROVENANCE_COLUMNS

    # `source` for a row whose origin nobody recorded: every row that existed before #462,
    # and every skeleton row `audit_sync.py sync` adds for a URL it found in the docs.
    SOURCE_UNKNOWN = 'legacy-unknown'

    def __init__(self, csv_path: Optional[Path] = None):
        """
        Initialize inventory manager.

        Args:
            csv_path: Path to CSV file (uses config default if None)
        """
        self.csv_path = csv_path or config.inventory_csv

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Inventory CSV not found: {self.csv_path}")

    def read_header(self) -> List[str]:
        """Return the column names in the file's header row, in file order."""
        with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
            return next(csv.reader(f), [])

    def read_inventory(self) -> List[Dict[str, str]]:
        """
        Read entire inventory from CSV.

        Returns:
            list: List of asset dictionaries
        """
        with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def fieldnames(self) -> List[str]:
        """The columns a write uses: COLUMNS, then any column the file has that COLUMNS lacks.

        A column somebody added to the file by hand, or that a newer script knows and this
        one does not, is kept in its file order after the known ones, so a write never
        drops it (#462).
        """
        known = set(self.COLUMNS)
        return self.COLUMNS + [c for c in self.read_header() if c and c not in known]

    def write_inventory(self, assets: List[Dict[str, str]]):
        """
        Write complete inventory to CSV, atomically.

        Writes to a temp file in the same directory then os.replace()s it over
        the target, so an interrupted write can never leave a torn/half CSV.

        Args:
            assets: List of asset dictionaries to write

        Raises:
            ValueError: a row carries a key that is neither in COLUMNS nor in the
                file's header. Nothing is written and the file is left as it was.
        """
        # Until #462 this wrote only the 16 known columns with extrasaction='ignore', so
        # any other column in the file, and any key a caller misspelt, vanished without a
        # word on the next write. Now the file's own extra columns are written back, and
        # a key with no column raises before the file is touched. A row read from a line
        # with more fields than the header carries them under the key None, and that
        # raises too, rather than dropping the fields.
        fieldnames = self.fieldnames()
        dir_ = self.csv_path.parent
        fd, tmp = tempfile.mkstemp(dir=dir_, prefix='.inv-', suffix='.csv.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                # lineterminator is explicit because csv defaults to CRLF. The
                # committed file is LF, so the default rewrote every one of its
                # ~874 lines on any write and buried a handful of real new rows
                # in a whole-file diff nobody could review.
                writer = csv.DictWriter(f, fieldnames=fieldnames,
                                        extrasaction='raise', lineterminator='\n')
                writer.writeheader()
                writer.writerows(assets)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.csv_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def find_asset(
        self,
        by_url: Optional[str] = None,
        by_r2_key: Optional[str] = None,
        by_filename: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Find an asset by URL, R2 key, or filename.

        Args:
            by_url: Search by production_url (tries normalized URLs)
            by_r2_key: Search by r2_key
            by_filename: Search by filename

        Returns:
            dict: Asset record if found, None otherwise
        """
        assets = self.read_inventory()

        for asset in assets:
            # Search by URL (with normalization)
            if by_url:
                if self._urls_match(asset.get('production_url', ''), by_url):
                    return asset

            # Search by R2 key
            if by_r2_key and asset.get('r2_key') == by_r2_key:
                return asset

            # Search by filename
            if by_filename and asset.get('filename') == by_filename:
                return asset

        return None

    def add_asset(self, asset: Dict[str, str], skip_duplicates: bool = True) -> bool:
        """
        Add a new asset to inventory.

        Args:
            asset: Asset dictionary with required fields
            skip_duplicates: Skip if asset with same r2_key exists

        Returns:
            bool: True if added, False if skipped (duplicate)
        """
        assets = self.read_inventory()

        # Check for duplicates
        if skip_duplicates:
            r2_key = asset.get('r2_key')
            if any(a.get('r2_key') == r2_key for a in assets):
                return False

        # Add default values for missing fields
        asset = self._fill_defaults(asset)

        assets.append(asset)
        self.write_inventory(assets)

        return True

    def update_asset(
        self,
        r2_key: str,
        updates: Dict[str, str],
        create_if_missing: bool = False
    ) -> bool:
        """
        Update an existing asset.

        Args:
            r2_key: R2 key of asset to update
            updates: Dictionary of fields to update
            create_if_missing: Create asset if it doesn't exist

        Returns:
            bool: True if updated/created, False if not found and not created
        """
        assets = self.read_inventory()
        found = False

        for i, asset in enumerate(assets):
            if asset.get('r2_key') == r2_key:
                # Update fields
                assets[i].update(updates)
                found = True
                break

        if not found and create_if_missing:
            # Create new asset
            new_asset = {'r2_key': r2_key}
            new_asset.update(updates)
            assets.append(self._fill_defaults(new_asset))
            found = True

        if found:
            self.write_inventory(assets)

        return found

    def delete_asset(self, r2_key: str) -> bool:
        """
        Delete an asset from inventory.

        Args:
            r2_key: R2 key of asset to delete

        Returns:
            bool: True if deleted, False if not found
        """
        assets = self.read_inventory()
        original_count = len(assets)

        assets = [a for a in assets if a.get('r2_key') != r2_key]

        if len(assets) < original_count:
            self.write_inventory(assets)
            return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get inventory statistics.

        Returns:
            dict: Statistics about assets
        """
        assets = self.read_inventory()

        stats = {
            'total': len(assets),
            'by_type': {},
            'by_source': {},
            'with_captions': 0,
            'needs_captions': 0,
            'orphaned': 0,
            'missing': 0,
            'total_size_bytes': 0
        }

        for asset in assets:
            # By file type
            file_type = asset.get('file_type', 'unknown')
            stats['by_type'][file_type] = stats['by_type'].get(file_type, 0) + 1

            # By source type
            source_type = asset.get('source_type', 'unknown')
            stats['by_source'][source_type] = stats['by_source'].get(source_type, 0) + 1

            # Caption status
            if asset.get('ai_caption_alt'):
                stats['with_captions'] += 1
            elif asset.get('needs_caption') == 'yes':
                stats['needs_captions'] += 1

            # Special cases
            if source_type == 'orphaned':
                stats['orphaned'] += 1
            if source_type == 'missing':
                stats['missing'] += 1

            # Total size
            try:
                size_bytes = int(asset.get('file_size_bytes', 0))
                stats['total_size_bytes'] += size_bytes
            except (ValueError, TypeError):
                pass

        # Calculate total size in human-readable format
        stats['total_size'] = self._format_bytes(stats['total_size_bytes'])

        return stats

    def verify_urls(self, limit: Optional[int] = None) -> Dict[str, List[str]]:
        """
        Verify that asset URLs are accessible.

        Args:
            limit: Maximum number of URLs to check (None = all)

        Returns:
            dict: {'accessible': [...], 'missing': [...]}
        """
        assets = self.read_inventory()
        results = {'accessible': [], 'missing': []}

        count = 0
        for asset in assets:
            if limit and count >= limit:
                break

            url = asset.get('production_url')
            if not url:
                continue

            # Check if URL is accessible
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    results['accessible'].append(url)
                else:
                    results['missing'].append(url)
            except requests.exceptions.RequestException:
                results['missing'].append(url)

            count += 1

        return results

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs match (handles encoding differences)."""
        if url1 == url2:
            return True

        # Try with URL decoding
        if unquote(url1) == unquote(url2):
            return True

        # Try with URL encoding
        if quote(url1, safe='/:') == quote(url2, safe='/:'):
            return True

        return False

    def _fill_defaults(self, asset: Dict[str, str]) -> Dict[str, str]:
        """Fill in default values for missing fields."""
        defaults = {
            'filename': '',
            'r2_key': '',
            'production_url': '',
            'source_type': 'native',
            'file_type': '',
            'file_size': '',
            'file_size_bytes': '0',
            'url_exists': 'False',
            'article_ids': '',
            'article_count': '0',
            'last_modified': '',
            'etag': '',
            'ai_caption_alt': '',
            'ai_caption_descriptive': '',
            'ai_caption_seo': '',
            'needs_caption': 'yes'
        }
        defaults.update({column: '' for column in self.PROVENANCE_COLUMNS})
        # A row nobody says the origin of is legacy-unknown, never blank, so "who made
        # this image" always has an answer a reader can act on (#462).
        defaults['source'] = self.SOURCE_UNKNOWN

        # Merge with provided values
        result = defaults.copy()
        result.update(asset)

        # Auto-populate some fields if possible
        if result['r2_key'] and not result['filename']:
            result['filename'] = Path(result['r2_key']).name

        if result['r2_key'] and not result['file_type']:
            result['file_type'] = Path(result['r2_key']).suffix or 'unknown'

        if result['r2_key'] and not result['production_url']:
            result['production_url'] = f"{config.r2_public_url}/{result['r2_key']}"

        # Set needs_caption based on file type
        if result['file_type'] in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            result['needs_caption'] = 'yes'
        else:
            result['needs_caption'] = 'no'

        return result

    def migration_problems(self) -> List[str]:
        """What stops this file being on the #462 schema. Empty means it is migrated.

        Migrated means the header starts with COLUMNS in order (columns the file adds
        after them are allowed) and every row has a non-empty `source`.
        """
        problems = []
        header = self.read_header()
        if header[:len(self.COLUMNS)] != self.COLUMNS:
            missing = [c for c in self.COLUMNS if c not in header]
            problems.append(
                'header does not start with the known columns in order'
                + (f"; missing: {', '.join(missing)}" if missing else ''))
        blank = [i for i, row in enumerate(self.read_inventory(), start=2)
                 if not (row.get('source') or '').strip()]
        if blank:
            shown = ', '.join(str(n) for n in blank[:10])
            more = f' and {len(blank) - 10} more' if len(blank) > 10 else ''
            problems.append(f'{len(blank)} row(s) with no source, at line(s) {shown}{more}')
        return problems

    def migrate_columns(self) -> Dict[str, int]:
        """Write the #462 header and set source=legacy-unknown on every row that has none.

        A row that already names its source keeps it, so running this twice changes
        nothing. The 16 legacy fields of every row are written back exactly as read.
        """
        assets = self.read_inventory()
        filled = 0
        for asset in assets:
            if not (asset.get('source') or '').strip():
                asset['source'] = self.SOURCE_UNKNOWN
                filled += 1
        self.write_inventory(assets)
        return {'rows': len(assets), 'source_filled': filled}

    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024
        return f"{bytes_value:.1f}TB"


def _self_test() -> int:
    """Prove the writer keeps every column and refuses a key it has no column for (#462).

    Every case works on CSV files it writes in a temporary directory. None reads or writes
    the real documentation_assets.csv. Returns 0 when every case passes, 1 when one fails.
    """
    import hashlib
    import io

    results = []

    def check(name: str, ok: bool, detail: str = ''):
        results.append(ok)
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ''))

    def write_text(path: Path, text: str):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)

    # Values chosen to trip quoting: commas, a doubled quote, non-ASCII text.
    legacy_row = ['a.png', 'tallyfy/pro/a.png', 'https://screenshots.tallyfy.com/tallyfy/pro/a.png',
                  'native', '.png', '1.0KB', '1024', 'True', 'id1,id2', '2', '2024-09-24T02:01:22.452Z',
                  '0123456789abcdef0123456789abcdef', 'Task list, with "Due" column',
                  'Café menu showing steps', 'tallyfy tasks', 'no']
    legacy_line = ('a.png,tallyfy/pro/a.png,https://screenshots.tallyfy.com/tallyfy/pro/a.png,native,.png,'
                   '1.0KB,1024,True,"id1,id2",2,2024-09-24T02:01:22.452Z,0123456789abcdef0123456789abcdef,'
                   '"Task list, with ""Due"" column",Café menu showing steps,tallyfy tasks,no')
    legacy_line_2 = legacy_line.replace('a.png', 'b.png')
    legacy_header = ('filename,r2_key,production_url,source_type,file_type,file_size,file_size_bytes,'
                     'url_exists,article_ids,article_count,last_modified,etag,ai_caption_alt,'
                     'ai_caption_descriptive,ai_caption_seo,needs_caption')
    legacy_text = legacy_header + '\n' + legacy_line + '\n' + legacy_line_2 + '\n'

    # 0. The schema is the 16 old columns, then the 10 from #462, by name and in order.
    check('COLUMNS starts with the 16 legacy columns in order',
          AssetInventory.COLUMNS[:16] == legacy_text.split('\n')[0].split(','))
    check('COLUMNS ends with the 10 provenance columns from #462, in order',
          AssetInventory.COLUMNS[16:] == ['source', 'repo_path', 'app_screen', 'app_url', 'location_source',
                                          'captured_at', 'content_sha256', 'markdown_alt',
                                          'source_description', 'source_ref'],
          str(AssetInventory.COLUMNS[16:]))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1. A full-width file round-trips byte for byte, every column included.
        full = tmp / 'full.csv'
        full_row = legacy_row + ['manual', '/screenshots/launchbrightly/a.png', 'Tasks, list view',
                                 '/tasks', 'inferred', '2026-11-05T00:00:00Z', 'f' * 64,
                                 'Task list', 'A list of tasks', 'recipe-1']
        buf = io.StringIO()
        csv.writer(buf, lineterminator='\n').writerows([AssetInventory.COLUMNS, full_row])
        write_text(full, buf.getvalue())
        inv = AssetInventory(full)
        before = full.read_bytes()
        inv.write_inventory(inv.read_inventory())
        after = full.read_bytes()
        check('a row with all 26 columns round-trips byte for byte', after == before)
        check('the written header is every known column, in order',
              inv.read_header() == AssetInventory.COLUMNS, str(inv.read_header()))

        # 2. A column the script does not know survives a write that changes another field.
        extra = tmp / 'extra.csv'
        write_text(extra, ','.join(AssetInventory.COLUMNS + ['reviewer']) + '\n'
                   + ','.join(['x'] * len(AssetInventory.COLUMNS) + ['Amit']) + '\n')
        inv = AssetInventory(extra)
        inv.update_asset('x', {'ai_caption_alt': 'new alt'})
        rows = inv.read_inventory()
        check('an unknown column stays in the header after a write',
              inv.read_header()[-1:] == ['reviewer'], str(inv.read_header()))
        check('an unknown column keeps its value after a write',
              rows[0].get('reviewer') == 'Amit' and rows[0].get('ai_caption_alt') == 'new alt',
              str(rows[0].get('reviewer')))

        # 3. A key with no column raises and leaves the file exactly as it was.
        before = extra.read_bytes()
        raised = False
        try:
            inv.write_inventory([dict(rows[0], ai_caption_alttext='typo')])
        except ValueError:
            raised = True
        check('a key with no column raises ValueError', raised)
        check('a refused write leaves the file unchanged', extra.read_bytes() == before)
        check('a refused write leaves no temp file behind',
              not any(p.name.startswith('.inv-') for p in tmp.iterdir()))

        # 4. A line with more fields than the header raises rather than dropping them.
        long_line = tmp / 'long.csv'
        write_text(long_line, ','.join(AssetInventory.COLUMNS) + '\n'
                   + ','.join(['y'] * (len(AssetInventory.COLUMNS) + 1)) + '\n')
        inv = AssetInventory(long_line)
        raised = False
        try:
            inv.write_inventory(inv.read_inventory())
        except ValueError:
            raised = True
        check('a row with an extra unnamed field raises', raised)

        # 5. Writes keep LF endings.
        data = full.read_bytes() + extra.read_bytes()
        check('written files hold no carriage return', b'\r' not in data)

        # 6. A new row with no source says legacy-unknown; one that names its source keeps it.
        check("_fill_defaults sets source to 'legacy-unknown'",
              AssetInventory(full)._fill_defaults({'r2_key': 'k.png'}).get('source') == 'legacy-unknown')
        check('_fill_defaults keeps a given source',
              AssetInventory(full)._fill_defaults({'r2_key': 'k.png', 'source': 'manual'})['source'] == 'manual')
        filled = AssetInventory(full)._fill_defaults({'r2_key': 'k.png'})
        check('_fill_defaults gives every column a value',
              all(c in filled for c in AssetInventory.COLUMNS),
              str([c for c in AssetInventory.COLUMNS if c not in filled]))

        # 7. The migration: a 16-column file gains the 10 columns, every row gets
        #    source=legacy-unknown, and each line still starts with its old bytes.
        legacy = tmp / 'legacy.csv'
        write_text(legacy, legacy_text)
        inv = AssetInventory(legacy)
        check('migrate-columns --check reports an unmigrated file', bool(inv.migration_problems()))
        summary = inv.migrate_columns()
        new_lines = legacy.read_text(encoding='utf-8').split('\n')
        suffix = ',' + 'legacy-unknown' + ',' * (len(AssetInventory.PROVENANCE_COLUMNS) - 1)
        check('migration writes the 26-column header', new_lines[0] == ','.join(AssetInventory.COLUMNS))
        check('migration keeps the first 16 fields of every line byte for byte',
              new_lines[1:3] == [legacy_line + suffix, legacy_line_2 + suffix], repr(new_lines[1]))
        check('migration counts every row it filled', summary == {'rows': 2, 'source_filled': 2}, str(summary))
        check('migrate-columns --check passes once migrated', inv.migration_problems() == [],
              str(inv.migration_problems()))
        once = hashlib.sha256(legacy.read_bytes()).hexdigest()
        again = inv.migrate_columns()
        check('a second migration changes no byte',
              hashlib.sha256(legacy.read_bytes()).hexdigest() == once and again['source_filled'] == 0,
              str(again))
        rows = inv.read_inventory()
        rows[0]['source'] = 'manual'
        inv.write_inventory(rows)
        inv.migrate_columns()
        check('a migration keeps a source a row already names',
              inv.read_inventory()[0]['source'] == 'manual')
        blank = tmp / 'blank.csv'
        write_text(blank, ','.join(AssetInventory.COLUMNS) + '\n' + ','.join(['z'] * 16 + [''] * 10) + '\n')
        check('migrate-columns --check reports a row with no source',
              any('no source' in p for p in AssetInventory(blank).migration_problems()))
        short = tmp / 'short.csv'
        write_text(short, ','.join(AssetInventory.COLUMNS[:-1]) + '\n'
                   + ','.join(['z'] * 16 + ['manual'] + [''] * 8) + '\n')
        check('migrate-columns --check reports a header missing a column, even when every row has a source',
              any('source_ref' in p for p in AssetInventory(short).migration_problems()),
              str(AssetInventory(short).migration_problems()))

    passed = sum(results)
    print(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: "
          f"{passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


# CLI interface
if __name__ == '__main__':
    import argparse
    import json
    import sys

    # Checked before argparse, which would otherwise demand an action first.
    if '--self-test' in sys.argv[1:]:
        sys.exit(_self_test())

    parser = argparse.ArgumentParser(description='Manage documentation asset inventory')
    parser.add_argument(
        'action',
        choices=['stats', 'find', 'add', 'update', 'delete', 'verify', 'migrate-columns'],
        help='Action to perform'
    )
    parser.add_argument('--url', help='Asset URL (for find)')
    parser.add_argument('--r2-key', help='R2 key (for find/update/delete)')
    parser.add_argument('--filename', help='Filename (for find)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--limit', type=int, help='Limit for verify action')
    parser.add_argument('--check', action='store_true',
                        help='For migrate-columns: report whether the file is migrated, write nothing '
                             '(exit 0 migrated, 1 not)')
    parser.add_argument('--self-test', action='store_true',
                        help='Run the self-test on temporary files and exit')

    args = parser.parse_args()

    inventory = AssetInventory()

    if args.action == 'migrate-columns':
        if args.check:
            problems = inventory.migration_problems()
            if problems:
                print(f"NOT MIGRATED: {inventory.csv_path}")
                for problem in problems:
                    print(f"  - {problem}")
                sys.exit(1)
            print(f"MIGRATED: {inventory.csv_path} ({len(inventory.read_inventory())} rows)")
            sys.exit(0)
        summary = inventory.migrate_columns()
        print(f"Migrated {inventory.csv_path}: {summary['rows']} rows, "
              f"source set to {AssetInventory.SOURCE_UNKNOWN} on {summary['source_filled']}")
        sys.exit(0)

    if args.action == 'stats':
        stats = inventory.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("📊 Asset Inventory Statistics")
            print("=" * 50)
            print(f"Total assets: {stats['total']}")
            print(f"  With AI captions: {stats['with_captions']}")
            print(f"  Needs captions: {stats['needs_captions']}")
            print(f"  Orphaned: {stats['orphaned']}")
            print(f"  Missing (404): {stats['missing']}")
            print(f"Total size: {stats['total_size']}")
            print(f"\nBy source type:")
            for source, count in stats['by_source'].items():
                print(f"  {source}: {count}")

    elif args.action == 'find':
        asset = inventory.find_asset(
            by_url=args.url,
            by_r2_key=args.r2_key,
            by_filename=args.filename
        )
        if asset:
            if args.json:
                print(json.dumps(asset, indent=2))
            else:
                print("✅ Asset found:")
                for key, value in asset.items():
                    print(f"  {key}: {value}")
        else:
            print("❌ Asset not found")

    elif args.action == 'verify':
        print(f"🔍 Verifying asset URLs{f' (limit: {args.limit})' if args.limit else ''}...")
        results = inventory.verify_urls(limit=args.limit)
        print(f"✅ Accessible: {len(results['accessible'])}")
        print(f"❌ Missing: {len(results['missing'])}")
        if results['missing']:
            print("\nMissing URLs:")
            for url in results['missing'][:10]:  # Show first 10
                print(f"  - {url}")

    else:
        print(f"Action '{args.action}' requires additional implementation")
