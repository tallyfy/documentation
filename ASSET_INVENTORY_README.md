# Documentation Asset Inventory - README

> **Path Convention**: This document uses `$GITHUB_ROOT` to represent your GitHub workspace directory (e.g., `/Users/username/GitHub` or `~/GitHub`). Replace `$GITHUB_ROOT` with your actual path when executing commands. Scripts auto-detect paths relative to their location and support the `GITHUB_ROOT` environment variable.

## File Locations

### Primary Location

**Master Inventory CSV**:
- `$GITHUB_ROOT/documentation/documentation_assets.csv` (version-controlled in /documentation repo)

This is the **ONLY** copy of the inventory. There is no root directory copy. All scripts and systems reference this single location.

### Working Directory

**Asset Inventory Workspace**:
- `$GITHUB_ROOT/temporary/asset-inventory/` - Working directory for inventory generation
- `asset_inventory_master.csv` - Original generated inventory (source of truth)
- `batch_assignments.json` - Parallel caption generation task assignments
- `images_for_captioning.json` - List of images needing captions

## File Descriptions

### documentation_assets.csv

**Purpose**: Master catalog of all documentation assets hosted on Cloudflare R2

**Schema** (16 columns):
1. `filename` - Asset filename (e.g., `desktop-light-assign-task.png`)
2. `r2_key` - Full R2 bucket path (e.g., `tallyfy/pro/desktop-light-assign-task.png`)
3. `production_url` - Public CDN URL (`https://screenshots.tallyfy.com/{r2_key}`)
4. `source_type` - `native` (used), `orphaned` (unused), `missing` (404)
5. `file_type` - File extension (`.png`, `.jpg`, `.svg`, etc.)
6. `file_size` - Human-readable size (e.g., `45.2KB`)
7. `file_size_bytes` - Size in bytes
8. `url_exists` - Boolean (`TRUE`/`FALSE`) - URL accessibility
9. `article_ids` - Comma-separated article IDs where image is used
10. `article_count` - Number of articles referencing this image
11. `last_modified` - Last modified timestamp
12. `etag` - R2 ETag checksum
13. `ai_caption_alt` - AI-generated alt text caption
14. `ai_caption_descriptive` - AI-generated detailed caption
15. `ai_caption_seo` - AI-generated SEO-optimized caption
16. `needs_caption` - `yes`|`no` - Whether image should have AI caption

### Current Statistics (as of 2025-11-19)

- **Total assets**: 812 (plus 1 header row = 813 lines)
- **Active** (used in documentation): 290
- **Orphaned** (not referenced): 499
- **Missing** (404 errors): 23
- **File size**: 233KB

## Usage

### For Writers/Editors

See `ASSET_MANAGEMENT_GUIDE.md` for complete usage instructions on:
- Adding new screenshots
- Replacing existing images
- Finding image URLs
- Understanding AI-generated captions

### For Developers

See `BUILD_TIME_ALT_TEXT_INTEGRATION.md` for technical details on:
- Build-time alt text injection
- Remark plugin architecture
- CSV schema and data flow
- Integration with Astro/Starlight

### For System Administrators

**Updating the Inventory**:
1. Run inventory generation script in `/temporary/asset-inventory/`
2. Review generated `asset_inventory_master.csv`
3. Copy to documentation repository:
   ```bash
   cp $GITHUB_ROOT/temporary/asset-inventory/asset_inventory_master.csv $GITHUB_ROOT/documentation/documentation_assets.csv
   ```
4. Commit changes to /documentation repository

## Version Control

**Single Source of Truth**: `$GITHUB_ROOT/documentation/documentation_assets.csv`
- Versioned in git
- Changes tracked with commit history
- Part of documentation repository
- **This is the ONLY copy** - no duplicate locations

## Maintenance

### Regular Tasks

**Weekly**:
- Verify CSV integrity
- Check for new orphaned assets

**Monthly**:
- Review orphaned assets for cleanup
- Update captions for improved quality
- Regenerate inventory to capture new assets

