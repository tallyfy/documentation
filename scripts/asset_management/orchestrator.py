#!/usr/bin/env python3
"""
Asset Management Orchestrator - Main CLI interface.

Coordinates the complete workflow:
  upload → caption generation → inventory update

Captioning is deliberately TWO PHASE. `upload` puts the image on R2 and inventories it; it
does not caption. `caption` writes caption text, and only works inside a Claude Code session,
which is what can actually read the image. Neither command pretends to have done the other's
job, which they both used to do (tallyfy/documentation#117).

Usage examples:
  # Upload a new screenshot (inventoried, NOT captioned)
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
import hashlib
import shutil
import subprocess
import re
import tempfile
from pathlib import Path
from typing import Optional

# Maximum dimension for images (Claude API limit for multi-image requests)
MAX_IMAGE_DIMENSION = 2000

# image_captioner.generate_captions() returns alt_text/descriptive/seo. The CSV columns are
# ai_caption_*. asset_inventory writes with extrasaction='ignore', so handing the generator's
# keys straight to it drops all three SILENTLY and the caller sees success. This map is the
# single place that translation happens; keep it in step with both sides.
# Dated 2026-11-05 (#462): the writer now uses extrasaction='raise', so such keys stop the
# write with an error instead of vanishing. The map is still where the translation happens.
CAPTION_COLUMNS = {
    'alt_text': 'ai_caption_alt',
    'descriptive': 'ai_caption_descriptive',
    'seo': 'ai_caption_seo',
}

# image_captioner._generate_single_caption is a documented stub that returns this shape when
# it is called outside a Claude Code session. Treat it as "no caption", never as text.
PLACEHOLDER_RE = re.compile(r'^\s*\[CAPTION NEEDED\b', re.IGNORECASE)


def is_placeholder(value: str) -> bool:
    """True when a caption is the stub's placeholder rather than real text."""
    return bool(PLACEHOLDER_RE.match(value or ''))


IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

# R2 keys under this prefix hold LaunchBrightly's screenshots. The pipeline uploads those from
# screenshots/launchbrightly/ in this repository and owns their inventory rows, so a hand
# upload there would be overwritten or would contradict the row (#462).
RESERVED_KEY_PREFIX = 'launchbrightly/'


def reserved_key_error(r2_key: str) -> Optional[str]:
    """The reason a key may not be uploaded by hand, or None when it may."""
    if (r2_key or '').strip().lstrip('/').lower().startswith(RESERVED_KEY_PREFIX):
        return (f"refusing to upload to {r2_key!r}: keys under {RESERVED_KEY_PREFIX} are reserved "
                f"for LaunchBrightly screenshots, which the pipeline uploads from "
                f"screenshots/launchbrightly/ in this repository. Use another key.")
    return None


