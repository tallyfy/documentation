#!/usr/bin/env python3
"""
Asset inventory manager for documentation_assets.csv.

Provides CRUD operations and analysis for the master asset inventory.
"""

import csv
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import unquote, quote

from config import config


class AssetInventory:
    """Manager for documentation asset inventory CSV."""

    # CSV column schema
    COLUMNS = [
        'filename', 'r2_key', 'production_url', 'source_type', 'file_type',
        'file_size', 'file_size_bytes', 'url_exists', 'article_ids',
        'article_count', 'last_modified', 'etag', 'ai_caption_alt',
        'ai_caption_descriptive', 'ai_caption_seo', 'needs_caption'
    ]

    def __init__(self, csv_path: Optional[Path] = None):
        """
        Initialize inventory manager.

        Args:
            csv_path: Path to CSV file (uses config default if None)
        """
        self.csv_path = csv_path or config.inventory_csv

        if not self.csv_path.exists():
            raise FileNotFoundError(f"Inventory CSV not found: {self.csv_path}")

    def read_inventory(self) -> List[Dict[str, str]]:
        """
        Read entire inventory from CSV.

        Returns:
            list: List of asset dictionaries
        """
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def write_inventory(self, assets: List[Dict[str, str]]):
        """
        Write complete inventory to CSV.

        Args:
            assets: List of asset dictionaries to write
        """
        with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            writer.writeheader()
            writer.writerows(assets)

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

    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024
        return f"{bytes_value:.1f}TB"


# CLI interface
if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Manage documentation asset inventory')
    parser.add_argument(
        'action',
        choices=['stats', 'find', 'add', 'update', 'delete', 'verify'],
        help='Action to perform'
    )
    parser.add_argument('--url', help='Asset URL (for find)')
    parser.add_argument('--r2-key', help='R2 key (for find/update/delete)')
    parser.add_argument('--filename', help='Filename (for find)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--limit', type=int, help='Limit for verify action')

    args = parser.parse_args()

    inventory = AssetInventory()

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
