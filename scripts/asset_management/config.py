#!/usr/bin/env python3
"""
Configuration loader for asset management system.

Supports loading credentials from:
1. .env file in this directory
2. Parent directory cloudflare_credentials.json
3. Environment variables

Priority: .env > environment > cloudflare_credentials.json
"""

import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


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
        """Find cloudflare_credentials.json in parent directories."""
        current = Path(__file__).parent

        # Search up to 4 levels
        for _ in range(4):
            current = current.parent
            cred_file = current / 'cloudflare_credentials.json'
            if cred_file.exists():
                return cred_file

        return None

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
        print(f"  Account ID: {self.account_id[:8]}..." if self.account_id else "  Account ID: NOT SET")
        print(f"  R2 Token: {'*' * 20}" if self.r2_token else "  R2 Token: NOT SET")
        print(f"  R2 Bucket: {self.r2_bucket}")
        print(f"  R2 Public URL: {self.r2_public_url}")
        print(f"  R2 Endpoint: {self.r2_endpoint}")
        print(f"  Inventory CSV: {self.inventory_csv}")
        print(f"  CSV exists: {self.inventory_csv.exists()}")


# Global configuration instance
config = Config()


if __name__ == '__main__':
    # Test configuration loading
    config.print_config()

    is_valid, missing = config.validate()
    if is_valid:
        print("\n✅ Configuration is valid and complete")
    else:
        print("\n❌ Configuration is incomplete. Missing:")
        for field in missing:
            print(f"  - {field}")
