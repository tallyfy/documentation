# Documentation Asset Manager Skill - Technical Reference

## Overview

This technical reference provides complete documentation for the `documentation-asset-manager` Claude Code skill, including script internals, API specifications, configuration options, and advanced usage patterns.

**Skill Location**: `scripts/asset_management/`
**Version**: 1.0.0
**Author**: Tallyfy Dev Team

## Table of Contents

1. [Architecture](#architecture)
2. [Script Reference](#script-reference)
3. [API Specifications](#api-specifications)
4. [Configuration](#configuration)
5. [Data Schemas](#data-schemas)
6. [Advanced Usage](#advanced-usage)
7. [Error Codes](#error-codes)
8. [Performance](#performance)
9. [Troubleshooting](#troubleshooting)

---

## Architecture

### Component Diagram

```
┌────────────────────────────────────────────────────────┐
│  orchestrator.py (Main Entry Point)                    │
│  Coordinates complete upload → caption → inventory flow│
└────────────────────────────────────────────────────────┘
              ↓                ↓                ↓
┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐
│  r2_uploader.py │  │image_captioner.py│  │asset_inventory.│
│  Upload to R2   │  │Generate captions │  │py Maintain CSV │
└─────────────────┘  └──────────────────┘  └────────────────┘
              ↓                ↓                ↓
┌────────────────────────────────────────────────────────┐
│  External Services                                      │
│  • Cloudflare R2 API                                   │
│  • Claude Vision API                                   │
│  • documentation_assets.csv                            │
└────────────────────────────────────────────────────────┘
```

### Data Flow

```
[User provides image file]
        ↓
[orchestrator.py validates file]
        ↓
[r2_uploader.py uploads to R2] → Returns public URL
        ↓
[image_captioner.py generates AI captions] → Returns alt_text, descriptive, seo
        ↓
[asset_inventory.py updates CSV] → Adds/updates row with metadata + captions
        ↓
[orchestrator.py returns complete result to user]
```

---

## Script Reference

### 1. orchestrator.py

**Purpose**: Main workflow coordinator for complete asset management pipeline

**Location**: `scripts/asset_management/orchestrator.py`

#### Command-Line Interface

```bash
python3 orchestrator.py \
  --file PATH \
  [--key KEY] \
  [--article-ids IDS] \
  [--credentials PATH] \
  [--skip-captions] \
  [--batch-mode] \
  [--verbose]
```

#### Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `--file` | Yes | Path | Local file path to upload |
| `--key` | No | String | R2 bucket key (default: auto-generated from filename) |
| `--article-ids` | No | CSV String | Comma-separated article IDs |
| `--credentials` | No | Path | Cloudflare credentials JSON (default: `../cloudflare_credentials.json`) |
| `--skip-captions` | No | Flag | Skip AI caption generation |
| `--batch-mode` | No | Flag | Suppress progress output |
| `--verbose` | No | Flag | Enable debug logging |

#### Return Values

```python
{
  "success": True,
  "filename": "desktop-light-assign-task.png",
  "r2_key": "tallyfy/pro/desktop-light-assign-task.png",
  "production_url": "https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-assign-task.png",
  "file_size": "125.4KB",
  "file_size_bytes": 128512,
  "captions": {
    "alt_text": "Task assignment interface...",
    "descriptive": "Detailed caption...",
    "seo": "SEO keywords..."
  },
  "inventory_updated": True
}
```

#### Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 1 | File not found | Verify file path |
| 2 | Upload failed | Check credentials |
| 3 | Caption generation failed | Image format issue or API error |
| 4 | Inventory update failed | CSV locked or permissions issue |

---

### 2. r2_uploader.py

**Purpose**: Upload files to Cloudflare R2 bucket via REST API

**Location**: `scripts/asset_management/r2_uploader.py`

#### Command-Line Interface

```bash
python3 r2_uploader.py \
  --file PATH \
  --key KEY \
  [--credentials PATH] \
  [--bucket NAME] \
  [--overwrite]
```

#### Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `--file` | Yes | Path | Local file to upload |
| `--key` | Yes | String | R2 object key (path in bucket) |
| `--credentials` | No | Path | Cloudflare credentials (default: `../cloudflare_credentials.json`) |
| `--bucket` | No | String | R2 bucket name (default: `screenshots`) |
| `--overwrite` | No | Flag | Overwrite if key exists (default: True) |

#### Python API

```python
from r2_uploader import R2Uploader

# Initialize uploader
uploader = R2Uploader(credentials_path='../cloudflare_credentials.json')

# Upload file
result = uploader.upload_file(
    local_path='/path/to/screenshot.png',
    r2_key='tallyfy/pro/feature.png'
)

# Result:
# {
#   'success': True,
#   'url': 'https://screenshots.tallyfy.com/tallyfy/pro/feature.png',
#   'key': 'tallyfy/pro/feature.png',
#   'size': '125.4KB',
#   'size_bytes': 128512,
#   'content_type': 'image/png',
#   'etag': '...',
#   'message': 'Uploaded screenshot.png to tallyfy/pro/feature.png'
# }
```

#### Internal Functions

| Function | Description |
|----------|-------------|
| `load_credentials()` | Load and validate Cloudflare credentials |
| `get_file_metadata(path)` | Extract file size, type, dimensions |
| `upload_file(local_path, r2_key)` | Main upload function |
| `generate_public_url(key)` | Convert R2 key to public CDN URL |

---

### 3. image_captioner.py

**Purpose**: Generate AI-powered captions using Claude Vision

**Location**: `scripts/asset_management/image_captioner.py`

#### Command-Line Interface

```bash
python3 image_captioner.py \
  --url URL \
  [--type TYPE] \
  [--output PATH] \
  [--update-inventory]
```

#### Parameters

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `--url` | Yes | URL | Public image URL |
| `--type` | No | Enum | Caption type: `all`, `alt_text`, `descriptive`, `seo` (default: `all`) |
| `--output` | No | Path | JSON output file path |
| `--update-inventory` | No | Flag | Auto-update CSV inventory |

#### Python API

```python
from image_captioner import ImageCaptioner

# Initialize captioner
captioner = ImageCaptioner()

# Generate all caption types
captions = captioner.generate_all_captions(
    image_url='https://screenshots.tallyfy.com/image.png'
)

# Result:
# {
#   'alt_text': '1-2 sentence accessible description',
#   'descriptive': '2-4 sentence detailed description',
#   'seo': 'SEO-optimized keyword-rich description'
# }

# Generate specific caption type
alt_caption = captioner.generate_caption(
    image_source='https://screenshots.tallyfy.com/image.png',
    caption_type='alt_text',
    is_url=True
)
```

#### Prompt Templates

**Alt Text Prompt**:
```
Generate concise, accessible alt text (1-2 sentences maximum) for this
documentation screenshot. Describe what the image shows directly without
phrases like "screenshot of" or "image showing".
```

**Descriptive Prompt**:
```
Generate a detailed description (2-4 sentences) of this documentation
screenshot. Include specific UI elements visible, what functionality is
being demonstrated, and key visual details.
```

**SEO Prompt**:
```
Generate SEO-optimized description for this documentation screenshot.
Include what Tallyfy feature is shown, specific UI elements visible,
and the user action being documented.
```

#### Internal Functions

| Function | Description |
|----------|-------------|
| `download_image(url)` | Download image from URL to memory |
| `encode_image(image_path)` | Convert image to base64 |
| `generate_caption(image, type)` | Call Claude Vision API |
| `generate_all_captions(url)` | Generate all 3 caption types |

---

### 4. asset_inventory.py

**Purpose**: Manage master CSV inventory of all documentation assets

**Location**: `scripts/asset_management/asset_inventory.py`

#### Command-Line Interface

```bash
python3 asset_inventory.py \
  --action ACTION \
  [--r2-key KEY] \
  [--url URL] \
  [--captions JSON_PATH] \
  [--article-ids IDS] \
  [--stats] \
  [--verify-urls] \
  [--rebuild]
```

#### Actions

| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `add` | Add new asset | `--r2-key`, `--url` |
| `update` | Update existing asset | `--r2-key` or `--url` |
| `delete` | Remove asset | `--r2-key` or `--url` |
| `find` | Search for asset | `--r2-key` or `--url` or `--filename` |
| `list` | List all assets | None |
| `stats` | Show statistics | None |
| `verify-urls` | Check all URLs | None |
| `rebuild` | Rebuild from R2 + docs | None |

#### Python API

```python
from asset_inventory import AssetInventory

# Initialize inventory manager
inventory = AssetInventory(csv_path='/documentation/documentation_assets.csv')

# Add new asset
inventory.add_asset({
    'filename': 'desktop-light-feature.png',
    'r2_key': 'tallyfy/pro/desktop-light-feature.png',
    'production_url': 'https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-feature.png',
    'source_type': 'native',
    'file_type': '.png',
    'file_size': '125.4KB',
    'file_size_bytes': 128512,
    'url_exists': True,
    'article_ids': 'pro-feature-guide,pro-getting-started',
    'article_count': 2,
    'ai_caption_alt': 'Feature interface showing...',
    'ai_caption_descriptive': 'Detailed description...',
    'ai_caption_seo': 'SEO keywords...',
    'needs_caption': 'no'
})

# Find asset
asset = inventory.find_asset(production_url='https://screenshots.tallyfy.com/...')

# Update captions
inventory.update_captions(
    production_url='https://screenshots.tallyfy.com/...',
    captions={
        'ai_caption_alt': 'Updated alt text',
        'ai_caption_descriptive': 'Updated description',
        'ai_caption_seo': 'Updated SEO text'
    }
)

# Get statistics
stats = inventory.get_stats()
# Returns: {'total': 812, 'active': 290, 'orphaned': 499, 'missing': 23, ...}
```

#### CSV Schema

See "Data Schemas" section for complete 16-column schema.

---

## API Specifications

### Cloudflare R2 API

**Base URL**: `https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets/{bucket}/objects/{key}`

**Authentication**: Bearer token via `Authorization` header

**Upload Request**:
```http
PUT /client/v4/accounts/{account_id}/r2/buckets/screenshots/objects/{key} HTTP/1.1
Host: api.cloudflare.com
Authorization: Bearer {r2_api_token}
Content-Type: image/png
Content-Length: {file_size}

{binary_file_data}
```

**Upload Response** (Success):
```json
{
  "success": true,
  "errors": [],
  "messages": [],
  "result": {
    "key": "tallyfy/pro/feature.png",
    "etag": "\"abc123...\"",
    "size": 128512,
    "uploaded": "2025-11-19T15:08:00Z"
  }
}
```

**Upload Response** (Error):
```json
{
  "success": false,
  "errors": [
    {
      "code": 10000,
      "message": "Authentication error"
    }
  ]
}
```

### Claude Vision API

**Model**: `claude-sonnet-4-5-20250929` (Claude 3.5 Sonnet)

**Request Format**:
```json
{
  "model": "claude-sonnet-4-5-20250929",
  "max_tokens": 512,
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "{base64_encoded_image}"
          }
        },
        {
          "type": "text",
          "text": "{caption_prompt}"
        }
      ]
    }
  ]
}
```

**Response Format**:
```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Task assignment interface showing user selection dropdown menu with role-based options"
    }
  ],
  "model": "claude-sonnet-4-5-20250929",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 2048,
    "output_tokens": 25
  }
}
```

---

## Configuration

### Credentials File Format

**Location**: `/cloudflare_credentials.json`

```json
{
  "account_id": "ac9046789c9ad74c8704a143b442f918",
  "api_token": "cloudflare-api-token-here",
  "r2_api_token": "r2-specific-api-token-here"
}
```

**Required Fields**:
- `account_id`: Cloudflare account ID
- `r2_api_token`: R2-specific API token with Object Read & Write permissions

**Optional Fields**:
- `api_token`: General Cloudflare API token (not used by skill)

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude Vision API authentication | From `~/.anthropic/api_key` |
| `DEBUG` | Enable debug logging | `false` |
| `SKIP_CAPTIONS` | Skip caption generation globally | `false` |

### R2 Bucket Configuration

**Bucket Settings**:
- Name: `screenshots`
- Region: `auto` (global)
- Public Access: Custom domain (`screenshots.tallyfy.com`)
- CORS: Enabled for documentation domains

**Custom Domain**:
- Domain: `screenshots.tallyfy.com`
- SSL: Enabled (Cloudflare managed)
- CDN: Cloudflare global edge cache

---

## Data Schemas

### CSV Inventory Schema

**File**: `documentation_assets.csv`

| Column # | Field Name | Type | Description | Example |
|----------|-----------|------|-------------|---------|
| 1 | `filename` | String | Asset filename | `desktop-light-assign-task.png` |
| 2 | `r2_key` | String | Full R2 bucket path | `tallyfy/pro/desktop-light-assign-task.png` |
| 3 | `production_url` | String | Public CDN URL | `https://screenshots.tallyfy.com/...` |
| 4 | `source_type` | Enum | `native`, `orphaned`, `missing` | `native` |
| 5 | `file_type` | String | File extension | `.png` |
| 6 | `file_size` | String | Human-readable size | `125.4KB` |
| 7 | `file_size_bytes` | Integer | Size in bytes | `128512` |
| 8 | `url_exists` | Boolean | URL accessible (TRUE/FALSE) | `TRUE` |
| 9 | `article_ids` | CSV String | Comma-separated IDs | `pro-guide,pro-start` |
| 10 | `article_count` | Integer | Number of referencing articles | `2` |
| 11 | `last_modified` | ISO Timestamp | Last modified date | `2025-11-19T15:08:00Z` |
| 12 | `etag` | String | R2 ETag checksum | `"abc123..."` |
| 13 | `ai_caption_alt` | Text | Alt text caption (1-2 sentences) | `Task assignment interface...` |
| 14 | `ai_caption_descriptive` | Text | Detailed caption (2-4 sentences) | `Tallyfy task assignment screen...` |
| 15 | `ai_caption_seo` | Text | SEO caption (keywords) | `assign tasks Tallyfy workflow...` |
| 16 | `needs_caption` | Enum | `yes`, `no` | `no` |

---

## Advanced Usage

### Custom Caption Prompts

```python
from image_captioner import ImageCaptioner

captioner = ImageCaptioner()

# Custom prompt for specific documentation style
custom_prompt = """
Generate alt text for this Tallyfy screenshot following these rules:
- Start with the primary action shown (e.g., "Assigning tasks...")
- Mention specific UI elements visible
- Keep under 100 characters
- Use active voice
"""

caption = captioner.generate_caption(
    image_source='https://screenshots.tallyfy.com/image.png',
    caption_type='alt_text',
    is_url=True,
    custom_prompt=custom_prompt
)
```

### Batch Processing with Rate Limiting

```python
import time
from orchestrator import Orchestrator

orchestrator = Orchestrator()

images = [
    {'file': 'screenshot1.png', 'key': 'tallyfy/pro/feature1.png'},
    {'file': 'screenshot2.png', 'key': 'tallyfy/pro/feature2.png'},
    # ... 50 more images
]

for img in images:
    result = orchestrator.process_asset(
        local_path=img['file'],
        r2_key=img['key'],
        skip_captions=False
    )

    if result['success']:
        print(f"✅ {img['file']}")
    else:
        print(f"❌ {img['file']}: {result['error']}")

    # Rate limiting: 2 seconds between uploads
    time.sleep(2)
```

### Inventory Synchronization

```bash
# Rebuild inventory from scratch
python3 scripts/asset_inventory.py --action rebuild

# This will:
# 1. Scan R2 bucket for all objects
# 2. Scan documentation for all image references
# 3. Cross-reference and classify (native/orphaned/missing)
# 4. Preserve existing captions
# 5. Regenerate complete CSV
```

---

## Error Codes

### System Error Codes

| Code | Category | Description | Resolution |
|------|----------|-------------|------------|
| E001 | Credentials | Credentials file not found | Check `/cloudflare_credentials.json` exists |
| E002 | Credentials | Invalid credentials format | Verify JSON structure and required fields |
| E003 | Upload | R2 API authentication failed | Verify `r2_api_token` has correct permissions |
| E004 | Upload | Network error during upload | Check internet connection, retry |
| E005 | Upload | File not found | Verify local file path exists |
| E006 | Caption | Anthropic API key missing | Set `ANTHROPIC_API_KEY` or create `~/.anthropic/api_key` |
| E007 | Caption | Claude Vision API error | Check API key validity, quotas, rate limits |
| E008 | Caption | Image format not supported | Use PNG, JPG, GIF, or WEBP |
| E009 | Inventory | CSV file locked | Another process is using CSV, wait and retry |
| E010 | Inventory | CSV corrupted | Restore from backup or rebuild |

---

## Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Upload 1MB PNG | ~500ms | Network dependent |
| Generate alt text | ~2s | Claude Vision processing |
| Generate all 3 captions | ~6s | Sequential API calls |
| CSV inventory update | ~10ms | Single row operation |
| Complete workflow (upload + captions + inventory) | ~7s | For 1MB image |

### Optimization Tips

1. **Skip captions for batch uploads**: Generate captions separately after batch completes
2. **Use parallel workers**: Upload multiple images concurrently (max 5 concurrent)
3. **Compress images**: Optimize file sizes before upload (< 500KB ideal)
4. **Cache caption results**: Store captions in temporary file between operations
5. **Batch inventory updates**: Update CSV once after processing multiple images

### Rate Limits

**Claude Vision API**:
- Tier 1: 50 requests/minute
- Tier 2: 200 requests/minute
- Recommended: 1 request every 2 seconds for sustainable throughput

**Cloudflare R2 API**:
- No explicit rate limits
- Recommended: 10 uploads/second max for stability

---

## Troubleshooting

### Common Issues Matrix

| Symptom | Likely Cause | Diagnostic Command | Fix |
|---------|--------------|-------------------|-----|
| Upload succeeds but URL 404 | CDN cache delay | `curl -I {url}` | Wait 30-60s |
| "Invalid image format" | Unsupported file type | `file {path}` | Convert to PNG/JPG |
| "Rate limit exceeded" | Too many API calls | Check logs | Wait 60s, reduce frequency |
| Caption generation fails | API key issue | `echo $ANTHROPIC_API_KEY` | Set valid API key |
| CSV update fails | File locked | `lsof {csv_path}` | Close other processes |
| Slow uploads | Large file size | `ls -lh {file}` | Compress image |

### Debug Mode

Enable verbose logging:

```bash
DEBUG=true python3 scripts/orchestrator.py --file screenshot.png --verbose
```

Output includes:
- HTTP request/response details
- API call timing
- File I/O operations
- CSV operations
- Error stack traces

---

## References

- **SKILL.md**: `scripts/asset_management/SKILL.md`
- **User Guide**: `/documentation/ASSET_MANAGEMENT_GUIDE.md`
- **Build Integration**: `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md`
- **CLAUDE.md**: `/documentation/CLAUDE.md` (asset management section)
- **Cloudflare R2 API**: https://developers.cloudflare.com/r2/api/
- **Anthropic Claude API**: https://docs.anthropic.com/claude/reference/

---

**Last Updated**: 2025-11-19
**Maintained By**: Tallyfy Dev Team
**Skill Version**: 1.0.0
