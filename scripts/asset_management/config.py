#!/usr/bin/env python3
"""
Configuration loader for asset management system.

Supports loading credentials from:
1. Environment variables
2. .env file in this directory (load_dotenv never overrides a variable already set)
3. The nearest cloudflare_credentials.json in any folder above this one (the GitHub root)

Priority: environment > .env > cloudflare_credentials.json
"""

import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


CREDENTIALS_FILENAME = 'cloudflare_credentials.json'


def find_credentials_file(start: Path) -> Optional[Path]:
    """Return the nearest cloudflare_credentials.json in `start` or any folder above it.

    The file lives at the GitHub root (`~/GitHub/cloudflare_credentials.json`), above every
    checkout. Until tallyfy/documentation#443 this looked only 4 folders up, which reaches the
    GitHub root from the main checkout but stops at `.claude` from a worktree such as
    `documentation/.claude/worktrees/<name>/`, so every upload from a worktree refused. Walking
    every parent up to the filesystem root finds it from any depth. Never reads the file.
    """
    current = start
    while True:
        candidate = current / CREDENTIALS_FILENAME
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


class Config:
    """Configuration manager for asset management scripts."""

    def __init__(self):
        """Initialize configuration by loading from available sources."""
        # Try to load from .env file in this directory
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            self.source = '.env file'
        else:
            self.source = 'environment variables'

        # Load configuration
        self._load_cloudflare_config()
        self._load_r2_config()
        self._load_paths()

    def _load_cloudflare_config(self):
        """Load Cloudflare credentials from env or JSON file."""
        # Try environment variables first
        self.account_id = os.getenv('CLOUDFLARE_ACCOUNT_ID')
        self.r2_token = os.getenv('CLOUDFLARE_R2_TOKEN')
        self.api_token = os.getenv('CLOUDFLARE_API_TOKEN')

        # If not in environment, try cloudflare_credentials.json
        if not (self.account_id and self.r2_token):
            cred_path = self._find_credentials_file()
            if cred_path:
                with open(cred_path, 'r') as f:
                    creds = json.load(f)
                    self.account_id = self.account_id or creds.get('account_id')
                    self.r2_token = self.r2_token or creds.get('r2_api_token')
                    self.api_token = self.api_token or creds.get('api_token')
                    self.source = f'cloudflare_credentials.json ({cred_path})'

    def _load_r2_config(self):
        """Load R2-specific configuration."""
        self.r2_bucket = os.getenv('R2_BUCKET_NAME', 'screenshots')
        self.r2_public_url = os.getenv('R2_PUBLIC_URL', 'https://screenshots.tallyfy.com')

        # Construct R2 API endpoint
        if self.account_id:
            self.r2_endpoint = f'https://{self.account_id}.r2.cloudflarestorage.com'
        else:
            self.r2_endpoint = None

    def _load_paths(self):
        """Load file path configuration."""
        # Default to repository root
        repo_root = Path(__file__).parent.parent.parent

        # CSV inventory path
        default_csv = repo_root / 'documentation_assets.csv'
        csv_path = os.getenv('INVENTORY_CSV_PATH', str(default_csv))
        self.inventory_csv = Path(csv_path)

    def _find_credentials_file(self) -> Optional[Path]:
        """Find cloudflare_credentials.json in a parent directory of this script."""
        return find_credentials_file(Path(__file__).resolve().parent)

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate that required configuration is present.

        Returns:
            tuple: (is_valid, list_of_missing_fields)
        """
        missing = []

        if not self.account_id:
            missing.append('CLOUDFLARE_ACCOUNT_ID')
        if not self.r2_token:
            missing.append('CLOUDFLARE_R2_TOKEN')
        if not self.r2_endpoint:
            missing.append('R2 endpoint (derived from account_id)')
        if not self.inventory_csv.exists():
            missing.append(f'Inventory CSV at {self.inventory_csv}')

        return (len(missing) == 0, missing)

    def print_config(self):
        """Print current configuration (masking sensitive values)."""
        print(f"Configuration loaded from: {self.source}")
        print("  Account ID: set" if self.account_id else "  Account ID: NOT SET")
        print(f"  R2 Token: {'*' * 20}" if self.r2_token else "  R2 Token: NOT SET")
        print(f"  R2 Bucket: {self.r2_bucket}")
        print(f"  R2 Public URL: {self.r2_public_url}")
        print("  R2 Endpoint: set (from the account ID)" if self.r2_endpoint else "  R2 Endpoint: NOT SET")
        print(f"  Inventory CSV: {self.inventory_csv}")
        print(f"  CSV exists: {self.inventory_csv.exists()}")


# Global configuration instance
config = Config()


def _self_test() -> int:
    """Prove find_credentials_file finds the file from deep and shallow folders, and not when absent.

    Every case uses folders it builds in a temporary directory and never reads the file it finds.
    Returns 0 when every case passes, 1 when one fails.
    """
    import tempfile

    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve() / 'GitHub'
        main_checkout = root / 'documentation' / 'scripts' / 'asset_management'
        worktree = (root / 'documentation' / '.claude' / 'worktrees' / 'name'
                    / 'scripts' / 'asset_management')
        nested = root / 'temporary' / 'tables' / 'wt' / 'documentation-1' / 'scripts' / 'asset_management'
        no_creds = Path(tmp).resolve() / 'elsewhere' / 'scripts' / 'asset_management'
        for folder in (main_checkout, worktree, nested, no_creds):
            folder.mkdir(parents=True)
        creds = root / CREDENTIALS_FILENAME
        creds.write_text('{}')

        cases = [
            ('main checkout, 3 folders below the file', main_checkout, creds),
            ('worktree, 6 folders below the file', worktree, creds),
            ('nested worktree under temporary/, 6 folders below', nested, creds),
        ]
        # The absent case only proves something if nothing above the temp dir has the file.
        if find_credentials_file(Path(tmp).resolve()) is None:
            cases.append(('no file anywhere above', no_creds, None))
        else:
            print('  [skip] a credentials file exists above the temp dir, so the absent case cannot run')
        for name, start, expected in cases:
            got = find_credentials_file(start)
            ok = got == expected
            failures += 0 if ok else 1
            print(f"  [{'ok' if ok else 'FAIL'}] {name}: expected {expected is not None}, got {got is not None}")

    print(f"SELF-TEST {'PASSED' if failures == 0 else 'FAILED'}: {len(cases) - failures} of {len(cases)} case(s)")
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    import sys

    if '--self-test' in sys.argv[1:]:
        sys.exit(_self_test())

    # Test configuration loading
    config.print_config()

    is_valid, missing = config.validate()
    if is_valid:
        print("\n✅ Configuration is valid and complete")
    else:
        print("\n❌ Configuration is incomplete. Missing:")
        for field in missing:
            print(f"  - {field}")
