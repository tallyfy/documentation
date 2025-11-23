#!/usr/bin/env python3
"""
Cloudflare R2 uploader for documentation assets.

Handles uploading files to Cloudflare R2 storage bucket
and returns public CDN URLs for use in documentation.
"""

import os
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from config import config


class R2Uploader:
    """Cloudflare R2 storage uploader."""

    def __init__(self):
        """Initialize R2 uploader with configuration."""
        self.account_id = config.account_id
        self.r2_token = config.r2_token
        self.bucket = config.r2_bucket
        self.endpoint = config.r2_endpoint
        self.public_url = config.r2_public_url

        # Validate configuration
        is_valid, missing = config.validate()
        if not is_valid:
            raise ValueError(f"Invalid configuration. Missing: {', '.join(missing)}")

    def upload_file(
        self,
        file_path: str | Path,
        r2_key: str,
        overwrite: bool = True,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to R2 storage.

        Args:
            file_path: Local path to file to upload
            r2_key: R2 object key (path in bucket)
            overwrite: Allow overwriting existing files
            content_type: MIME type (auto-detected if None)

        Returns:
            dict: Upload result with keys:
                - success (bool): Whether upload succeeded
                - url (str): Public CDN URL
                - r2_key (str): R2 object key
                - etag (str): R2 ETag hash
                - size (int): File size in bytes
                - last_modified (str): Last modified timestamp
                - error (str): Error message if failed

        Raises:
            FileNotFoundError: If file_path doesn't exist
            ValueError: If r2_key is empty or invalid
        """
        file_path = Path(file_path)

        # Validation
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not r2_key or not r2_key.strip():
            raise ValueError("r2_key cannot be empty")

        # Auto-detect content type if not provided
        if content_type is None:
            content_type = self._detect_content_type(file_path)

        # Read file
        with open(file_path, 'rb') as f:
            file_data = f.read()

        file_size = len(file_data)

        # Check if file exists (optional pre-check)
        if not overwrite:
            exists = self.file_exists(r2_key)
            if exists:
                return {
                    'success': False,
                    'error': f'File already exists at {r2_key} and overwrite=False',
                    'r2_key': r2_key,
                    'url': f'{self.public_url}/{r2_key}'
                }

        # Build upload URL
        upload_url = f'{self.endpoint}/{self.bucket}/{r2_key}'

        # Headers
        headers = {
            'Authorization': f'Bearer {self.r2_token}',
            'Content-Type': content_type,
            'Content-Length': str(file_size)
        }

        try:
            # Upload to R2
            response = requests.put(
                upload_url,
                headers=headers,
                data=file_data,
                timeout=60
            )

            if response.status_code in [200, 201]:
                # Extract metadata from response headers
                etag = response.headers.get('ETag', '').strip('"')
                last_modified = response.headers.get('Last-Modified', datetime.utcnow().isoformat())

                return {
                    'success': True,
                    'url': f'{self.public_url}/{r2_key}',
                    'r2_key': r2_key,
                    'etag': etag,
                    'size': file_size,
                    'last_modified': last_modified,
                    'content_type': content_type
                }
            else:
                return {
                    'success': False,
                    'error': f'Upload failed: HTTP {response.status_code} - {response.text}',
                    'r2_key': r2_key,
                    'status_code': response.status_code
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Upload request failed: {str(e)}',
                'r2_key': r2_key
            }

    def file_exists(self, r2_key: str) -> bool:
        """
        Check if a file exists in R2.

        Args:
            r2_key: R2 object key to check

        Returns:
            bool: True if file exists, False otherwise
        """
        head_url = f'{self.endpoint}/{self.bucket}/{r2_key}'

        headers = {
            'Authorization': f'Bearer {self.r2_token}'
        }

        try:
            response = requests.head(head_url, headers=headers, timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def delete_file(self, r2_key: str) -> Dict[str, Any]:
        """
        Delete a file from R2.

        Args:
            r2_key: R2 object key to delete

        Returns:
            dict: Result with success status and error if any
        """
        delete_url = f'{self.endpoint}/{self.bucket}/{r2_key}'

        headers = {
            'Authorization': f'Bearer {self.r2_token}'
        }

        try:
            response = requests.delete(delete_url, headers=headers, timeout=30)

            if response.status_code in [200, 204]:
                return {'success': True, 'r2_key': r2_key}
            else:
                return {
                    'success': False,
                    'error': f'Delete failed: HTTP {response.status_code}',
                    'r2_key': r2_key
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Delete request failed: {str(e)}',
                'r2_key': r2_key
            }

    def verify_upload(self, r2_key: str, local_file: Optional[Path] = None) -> Dict[str, Any]:
        """
        Verify that an uploaded file matches local file.

        Args:
            r2_key: R2 object key to verify
            local_file: Local file to compare (optional)

        Returns:
            dict: Verification result with metadata
        """
        # Check if file exists
        if not self.file_exists(r2_key):
            return {
                'verified': False,
                'error': 'File not found in R2',
                'r2_key': r2_key
            }

        # Get file metadata
        head_url = f'{self.endpoint}/{self.bucket}/{r2_key}'
        headers = {'Authorization': f'Bearer {self.r2_token}'}

        try:
            response = requests.head(head_url, headers=headers, timeout=10)
            etag = response.headers.get('ETag', '').strip('"')
            size = int(response.headers.get('Content-Length', 0))
            last_modified = response.headers.get('Last-Modified')

            result = {
                'verified': True,
                'r2_key': r2_key,
                'url': f'{self.public_url}/{r2_key}',
                'etag': etag,
                'size': size,
                'last_modified': last_modified
            }

            # If local file provided, verify size matches
            if local_file and Path(local_file).exists():
                local_size = Path(local_file).stat().st_size
                if local_size != size:
                    result['verified'] = False
                    result['error'] = f'Size mismatch: local={local_size}, remote={size}'

            return result

        except requests.exceptions.RequestException as e:
            return {
                'verified': False,
                'error': f'Verification failed: {str(e)}',
                'r2_key': r2_key
            }

    def _detect_content_type(self, file_path: Path) -> str:
        """Detect MIME type from file extension."""
        extension = file_path.suffix.lower()

        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.mp4': 'video/mp4',
            '.pdf': 'application/pdf',
            '.json': 'application/json',
            '.zip': 'application/zip'
        }

        return mime_types.get(extension, 'application/octet-stream')


# CLI interface for testing
if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Upload files to Cloudflare R2')
    parser.add_argument('file', help='File to upload')
    parser.add_argument('key', help='R2 object key (path in bucket)')
    parser.add_argument('--no-overwrite', action='store_true', help='Fail if file exists')
    parser.add_argument('--verify', action='store_true', help='Verify upload after completion')

    args = parser.parse_args()

    uploader = R2Uploader()

    print(f"Uploading {args.file} to R2 as {args.key}...")

    result = uploader.upload_file(
        args.file,
        args.key,
        overwrite=not args.no_overwrite
    )

    if result['success']:
        print(f"✅ Upload successful!")
        print(f"   URL: {result['url']}")
        print(f"   Size: {result['size']:,} bytes")
        print(f"   ETag: {result['etag']}")

        if args.verify:
            print("\nVerifying upload...")
            verify_result = uploader.verify_upload(args.key, Path(args.file))
            if verify_result['verified']:
                print("✅ Verification passed")
            else:
                print(f"❌ Verification failed: {verify_result.get('error', 'Unknown error')}")
                sys.exit(1)
    else:
        print(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