**As Needed**:
- After bulk screenshot uploads
- When documentation structure changes
- When cleaning up old/unused images

### Update Procedure

To update the inventory CSV from the working directory:

```bash
#!/bin/bash
# update-asset-inventory.sh

SOURCE="$GITHUB_ROOT/temporary/asset-inventory/asset_inventory_master.csv"
TARGET="$GITHUB_ROOT/documentation/documentation_assets.csv"

# Verify source exists
if [ ! -f "$SOURCE" ]; then
    echo "❌ Source file not found: $SOURCE"
    exit 1
fi

# Copy to documentation repository
cp "$SOURCE" "$TARGET"

# Verify
if [ -f "$TARGET" ]; then
    echo "✅ Inventory updated successfully"
    ls -lh "$TARGET"
    wc -l "$TARGET"
else
    echo "❌ Update failed"
    exit 1
fi
```

## Integration Points

### Build-Time Processing

The `/support-docs` repository uses this CSV during builds:
1. Remark plugin loads CSV at build initialization
2. Creates URL → alt text lookup map
3. Processes all MDX image nodes
4. Injects AI-generated captions as alt attributes

**Required**: CSV must be accessible to `/support-docs` during build (symlink or copy)

### Asset Management Skill

The `documentation-asset-manager` skill updates this CSV:
1. On upload: Adds new row with asset metadata
2. On caption generation: Updates caption fields
3. On replace: Updates row with new data
4. Maintains CSV integrity and formatting

## Data Sources

### How Inventory is Generated

1. **R2 Bucket Scan**: List all objects in `screenshots` bucket
2. **Documentation Scan**: Extract all image URLs from MDX files
3. **Cross-Reference**: Match R2 objects to documentation references
4. **Classification**: Tag as native/orphaned/missing
5. **Metadata Collection**: File size, timestamps, ETags
6. **Export**: Write to CSV with full schema

### Updating Asset Metadata

```python
# Example: Update a single asset's captions
import csv

csv_path = '$GITHUB_ROOT/documentation/documentation_assets.csv'

# Read all rows
with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Update specific row
for row in rows:
    if row['production_url'] == 'https://screenshots.tallyfy.com/target-image.png':
        row['ai_caption_alt'] = 'Updated alt text caption'
        row['ai_caption_descriptive'] = 'Updated descriptive caption'
        row['ai_caption_seo'] = 'Updated SEO caption'

# Write back
with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
```

## Troubleshooting

### CSV Not Found During Build

**Symptom**: Remark plugin fails to load CSV
**Solution**: Verify CSV exists at expected path or create symlink:
```bash
ln -s $GITHUB_ROOT/documentation/documentation_assets.csv $GITHUB_ROOT/support-docs/documentation_assets.csv
```

### CSV Corrupted or Invalid

**Symptom**: Parse errors, missing columns
**Solution**: Regenerate from master source:
```bash
cp $GITHUB_ROOT/temporary/asset-inventory/asset_inventory_master.csv $GITHUB_ROOT/documentation/documentation_assets.csv
```

### Inventory Corrupted

**Symptom**: CSV parse errors, missing data, or corrupted content
**Solution**: Restore from working directory master:
```bash
# Restore from asset inventory working directory
cp $GITHUB_ROOT/temporary/asset-inventory/asset_inventory_master.csv $GITHUB_ROOT/documentation/documentation_assets.csv

# Verify
wc -l $GITHUB_ROOT/documentation/documentation_assets.csv
head -2 $GITHUB_ROOT/documentation/documentation_assets.csv
```

## Related Documentation

- **User Guide**: `ASSET_MANAGEMENT_GUIDE.md` - Day-to-day usage
- **Technical Docs**: `BUILD_TIME_ALT_TEXT_INTEGRATION.md` - Build integration
- **CLAUDE.md Section**: Search for "DOCUMENTATION ASSET MANAGEMENT"
- **Scripts Directory**: `scripts/asset_management/`

---

**Last Updated**: 2025-11-19
**Maintained By**: Tallyfy Documentation Team