def sha256_of(path: Path) -> str:
    """SHA-256 of a file's bytes, as lowercase hex."""
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def image_changed(previous: dict, new_sha256: str, new_etag: str) -> Optional[bool]:
    """Whether the bytes now on R2 differ from the ones the row described.

    Compares content_sha256 when the row has one, otherwise the R2 etag. Returns None when
    the row has neither, because then nothing can tell a new image from the same one.
    """
    old_sha = (previous.get('content_sha256') or '').strip().lower()
    if old_sha:
        return old_sha != new_sha256.lower()
    old_etag = (previous.get('etag') or '').strip().strip('"').lower()
    etag = (new_etag or '').strip().strip('"').lower()
    if old_etag and etag:
        return old_etag != etag
    return None

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
        Return a path whose image fits inside max_dim on both sides.

        The cap exists for the caption phase: Claude enforces 2000px on a
        multi-image request. It is not an R2 or a rendering limit.

        This used to hand `sips` the caller's own file. `sips` rewrites in
        place, so uploading a tall screenshot silently destroyed the local
        original, and there was then nothing left to re-upload at full size.
        A 1000x3419 email capture came back as 585x2000 and its text was no
        longer readable. Resize a COPY instead, and leave the caller's file
        exactly as it was found.

        Args:
            file_path: Path to the image file
            max_dim: Maximum allowed dimension (default: 2000)

        Returns:
            Path: the original path when no resize was needed, otherwise a
            path to a resized temporary copy. The original is never touched.
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
                print(f"   🔄 Auto-resizing a COPY to max {max_dim}px (original untouched)...")

                # sips rewrites in place, so give it a throwaway copy.
                scratch = Path(tempfile.mkdtemp(prefix='asset-resize-')) / file_path.name
                shutil.copy2(file_path, scratch)

                # Use sips (macOS) to resize
                subprocess.run(
                    ['sips', '--resampleHeightWidthMax', str(max_dim), str(scratch)],
                    capture_output=True,
                    timeout=30
                )

                # Verify new dimensions
                result2 = subprocess.run(['file', str(scratch)], capture_output=True, text=True)
                match2 = re.search(r'(\d+)\s*x\s*(\d+)', result2.stdout)
                if match2:
                    new_w, new_h = int(match2.group(1)), int(match2.group(2))
                    print(f"   ✅ Resized copy: {new_w}x{new_h}")

                return scratch

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
        overwrite: bool = True,
        resize: bool = True,
        keep_captions: bool = False
    ) -> dict:
        """
        Complete upload workflow: upload → caption → inventory.

        Args:
            file_path: Local file to upload
            r2_key: R2 storage key
            article_ids: Comma-separated article IDs
            skip_captions: Skip AI caption generation
            overwrite: Allow overwriting existing files
            resize: Shrink an over-2000px image before upload. Pass False for
                    an image whose full height is the point, such as a tall
                    email render, where the shrink makes the text unreadable.
            keep_captions: When the key already has a row, keep its captions even
                    if the new bytes differ (a cosmetic swap). Without it, changed
                    bytes clear the three captions and queue the image again.

        Returns:
            dict: Result with success status and details
        """
        print(f"📤 Starting upload workflow for: {Path(file_path).name}")
        print(f"   R2 key: {r2_key}")

        refusal = reserved_key_error(r2_key)
        if refusal:
            print(f"   ❌ {refusal}")
            return {'success': False, 'step': 'validate', 'error': refusal}

        # Step 0: Auto-resize if needed (prevents Claude API 2000px limit errors).
        # ensure_max_dimension returns a temp copy when it resizes, so upload what
        # it hands back rather than the caller's path.
        file_path_obj = Path(file_path)
        upload_path = self.ensure_max_dimension(file_path_obj) if resize else file_path_obj
        # Hash what goes to R2, which is the resized copy when there is one, so
        # content_sha256 always describes the bytes the public URL serves.
        content_sha256 = sha256_of(upload_path)
        # The row as it stood before this upload, to tell a new image from the same one.
        previous = self.inventory.find_asset(by_r2_key=r2_key)

        # Step 1: Upload to R2
        print("\n[1/3] Uploading to R2...")
        upload_result = self.uploader.upload_file(upload_path, r2_key, overwrite=overwrite)

        if not upload_result['success']:
            return {
                'success': False,
                'step': 'upload',
                'error': upload_result.get('error')
            }

        print(f"   ✅ Uploaded: {upload_result['url']}")
        print(f"   Size: {upload_result['size']:,} bytes")

        # Step 2: Captions.
        #
        # This step does NOT generate captions and never has. Captioning is a two-phase
        # workflow: this script inventories the image, then a Claude Code session reads it
        # with native vision and writes the text back. That design is fine. What was not fine
        # is that this block used to write three EMPTY strings into the caption columns while
        # printing "Generating AI captions...", so a replace of an already-captioned asset
        # silently blanked its captions, and the caller was told captions had been generated.
        # See tallyfy/documentation#117.
        captions = {}
        captions_pending = False
        if not skip_captions:
            captions_pending = True
            print("\n[2/3] Captions: NOT generated here.")
            print("   This command inventories the image. It does not caption it.")
            print("   Caption it in a Claude Code session, which has the vision capability:")
            print(f"     python3 orchestrator.py caption --url {upload_result['url']}")
        else:
            print("\n[2/3] Skipping captions (--skip-captions)")

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
            'needs_caption': 'yes' if file_path_obj.suffix in ['.png', '.jpg', '.jpeg'] else 'no',
            # Uploaded by a person through this script (#462).
            'source': 'manual',
            'content_sha256': content_sha256,
        }

        # Add captions if generated
        asset_data.update(captions)

        # The key already had a row, so this upload replaced an image. Until #462 the old
        # captions stayed on whatever the new bytes show, and nothing queued it again.
        captions_cleared = False
        if previous:
            changed = image_changed(previous, content_sha256, upload_result.get('etag', ''))
            if keep_captions or changed is False:
                # Same image, or the caller says the captions still fit: leave the three
                # captions and the needs_caption flag exactly as the row had them.
                del asset_data['needs_caption']
                reason = '--keep-captions' if keep_captions else 'the bytes are unchanged'
                print(f"   Captions kept ({reason}).")
            else:
                if changed is None:
                    print("   ⚠️  The row has no content_sha256 and no etag, so it cannot tell whether")
                    print("      the image changed. Treating it as changed.")
                for column in CAPTION_COLUMNS.values():
                    asset_data[column] = ''
                asset_data['needs_caption'] = 'yes' if file_path_obj.suffix.lower() in IMAGE_SUFFIXES else 'no'
                captions_cleared = True

        # Update inventory (create or update)
        self.inventory.update_asset(r2_key, asset_data, create_if_missing=True)

        print(f"   ✅ Inventory updated")

        if captions_cleared:
            print("   ⚠️  The image changed, so its three captions were cleared and it is queued")
            print("      for captioning again. Caption it in a Claude Code session:")
            print(f"     python3 orchestrator.py caption --url {upload_result['url']}")
            print("      (Pass --keep-captions next time if a swap leaves the captions true.)")
        elif captions_pending and not (previous and (previous.get('ai_caption_alt') or '').strip()):
            print("   ⚠️  This asset has NO captions yet. Its alt text will be empty until you")
            print("      run the caption command above.")

        return {
            'success': True,
            'url': upload_result['url'],
            'r2_key': r2_key,
            'size': upload_result['size'],
            # Always False: this method does not generate captions. It reported
            # `not skip_captions` here for as long as it existed, which is how an
            # uncaptioned upload read as a captioned one.
            'captions_generated': False,
            'captions_pending': captions_pending,
            'captions_cleared': captions_cleared,
            'content_sha256': content_sha256,
        }

    def replace_asset(
        self,
        file_path: str | Path,
        r2_key: str,
        regenerate_captions: bool = True,
        resize: bool = True,
        keep_captions: bool = False
    ) -> dict:
        """
        Replace an existing asset.

        When the new bytes differ from the old ones, the three captions are cleared and
        needs_caption is set to yes, so `audit_sync.py worklist` offers the image again.
        keep_captions keeps them for a cosmetic swap.

        Args:
            file_path: New file to upload
            r2_key: Existing R2 key to replace
            regenerate_captions: Generate new captions for updated file
            keep_captions: Keep the existing captions even if the bytes changed

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
            overwrite=True,
            resize=resize,
            keep_captions=keep_captions
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

        captions = self.captioner.generate_captions(url)

        # The generator returns alt_text/descriptive/seo; the CSV columns are
        # ai_caption_alt/ai_caption_descriptive/ai_caption_seo. asset_inventory writes with
        # extrasaction='ignore', so passing the generator's keys straight through wrote
        # NOTHING and reported success. Translate explicitly (tallyfy/documentation#117).
        # Since #462 the writer raises on such keys instead (see CAPTION_COLUMNS above).
        row = {
            CAPTION_COLUMNS[key]: value
            for key, value in captions.items()
            if key in CAPTION_COLUMNS
        }

        unmapped = sorted(set(captions) - set(CAPTION_COLUMNS))
        if unmapped:
            return {
                'success': False,
                'error': (f"captioner returned unknown key(s) {unmapped}; refusing to write. "
                          f"Expected any of {sorted(CAPTION_COLUMNS)}.")
            }

        # A stub or a failed generation yields placeholders or blanks. Writing those over a
        # real caption is worse than doing nothing, and reporting success for it is how the
        # gap stayed invisible.
        usable = {k: v for k, v in row.items() if v and not is_placeholder(v)}
        if not usable:
            return {
                'success': False,
                'error': ("no usable captions were produced. This command only works inside a "
                          "Claude Code session, where the image can be read with native vision. "
                          "Nothing was written to the inventory.")
            }

        self.inventory.update_asset(r2_key, usable)

        written = ', '.join(sorted(usable))
        skipped = sorted(set(row) - set(usable))
        print(f"   ✅ Wrote {len(usable)} caption(s) to the inventory: {written}")
        if skipped:
            print(f"   ⚠️  Left unchanged (empty or placeholder): {', '.join(skipped)}")

        return {
            'success': True,
            'captions': usable,
            'skipped': skipped,
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


class _FakeUploader:
    """Stands in for R2Uploader in the self-test. It reads the file it is handed and records
    the key and bytes, and never makes a network call or reads a credential."""

    def __init__(self):
        self.calls = []

    def upload_file(self, file_path, r2_key, overwrite=True, content_type=None):
        data = Path(file_path).read_bytes()
        self.calls.append({'r2_key': r2_key, 'bytes': data})
        return {
            'success': True,
            'url': f'{config.r2_public_url}/{r2_key}',
            'r2_key': r2_key,
            # R2 gives a single PUT the MD5 of its bytes as the etag.
            'etag': hashlib.md5(data).hexdigest(),
            'size': len(data),
            'last_modified': '2026-11-05T00:00:00+00:00',
        }


def _self_test() -> int:
    """Prove upload and replace record provenance and re-queue a changed image (#462).

    Runs AssetOrchestrator against a fake uploader and a CSV in a temporary directory, so
    it needs no credentials and never uploads anything or touches documentation_assets.csv.
    Returns 0 when every case passes, 1 when one fails.
    """
    import contextlib
    import csv
    import io
    from audit_sync import _row_needs_caption

    results = []

    def check(name, ok, detail=''):
        results.append(ok)
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ''))

    old_bytes = b'\x89PNG\r\n\x1a\n old image'
    new_bytes = b'\x89PNG\r\n\x1a\n new image'
    captions = {'ai_caption_alt': 'Old alt', 'ai_caption_descriptive': 'Old descriptive',
                'ai_caption_seo': 'Old seo'}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old_file, new_file = tmp / 'old.png', tmp / 'new.png'
        old_file.write_bytes(old_bytes)
        new_file.write_bytes(new_bytes)
        csv_path = tmp / 'inventory.csv'

        def fresh(rows):
            """A new orchestrator over a CSV holding exactly these rows."""
            # Rows are written as given, not through _fill_defaults, which would reset
            # needs_caption from the file type and hide what the code under test does.
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=AssetInventory.COLUMNS, lineterminator='\n')
                writer.writeheader()
                writer.writerows(dict({c: '' for c in AssetInventory.COLUMNS}, **r) for r in rows)
            orch = AssetOrchestrator.__new__(AssetOrchestrator)
            orch.uploader = _FakeUploader()
            orch.captioner = None
            orch.inventory = AssetInventory(csv_path)
            return orch

        def run(fn, *args, **kwargs):
            with contextlib.redirect_stdout(io.StringIO()):
                return fn(*args, **kwargs)

        def row(orch, key):
            return orch.inventory.find_asset(by_r2_key=key) or {}

        captioned_row = dict(captions, r2_key='tallyfy/pro/a.png', needs_caption='no',
                             article_ids='id1,id2', article_count='2',
                             content_sha256=sha256_of(old_file))

        # 1. A new upload says it was made by hand and records the hash of what R2 got.
        orch = fresh([])
        result = run(orch.upload_asset, new_file, 'tallyfy/pro/new.png', resize=False)
        r = row(orch, 'tallyfy/pro/new.png')
        check('upload records source=manual', r.get('source') == 'manual', str(r.get('source')))
        check('upload records content_sha256 of the bytes sent to R2',
              len(orch.uploader.calls) == 1
              and r.get('content_sha256') == hashlib.sha256(orch.uploader.calls[0]['bytes']).hexdigest()
              == result.get('content_sha256'), str(r.get('content_sha256')))

        # 2. A resized copy is what goes up, so it is what gets hashed.
        orch = fresh([])
        resized = tmp / 'resized.png'
        resized.write_bytes(b'\x89PNG\r\n\x1a\n resized copy')
        orch.ensure_max_dimension = lambda path: resized
        run(orch.upload_asset, new_file, 'tallyfy/pro/big.png')
        check('content_sha256 is the hash of the resized copy that was uploaded',
              row(orch, 'tallyfy/pro/big.png').get('content_sha256') == sha256_of(resized))

        # 3. Keys under launchbrightly/ are refused before anything is uploaded or written.
        for key in ('launchbrightly/x.png', '/LaunchBrightly/x.png'):
            orch = fresh([])
            before = csv_path.read_bytes()
            result = run(orch.upload_asset, new_file, key, resize=False)
            check(f'upload refuses {key!r} without uploading or writing',
                  result.get('success') is False and orch.uploader.calls == []
                  and csv_path.read_bytes() == before, str(result))
        orch = fresh([])
        result = run(orch.replace_asset, new_file, 'launchbrightly/x.png', resize=False)
        check('replace refuses a launchbrightly/ key too',
              result.get('success') is False and orch.uploader.calls == [], str(result))
        orch = fresh([])
        result = run(orch.upload_asset, new_file, 'tallyfy/launchbrightly/x.png', resize=False)
        check('a key that only contains launchbrightly/ further in is allowed',
              result.get('success') is True and len(orch.uploader.calls) == 1, str(result))

        # 4. Replacing with different bytes clears the captions and queues the image again.
        orch = fresh([captioned_row])
        result = run(orch.replace_asset, new_file, 'tallyfy/pro/a.png', resize=False)
        r = row(orch, 'tallyfy/pro/a.png')
        check('replace with new bytes clears all three captions',
              all(r.get(c) == '' for c in CAPTION_COLUMNS.values()), str({c: r.get(c) for c in captions}))
        check('replace with new bytes sets needs_caption=yes', r.get('needs_caption') == 'yes')
        check('replace with new bytes puts the image back on the caption worklist', _row_needs_caption(r))
        check('replace with new bytes stores the new hash', r.get('content_sha256') == sha256_of(new_file))
        check('replace keeps article_ids', r.get('article_ids') == 'id1,id2')
        check('replace reports the clear', result.get('captions_cleared') is True)

        # 5. Replacing with the same bytes keeps everything.
        orch = fresh([captioned_row])
        result = run(orch.replace_asset, old_file, 'tallyfy/pro/a.png', resize=False)
        r = row(orch, 'tallyfy/pro/a.png')
        check('replace with the same bytes keeps the captions',
              all(r.get(c) == v for c, v in captions.items()), str({c: r.get(c) for c in captions}))
        check('replace with the same bytes keeps needs_caption', r.get('needs_caption') == 'no')
        check('replace with the same bytes reports no clear', result.get('captions_cleared') is False)

        # 6. --keep-captions keeps them through a real change.
        orch = fresh([captioned_row])
        run(orch.replace_asset, new_file, 'tallyfy/pro/a.png', resize=False, keep_captions=True)
        r = row(orch, 'tallyfy/pro/a.png')
        check('--keep-captions keeps the captions when the bytes change',
              all(r.get(c) == v for c, v in captions.items()) and r.get('needs_caption') == 'no')
        check('--keep-captions still stores the new hash', r.get('content_sha256') == sha256_of(new_file))

        # 7. A row from before #462 has no hash, so the etag decides.
        legacy = dict(captioned_row, content_sha256='', etag=hashlib.md5(old_bytes).hexdigest())
        orch = fresh([legacy])
        run(orch.replace_asset, old_file, 'tallyfy/pro/a.png', resize=False)
        check('no stored hash and the same etag keeps the captions',
              row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == 'Old alt')
        orch = fresh([legacy])
        run(orch.replace_asset, new_file, 'tallyfy/pro/a.png', resize=False)
        check('no stored hash and a different etag clears the captions',
              row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == '')

        # 8. Nothing to compare: treat it as changed.
        orch = fresh([dict(captioned_row, content_sha256='', etag='')])
        run(orch.replace_asset, old_file, 'tallyfy/pro/a.png', resize=False)
        check('no hash and no etag clears the captions',
              row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == '')

        # 9. upload over a key that already has a row is a replace too.
        orch = fresh([captioned_row])
        run(orch.upload_asset, new_file, 'tallyfy/pro/a.png', resize=False)
        check('upload over an existing key with new bytes clears the captions',
              row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == '')

        # 10. The command line passes the flags through. main() builds its orchestrator by
        #     name, so it is pointed at the fake one for these runs and restored after.
        def cli(argv, orch):
            saved_argv, saved_cls = sys.argv, globals()['AssetOrchestrator']
            globals()['AssetOrchestrator'] = lambda: orch
            sys.argv = ['orchestrator.py'] + argv
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
            except SystemExit as exc:
                return exc.code
            finally:
                sys.argv = saved_argv
                globals()['AssetOrchestrator'] = saved_cls
            return None

        orch = fresh([captioned_row])
        code = cli(['replace', '--file', str(new_file), '--key', 'tallyfy/pro/a.png',
                    '--no-resize', '--keep-captions'], orch)
        check('replace --keep-captions on the command line keeps the captions',
              code == 0 and row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == 'Old alt', str(code))
        orch = fresh([captioned_row])
        code = cli(['upload', '--file', str(new_file), '--key', 'tallyfy/pro/a.png',
                    '--no-resize', '--keep-captions'], orch)
        check('upload --keep-captions on the command line keeps the captions',
              code == 0 and row(orch, 'tallyfy/pro/a.png').get('ai_caption_alt') == 'Old alt', str(code))
        orch = fresh([])
        code = cli(['upload', '--file', str(new_file), '--key', 'launchbrightly/x.png', '--no-resize'], orch)
        check('upload of a launchbrightly/ key on the command line exits 1 and uploads nothing',
              code == 1 and orch.uploader.calls == [], str(code))

    passed = sum(results)
    print(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: "
          f"{passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


def main():
    """Main CLI entry point."""
    # Checked before argparse, which would otherwise demand a command first.
    if '--self-test' in sys.argv[1:]:
        sys.exit(_self_test())

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
    upload_parser.add_argument('--no-resize', action='store_true',
                               help='Upload at full size even above 2000px (tall email renders)')
    upload_parser.add_argument('--keep-captions', action='store_true',
                               help='If the key already has captions, keep them even when the bytes change')

    # Replace command
    replace_parser = subparsers.add_parser('replace', help='Replace existing asset')
    replace_parser.add_argument('--file', required=True, help='New file to upload')
    replace_parser.add_argument('--key', required=True, help='Existing R2 key')
    replace_parser.add_argument('--no-captions', action='store_true', help='Skip caption regeneration')
    replace_parser.add_argument('--no-resize', action='store_true',
                                help='Upload at full size even above 2000px (tall email renders)')
    replace_parser.add_argument('--keep-captions', action='store_true',
                                help='Keep the captions even when the bytes change (a cosmetic swap)')

    # Caption command
    caption_parser = subparsers.add_parser('caption', help='Generate captions for existing image')
    caption_parser.add_argument('--url', required=True, help='Image URL')

    # Stats command
    subparsers.add_parser('stats', help='Show inventory statistics')

    # Verify command
    subparsers.add_parser('verify', help='Verify configuration')

    # Audit command (read-only; no R2 credentials needed)
    audit_parser = subparsers.add_parser('audit', help='Read-only audit: referenced-not-in-inventory, dead, orphaned, uncaptioned')
    audit_parser.add_argument('--out', help='Write markdown report to this path')

    # Sync command (safe-auto; no R2 credentials needed)
    sync_parser = subparsers.add_parser('sync', help='Safe-auto: add skeleton rows for referenced-not-in-inventory + refresh article refs')
    sync_parser.add_argument('--dry-run', action='store_true', help='Show changes, write nothing')
    sync_parser.add_argument('--no-head-check', action='store_true', help='Skip HEAD url_exists checks')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Audit / sync run WITHOUT the R2 uploader (read-mostly, no credentials needed).
    if args.command in ('audit', 'sync'):
        from audit_sync import audit as _audit, sync as _sync, write_report as _write_report
        from pathlib import Path as _Path
        inv = AssetInventory()
        if args.command == 'audit':
            a = _audit(inv)
            print(f"Inventory rows: {a['total_rows']}")
            print(f"URLs referenced in docs: {a['distinct_urls_in_docs']}")
            print(f"Referenced-not-in-inventory: {len(a['referenced_not_in_inventory'])} "
                  f"({len(a['referenced_not_in_inventory_images'])} images)")
            print(f"Repository image paths: {a['distinct_repo_paths_in_docs']} referenced, "
                  f"{len(a['repo_paths_not_in_inventory'])} with no row")
            print(f"Dead: {len(a['dead_rows'])} | Orphaned: {len(a['orphaned_rows'])} | "
                  f"Missing captions: {len(a['missing_caption_rows'])}")
            if args.out:
                _write_report(a, _Path(args.out))
                print(f"Report written: {args.out}")
        else:
            s = _sync(inv, dry_run=args.dry_run, head_check=not args.no_head_check)
            tag = 'DRY-RUN' if s['dry_run'] else 'APPLIED'
            print(f"[{tag}] added={s['added']} (live images={s['added_images_live']}, "
                  f"dead={s['added_dead']}) refreshed_refs={s['refreshed_refs']}")
        sys.exit(0)

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
                overwrite=not args.no_overwrite,
                resize=not args.no_resize,
                keep_captions=args.keep_captions
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
                regenerate_captions=not args.no_captions,
                resize=not args.no_resize,
                keep_captions=args.keep_captions
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
