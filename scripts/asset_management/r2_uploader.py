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
from datetime import datetime, timezone

from config import config


class R2Uploader:
    """Cloudflare R2 storage uploader.

    Every request goes to the Cloudflare REST API, NOT to the S3-compatible endpoint
    (`<account>.r2.cloudflarestorage.com`). That is deliberate and it is not a style choice:

        R2's S3 endpoint requires AWS SigV4. Measured 2026-08-16, a Bearer API token against
        it walks a three-step staircase of 400s and never succeeds -
          no extra headers          -> InvalidRequest "Missing x-amz-content-sha256"
          + x-amz-content-sha256    -> InvalidArgument "No date provided in x-amz-date nor date header"
          + x-amz-date              -> InvalidRequest  "Please use AWS4-HMAC-SHA256"
        There is no header you can add to finish that climb, because the credential we hold is
        an API token and not an access-key/secret pair. Every upload through this class had
        been failing with the first of those three for as long as it took someone to notice.

    The REST object API takes the same Bearer token we already have:
        PUT/GET/HEAD/DELETE https://api.cloudflare.com/client/v4/accounts/{acct}/r2/buckets/{bucket}/objects/{key}

    Two traps live in that API, both measured, both of which make a probe answer confidently
    about the wrong thing:

      1. GET and HEAD on an object are EDGE-CACHED. A deleted object keeps answering 200 with
         `cf-cache-status: HIT` for minutes. `file_exists` therefore asks the LIST endpoint and
         compares the returned key to the one requested, which is uncached and was correct
         immediately after a delete (control: a live key matches, a fabricated key does not).
      2. The key goes in as PATH SEGMENTS, unencoded. URL-encoding it (`%2F`) addresses a
         literally-different object and returns "The specified key does not exist", and a
         cache-busting query parameter is read as part of the key, so a KNOWN-LIVE asset 404s.
    """

    API_ROOT = 'https://api.cloudflare.com/client/v4'

    def __init__(self):
        """Initialize R2 uploader with configuration."""
        self.account_id = config.account_id
        self.r2_token = config.r2_token
        self.bucket = config.r2_bucket
        # Kept for callers/diagnostics that still reference it. Nothing in this class talks to
        # it any more - see the class docstring for why it cannot work with a Bearer token.
        self.endpoint = config.r2_endpoint
        self.public_url = config.r2_public_url

        # Validate configuration
        is_valid, missing = config.validate()
        if not is_valid:
            raise ValueError(f"Invalid configuration. Missing: {', '.join(missing)}")

    @property
    def _objects_url(self) -> str:
        """Base URL for object operations on this bucket."""
        return f'{self.API_ROOT}/accounts/{self.account_id}/r2/buckets/{self.bucket}/objects'

    def _object_url(self, r2_key: str) -> str:
        """URL for one object. The key is appended raw - see trap 2 in the class docstring."""
        return f'{self._objects_url}/{r2_key}'

    @property
    def _auth_headers(self) -> Dict[str, str]:
        return {'Authorization': f'Bearer {self.r2_token}'}

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

        headers = dict(self._auth_headers)
        headers['Content-Type'] = content_type

        try:
            response = requests.put(
                self._object_url(r2_key),
                headers=headers,
                data=file_data,
                timeout=60
            )

            # The REST API answers HTTP 200 with a JSON envelope carrying its own `success`
            # flag. A failure can arrive as HTTP 200 + success:false (that is how a bad key
            # reports itself), so the status code alone is not the verdict.
            payload = {}
            try:
                payload = response.json()
            except ValueError:
                pass

            if response.status_code in (200, 201) and payload.get('success') is True:
                result = payload.get('result') or {}
                etag = str(result.get('etag', '')).strip('"')
                return {
                    'success': True,
                    'url': f'{self.public_url}/{r2_key}',
                    'r2_key': r2_key,
                    'etag': etag,
                    # `size` comes back as a string; trust the bytes we actually sent.
                    'size': file_size,
                    'last_modified': datetime.now(timezone.utc).isoformat(),
                    'content_type': content_type
                }
            else:
                detail = payload.get('errors') or response.text
                return {
                    'success': False,
                    'error': f'Upload failed: HTTP {response.status_code} - {detail}',
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

        Asks the LIST endpoint rather than HEAD-ing the object, because object reads are
        edge-cached and a deleted object keeps answering 200 (`cf-cache-status: HIT`). LIST
        answered correctly the instant a delete landed. The exact-key comparison matters: a
        prefix query is a prefix, so `foo.png` would otherwise be reported present by
        `foo.png.bak`.

        Args:
            r2_key: R2 object key to check

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            response = requests.get(
                self._objects_url,
                headers=self._auth_headers,
                params={'prefix': r2_key, 'per_page': 10},
                timeout=15
            )
            if response.status_code != 200:
                return False
            payload = response.json()
            if payload.get('success') is not True:
                return False
            return any(obj.get('key') == r2_key for obj in (payload.get('result') or []))
        except (requests.exceptions.RequestException, ValueError):
            return False

    def delete_file(self, r2_key: str) -> Dict[str, Any]:
        """
        Delete a file from R2.

        Args:
            r2_key: R2 object key to delete

        Returns:
            dict: Result with success status and error if any
        """
        try:
            response = requests.delete(
                self._object_url(r2_key),
                headers=self._auth_headers,
                timeout=30
            )

            payload = {}
            try:
                payload = response.json()
            except ValueError:
                pass

            if response.status_code == 200 and payload.get('success') is True:
                return {'success': True, 'r2_key': r2_key}

            detail = payload.get('errors') or response.text
            return {
                'success': False,
                'error': f'Delete failed: HTTP {response.status_code} - {detail}',
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

        # Get file metadata from the LIST entry (same reason as file_exists: object HEAD/GET
        # are edge-cached and can describe a version that is no longer there).
        try:
            response = requests.get(
                self._objects_url,
                headers=self._auth_headers,
                params={'prefix': r2_key, 'per_page': 10},
                timeout=15
            )
            entry = next(
                (o for o in ((response.json().get('result') or []) if response.status_code == 200 else [])
                 if o.get('key') == r2_key),
                {}
            )
            etag = str(entry.get('etag', '')).strip('"')
            size = int(entry.get('size', 0) or 0)
            last_modified = entry.get('last_modified')

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

        except (requests.exceptions.RequestException, ValueError) as e:
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
