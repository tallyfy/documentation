#!/usr/bin/env python3
"""
Asset Management Orchestrator - Main CLI interface.

Coordinates the complete workflow:
  upload → caption generation → inventory update

Usage examples:
  # Upload new screenshot with captions
  python orchestrator.py upload \\
    --file screenshot.png \\
    --key "tallyfy/pro/feature-name.png" \\
    --articles "article-1,article-2"

  # Replace existing screenshot
  python orchestrator.py replace \\
    --file updated.png \\
    --key "tallyfy/pro/existing-feature.png"

  # Generate captions for existing image
  python orchestrator.py caption \\
    --url "https://screenshots.tallyfy.com/image.png"

  # View inventory statistics
  python orchestrator.py stats
"""

import sys
import argparse
import subprocess
import re
from pathlib import Path
from typing import Optional

# Maximum dimension for images (Claude API limit for multi-image requests)
MAX_IMAGE_DIMENSION = 2000

try:
    from r2_uploader import R2Uploader
    from image_captioner import ImageCaptioner, generate_captions_via_claude
    from asset_inventory import AssetInventory
    from config import config
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the asset_management directory")
    sys.exit(1)


class AssetOrchestrator:
    """Orchestrates complete asset management workflow."""

    def __init__(self):
        """Initialize orchestrator with all components."""
        self.uploader = R2Uploader()
        self.captioner = ImageCaptioner()
        self.inventory = AssetInventory()

    def ensure_max_dimension(self, file_path: Path, max_dim: int = MAX_IMAGE_DIMENSION) -> Path:
        """
        Resize image if any dimension exceeds max_dim.

        This prevents Claude API errors when processing multiple images,
        which enforces a 2000px maximum dimension limit.

        Args:
            file_path: Path to the image file
            max_dim: Maximum allowed dimension (default: 2000)

        Returns:
            Path: Original path (file is modified in place if resized)
        """
        # Only process image files
        if file_path.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            return file_path

        # Get image dimensions using 'file' command
        try:
            result = subprocess.run(
                ['file', str(file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Parse "1234 x 5678" from file output
            match = re.search(r'(\d+)\s*x\s*(\d+)', result.stdout)
            if not match:
                print(f"   ⚠️  Could not determine dimensions for {file_path.name}")
                return file_path

            width, height = int(match.group(1)), int(match.group(2))

            if width > max_dim or height > max_dim:
                print(f"   ⚠️  Image exceeds {max_dim}px limit: {width}x{height}")
                print(f"   🔄 Auto-resizing to max {max_dim}px...")

                # Use sips (macOS) to resize
                subprocess.run(
                    ['sips', '--resampleHeightWidthMax', str(max_dim), str(file_path)],
                    capture_output=True,
                    timeout=30
                )

                # Verify new dimensions
                result2 = subprocess.run(['file', str(file_path)], capture_output=True, text=True)
                match2 = re.search(r'(\d+)\s*x\s*(\d+)', result2.stdout)
                if match2:
                    new_w, new_h = int(match2.group(1)), int(match2.group(2))
                    print(f"   ✅ Resized to: {new_w}x{new_h}")

        except subprocess.TimeoutExpired:
            print(f"   ⚠️  Timeout checking image dimensions")
        except Exception as e:
            print(f"   ⚠️  Error checking dimensions: {e}")

        return file_path

    def upload_asset(
        self,
        file_path: str | Path,
        r2_key: str,
        article_ids: Optional[str] = None,
        skip_captions: bool = False,
        overwrite: bool = True
    ) -> dict:
        """
        Complete upload workflow: upload → caption → inventory.

        Args:
            file_path: Local file to upload
            r2_key: R2 storage key
            article_ids: Comma-separated article IDs
            skip_captions: Skip AI caption generation
            overwrite: Allow overwriting existing files

        Returns:
            dict: Result with success status and details
        """
        print(f"📤 Starting upload workflow for: {Path(file_path).name}")
        print(f"   R2 key: {r2_key}")

        # Step 0: Auto-resize if needed (prevents Claude API 2000px limit errors)
        file_path_obj = Path(file_path)
        self.ensure_max_dimension(file_path_obj)

        # Step 1: Upload to R2
        print("\n[1/3] Uploading to R2...")
        upload_result = self.uploader.upload_file(file_path, r2_key, overwrite=overwrite)

        if not upload_result['success']:
            return {
                'success': False,
                'step': 'upload',
                'error': upload_result.get('error')
            }

        print(f"   ✅ Uploaded: {upload_result['url']}")
        print(f"   Size: {upload_result['size']:,} bytes")

        # Step 2: Generate captions (if not skipped)
        captions = {}
        if not skip_captions:
            print("\n[2/3] Generating AI captions...")
            print("   ⚠️  This requires Claude Code vision capabilities")
            print("   ⚠️  Captions will need to be generated separately if not in Claude Code session")

            # This would be filled in by Claude Code when executing
            captions = {
                'ai_caption_alt': '',
                'ai_caption_descriptive': '',
                'ai_caption_seo': ''
            }
        else:
            print("\n[2/3] Skipping caption generation (--skip-captions)")

        # Step 3: Update inventory
        print("\n[3/3] Updating inventory...")

        # Prepare asset record (file_path_obj already set at step 0)
        asset_data = {
            'filename': file_path_obj.name,
            'r2_key': r2_key,
            'production_url': upload_result['url'],
            'source_type': 'native',
            'file_type': file_path_obj.suffix,
            'file_size': self._format_bytes(upload_result['size']),
            'file_size_bytes': str(upload_result['size']),
            'url_exists': 'True',
            'article_ids': article_ids or '',
            'article_count': str(len(article_ids.split(',')) if article_ids else 0),
            'last_modified': upload_result.get('last_modified', ''),
            'etag': upload_result.get('etag', ''),
            'needs_caption': 'yes' if file_path_obj.suffix in ['.png', '.jpg', '.jpeg'] else 'no'
        }

        # Add captions if generated
        asset_data.update(captions)

        # Update inventory (create or update)
        self.inventory.update_asset(r2_key, asset_data, create_if_missing=True)

        print(f"   ✅ Inventory updated")

        return {
            'success': True,
            'url': upload_result['url'],
            'r2_key': r2_key,
            'size': upload_result['size'],
            'captions_generated': not skip_captions
        }

    def replace_asset(
        self,
        file_path: str | Path,
        r2_key: str,
        regenerate_captions: bool = True
    ) -> dict:
        """
        Replace an existing asset.

        Args:
            file_path: New file to upload
            r2_key: Existing R2 key to replace
            regenerate_captions: Generate new captions for updated file

        Returns:
            dict: Result with success status
        """
        print(f"🔄 Replacing asset: {r2_key}")

        # Check if asset exists in inventory
        existing = self.inventory.find_asset(by_r2_key=r2_key)
        if not existing:
            print(f"   ⚠️  Asset not found in inventory (will create new)")

        # Upload new version (reuse article_ids if available)
        article_ids = existing.get('article_ids', '') if existing else None

        return self.upload_asset(
            file_path,
            r2_key,
            article_ids=article_ids,
            skip_captions=not regenerate_captions,
            overwrite=True
        )

    def generate_captions_only(self, url: str) -> dict:
        """
        Generate captions for an existing image (URL).

        Args:
            url: Image URL to generate captions for

        Returns:
            dict: Captions generated
        """
        print(f"🎨 Generating captions for: {url}")
        print("   ⚠️  This requires Claude Code execution context")

        # Extract r2_key from URL
        r2_key = url.replace(config.r2_public_url + '/', '')

        # Find in inventory
        asset = self.inventory.find_asset(by_url=url)
        if not asset:
            return {
                'success': False,
                'error': 'Asset not found in inventory'
            }

        print(f"   Found in inventory: {asset['filename']}")

        # Generate captions (placeholder - needs Claude Code)
        captions = self.captioner.generate_captions(url)

        # Update inventory with captions
        self.inventory.update_asset(r2_key, captions)

        print("   ✅ Captions generated and inventory updated")

        return {
            'success': True,
            'captions': captions
        }

    def show_stats(self) -> dict:
        """Display inventory statistics."""
        stats = self.inventory.get_stats()

        print("\n📊 Asset Inventory Statistics")
        print("=" * 60)
        print(f"Total assets: {stats['total']}")
        print(f"  ✓ With AI captions: {stats['with_captions']}")
        print(f"  ⚠ Needs captions: {stats['needs_captions']}")
        print(f"  🔗 Orphaned (not referenced): {stats['orphaned']}")
        print(f"  ❌ Missing (404): {stats['missing']}")
        print(f"\nTotal size: {stats['total_size']}")

        print(f"\nBy source type:")
        for source, count in sorted(stats['by_source'].items()):
            print(f"  {source}: {count}")

        print(f"\nBy file type:")
        for file_type, count in sorted(stats['by_type'].items()):
            print(f"  {file_type}: {count}")

        return stats

    @staticmethod
    def _format_bytes(bytes_value: int) -> str:
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024
        return f"{bytes_value:.1f}TB"


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Documentation Asset Management Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload new screenshot with auto-captions
  python orchestrator.py upload \\
    --file ~/Desktop/screenshot.png \\
    --key "tallyfy/pro/feature-name.png" \\
    --articles "pro-features,pro-guide"

  # Replace existing screenshot
  python orchestrator.py replace \\
    --file ~/Desktop/updated.png \\
    --key "tallyfy/pro/existing-feature.png"

  # Generate captions only
  python orchestrator.py caption \\
    --url "https://screenshots.tallyfy.com/tallyfy/pro/image.png"

  # View statistics
  python orchestrator.py stats

  # Verify configuration
  python orchestrator.py verify
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload new asset')
    upload_parser.add_argument('--file', required=True, help='File to upload')
    upload_parser.add_argument('--key', required=True, help='R2 storage key')
    upload_parser.add_argument('--articles', help='Comma-separated article IDs')
    upload_parser.add_argument('--skip-captions', action='store_true', help='Skip caption generation')
    upload_parser.add_argument('--no-overwrite', action='store_true', help='Fail if file exists')

    # Replace command
    replace_parser = subparsers.add_parser('replace', help='Replace existing asset')
    replace_parser.add_argument('--file', required=True, help='New file to upload')
    replace_parser.add_argument('--key', required=True, help='Existing R2 key')
    replace_parser.add_argument('--no-captions', action='store_true', help='Skip caption regeneration')

    # Caption command
    caption_parser = subparsers.add_parser('caption', help='Generate captions for existing image')
    caption_parser.add_argument('--url', required=True, help='Image URL')

    # Stats command
    subparsers.add_parser('stats', help='Show inventory statistics')

    # Verify command
    subparsers.add_parser('verify', help='Verify configuration')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Verify configuration first
    if args.command == 'verify':
        print("🔍 Verifying configuration...")
        config.print_config()

        is_valid, missing = config.validate()
        if is_valid:
            print("\n✅ Configuration is valid and complete")
            sys.exit(0)
        else:
            print("\n❌ Configuration is incomplete. Missing:")
            for field in missing:
                print(f"  - {field}")
            sys.exit(1)

    # Initialize orchestrator
    try:
        orchestrator = AssetOrchestrator()
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        print("\nRun 'python orchestrator.py verify' to check configuration")
        sys.exit(1)

    # Execute command
    try:
        if args.command == 'upload':
            result = orchestrator.upload_asset(
                args.file,
                args.key,
                article_ids=args.articles,
                skip_captions=args.skip_captions,
                overwrite=not args.no_overwrite
            )

            if result['success']:
                print(f"\n✅ Upload complete!")
                print(f"   URL: {result['url']}")
                sys.exit(0)
            else:
                print(f"\n❌ Upload failed: {result.get('error')}")
                sys.exit(1)

        elif args.command == 'replace':
            result = orchestrator.replace_asset(
                args.file,
                args.key,
                regenerate_captions=not args.no_captions
            )

            if result['success']:
                print(f"\n✅ Replacement complete!")
                print(f"   URL: {result['url']}")
                sys.exit(0)
            else:
                print(f"\n❌ Replacement failed: {result.get('error')}")
                sys.exit(1)

        elif args.command == 'caption':
            result = orchestrator.generate_captions_only(args.url)

            if result['success']:
                print(f"\n✅ Captions generated!")
                sys.exit(0)
            else:
                print(f"\n❌ Caption generation failed: {result.get('error')}")
                sys.exit(1)

        elif args.command == 'stats':
            orchestrator.show_stats()
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
