# Documentation Asset Management - User Guide

> **Path Convention**: This guide uses `$GITHUB_ROOT` to represent your GitHub workspace directory. Replace with your actual path (e.g., `/Users/username/GitHub` or `~/GitHub`) when using these commands. All skill scripts automatically detect paths relative to their location.

## Quick Start

This guide shows you how to add, update, and manage screenshots and images in the Tallyfy documentation using the automated asset management system.

## Table of Contents

1. [Adding a New Screenshot](#adding-a-new-screenshot)
2. [Replacing an Existing Screenshot](#replacing-an-existing-screenshot)
3. [Finding Image URLs](#finding-image-urls)
4. [Understanding AI-Generated Captions](#understanding-ai-generated-captions)
5. [Using Images in Documentation](#using-images-in-documentation)
6. [Troubleshooting Common Issues](#troubleshooting-common-issues)
7. [Advanced Usage](#advanced-usage)

---

## Adding a New Screenshot

### Step 1: Capture Your Screenshot

1. **Take the screenshot** at high resolution (preferably 2x for Retina displays)
2. **Save as PNG** for UI screenshots (or JPG for photos/diagrams)
3. **Name descriptively**: Use `desktop-light-{action}-{context}.png` pattern

**Example filenames**:
- `desktop-light-assign-task.png` - Good ✅
- `desktop-light-settings-integrations.png` - Good ✅
- `screenshot1.png` - Bad ❌ (not descriptive)

### Step 2: Upload to R2 with AI Captions

Run the orchestrator script to upload, generate captions, and update inventory:

```bash
python3 scripts/asset_management/orchestrator.py \
  --file /path/to/your/screenshot.png \
  --key "tallyfy/pro/desktop-light-your-feature.png" \
  --article-ids "article-id-1,article-id-2"
```

**Parameters explained**:
- `--file`: Path to your screenshot file
- `--key`: R2 storage path (creates URL: `https://screenshots.tallyfy.com/{key}`)
- `--article-ids`: Comma-separated list of article IDs where this image is used

**Example**:
```bash
python3 scripts/asset_management/orchestrator.py \
  --file ~/Desktop/desktop-light-create-template.png \
  --key "tallyfy/pro/desktop-light-create-template.png" \
  --article-ids "pro-templates-overview,pro-getting-started"
```

### Step 3: Copy the Public URL

The script returns the public URL:
```
✅ Upload successful
📷 Public URL: https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-create-template.png
```

### Step 4: Add to Your Documentation

Use standard markdown image syntax in your MDX file:

```markdown
![Template creation interface](https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-create-template.png)
```

**Note**: You can use any alt text here - it will be automatically replaced with the AI-generated caption during the build process.

---

## Replacing an Existing Screenshot

When you need to update an outdated screenshot:

### Option 1: Replace with Same Key (Recommended)

Using the **same R2 key** keeps the URL consistent:

```bash
python3 scripts/asset_management/orchestrator.py \
  --file ~/Desktop/updated-screenshot.png \
  --key "tallyfy/pro/desktop-light-existing-feature.png" \
  --article-ids "existing-article-ids"
```

**Benefits**:
- ✅ URL stays the same - no need to update documentation
- ✅ Old image is automatically overwritten
- ✅ New captions generated for updated interface
- ✅ Inventory automatically updated

### Option 2: Upload with New Key

If the screenshot shows a significantly different feature:

```bash
python3 scripts/asset_management/orchestrator.py \
  --file ~/Desktop/new-screenshot.png \
  --key "tallyfy/pro/desktop-light-new-feature-name.png" \
  --article-ids "article-id"
```

Then update the markdown image URL in your documentation.

---

## Finding Image URLs

### Find Images in Documentation

Search for image URLs in documentation:

```bash
cd $GITHUB_ROOT/documentation
grep -r "screenshots.tallyfy.com" src/content/docs/pro --include="*.mdx"
```

### Check Inventory for Specific Image

```bash
cd $GITHUB_ROOT
grep "desktop-light-assign-task" documentation_assets.csv
```

### View All Images for an Article

```bash
cd $GITHUB_ROOT
grep "article-id-here" documentation_assets.csv
```

---

## Understanding AI-Generated Captions

The system generates **three types of captions** for every image:

### 1. Alt Text (`ai_caption_alt`)

**Purpose**: Accessibility (screen readers)
**Length**: 1-2 sentences (50-150 characters)
**Style**: Concise, direct description

**Example**:
```
Task assignment interface with role and user selection dropdown menus
```

**Where used**: Automatically injected as image `alt` attribute at build time

### 2. Descriptive Caption (`ai_caption_descriptive`)

**Purpose**: Detailed context and explanation
**Length**: 2-4 sentences
**Style**: Includes UI elements, functionality, visual details

**Example**:
```
Tallyfy task assignment screen showing dropdown options to assign by specific user,
role, or group. The interface displays deadline settings, priority levels, and an
optional notification toggle. Assignment can be made to multiple users simultaneously
with role-based dynamic routing.
```

**Where used**: Available for future use (tooltips, figcaptions, structured data)

### 3. SEO Caption (`ai_caption_seo`)

**Purpose**: Search engine optimization
**Length**: Keywords and phrases
**Style**: Feature names, UI elements, actions

**Example**:
```
assign tasks Tallyfy role-based assignment user assignment group assignment workflow
management task routing deadline setting priority levels
```

**Where used**: Available for future SEO integration (meta tags, structured data)

### How Captions are Generated

1. **Image uploaded** to R2 bucket
2. **Claude Vision analyzes** the screenshot
3. **Three specialized prompts** generate each caption type:
   - Alt text: Focus on conciseness and directness
   - Descriptive: Focus on detail and context
   - SEO: Focus on keywords and searchability
4. **Captions stored** in master CSV inventory
5. **Alt text automatically injected** into documentation at build time

---

## Using Images in Documentation

### Basic Image Syntax

```markdown
![Any alt text here](https://screenshots.tallyfy.com/path/to/image.png)
```

**Important**: The alt text you write will be replaced with AI-generated caption during build.

### Best Practices

✅ **DO**:
- Use descriptive filenames in R2 key
- Include images only when they add value
- Keep images focused on specific features
- Use PNG for UI screenshots, JPG for photos
- Upload at 2x resolution for Retina displays

❌ **DON'T**:
- Use generic filenames like `image1.png`
- Include unnecessary whitespace in screenshots
- Upload unoptimized large files
- Hardcode specific alt text (it will be replaced)

### Image Sizing and Optimization

**Before uploading**:
1. Crop to remove unnecessary chrome/whitespace
2. Use PNG format for screenshots
3. Optimize file size (most screenshots should be < 200KB)
4. Ensure text is legible at standard size

---

## Troubleshooting Common Issues

### Image Not Displaying (404 Error)

**Check 1**: Verify URL is correct
```bash
curl -I https://screenshots.tallyfy.com/your-image-path.png
```

**Check 2**: Verify file exists in inventory
```bash
grep "your-image-path.png" $GITHUB_ROOT/documentation/documentation_assets.csv
```

**Check 3**: Wait for CDN propagation (30-60 seconds after upload)

**Solution**: Re-upload the image with correct R2 key

### Upload Failed

**Error**: `Authentication error` or `403 Forbidden`

**Cause**: Missing or invalid R2 API credentials

**Solution**: Verify `$GITHUB_ROOT/cloudflare_credentials.json` exists and contains:
```json
{
  "account_id": "your-account-id",
  "r2_api_token": "your-r2-token"
}
```

### Captions Not Generating

**Error**: `Caption generation failed`

**Common causes**:
1. Image file not accessible (check file path)
2. Unsupported image format (use PNG or JPG)
3. File too large (R2 limit is 5GB, but aim for < 5MB)
4. Network issues downloading image

**Solution**:
```bash
# Skip captions and upload only
python3 scripts/asset_management/orchestrator.py \
  --file /path/to/image.png \
  --key "tallyfy/pro/image.png" \
  --skip-captions
```

Then generate captions separately:
```bash
python3 scripts/asset_management/image_captioner.py \
  --url "https://screenshots.tallyfy.com/tallyfy/pro/image.png" \
  --type all
```

### Alt Text Not Updating in Built Site

**Issue**: Markdown alt text shows instead of AI caption

**Causes**:
1. Remark plugin not registered in `astro.config.mjs`
2. CSV inventory not accessible during build
3. URL mismatch (encoding differences)

**Solution**: Verify build-time integration:
1. Check `/support-docs/documentation_assets.csv` exists
2. Verify plugin in `/support-docs/src/plugins/remark-inject-alt-text.ts`
3. Confirm plugin registered in `/support-docs/astro.config.mjs`
4. Check build logs for `[remark-inject-alt-text]` messages

### Image URL Encoding Issues

**Problem**: URL works but inventory lookup fails

**Cause**: URL encoding mismatch (` ` vs `%20`, `/` vs `%2F`)

**Solution**: The remark plugin tries three match strategies:
1. Direct match
2. URL-decoded match
3. URL-encoded match

Verify URL in CSV matches exactly how it appears in markdown.

---

## Advanced Usage

### Batch Upload Multiple Screenshots

Upload all screenshots in a directory:

```bash
#!/bin/bash
for img in ~/Desktop/screenshots/*.png; do
    filename=$(basename "$img" .png)
    python3 scripts/asset_management/orchestrator.py \
        --file "$img" \
        --key "tallyfy/pro/$filename.png" \
        --article-ids "batch-upload" \
        --skip-captions  # Skip for faster batch processing
    echo "✅ Uploaded: $filename"
    sleep 1  # Rate limiting
done
```

Then generate captions for batch:
```bash
#!/bin/bash
cd $GITHUB_ROOT
cat documentation_assets.csv | grep "batch-upload" | while IFS=',' read -r url rest; do
    python3 scripts/asset_management/image_captioner.py \
        --url "$url" \
        --type all
    sleep 2
done
```

### Regenerate Captions for Better Quality

If you want to improve caption quality with a better prompt:

```bash
python3 scripts/asset_management/image_captioner.py \
  --url "https://screenshots.tallyfy.com/tallyfy/pro/image.png" \
  --type alt_text \
  --custom-prompt "Generate alt text focusing on accessibility for visually impaired users"
```

### Export Captions to Different Format

Convert CSV inventory to JSON for programmatic use:

```python
#!/usr/bin/env python3
import csv
import json

with open('$GITHUB_ROOT/documentation/documentation_assets.csv', 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    assets = [row for row in reader]

with open('assets_export.json', 'w') as jsonfile:
    json.dump(assets, jsonfile, indent=2)
```

### Find Orphaned Assets (Not Used in Documentation)

Images uploaded but not referenced anywhere:

```bash
cd $GITHUB_ROOT
grep '"orphaned"' documentation_assets.csv | cut -d',' -f1-3
```

### Find Missing Images (404s)

Images referenced in documentation but not found:

```bash
cd $GITHUB_ROOT
grep '"missing"' documentation_assets.csv
```

### Inventory Statistics

View asset statistics:

```bash
cd $GITHUB_ROOT
python3 -c "
import csv
with open('documentation_assets.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    total = len(rows)
    active = len([r for r in rows if r['source_type'] == 'native'])
    orphaned = len([r for r in rows if r['source_type'] == 'orphaned'])
    missing = len([r for r in rows if r['source_type'] == 'missing'])
    with_captions = len([r for r in rows if r['ai_caption_alt']])

    print(f'Total assets: {total}')
    print(f'Active (used in docs): {active}')
    print(f'Orphaned (not referenced): {orphaned}')
    print(f'Missing (404): {missing}')
    print(f'With AI captions: {with_captions}')
"
```

---

## Quick Reference

### Common Commands

**Upload new screenshot**:
```bash
python3 scripts/asset_management/orchestrator.py \
  --file /path/to/image.png \
  --key "tallyfy/pro/feature-name.png" \
  --article-ids "article-1,article-2"
```

**Replace existing (same URL)**:
```bash
python3 scripts/asset_management/orchestrator.py \
  --file /path/to/updated-image.png \
  --key "tallyfy/pro/existing-feature.png" \
  --article-ids "article-1"
```

**Generate captions only**:
```bash
python3 scripts/asset_management/image_captioner.py \
  --url "https://screenshots.tallyfy.com/path/to/image.png" \
  --type all
```

**Find image in inventory**:
```bash
grep "feature-name" $GITHUB_ROOT/documentation/documentation_assets.csv
```

**Check upload statistics**:
```bash
wc -l $GITHUB_ROOT/documentation/documentation_assets.csv
```

### File Locations

| Item | Location |
|------|----------|
| **Master inventory** | `$GITHUB_ROOT/documentation/documentation_assets.csv` |
| **Skill scripts** | `scripts/asset_management/` |
| **Credentials** | `$GITHUB_ROOT/cloudflare_credentials.json` |
| **Documentation files** | `$GITHUB_ROOT/documentation/src/content/docs/` |
| **Build integration docs** | `$GITHUB_ROOT/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md` |

### URL Patterns

- **Public CDN**: `https://screenshots.tallyfy.com/{r2_key}`
- **Structured naming**: `tallyfy/{product}/{theme}-{action}-{context}.png`
- **Example**: `https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-assign-task.png`

### Caption Types

| Type | Purpose | Length | Where Used |
|------|---------|--------|------------|
| **Alt Text** | Accessibility | 1-2 sentences | Auto-injected as `alt` attribute |
| **Descriptive** | Detailed context | 2-4 sentences | Future use (tooltips, captions) |
| **SEO** | Search optimization | Keywords | Future use (meta tags, structured data) |

---

## Getting Help

### Documentation Resources

- **Technical details**: `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md`
- **CLAUDE.md asset section**: `/documentation/CLAUDE.md` (search for "ASSET MANAGEMENT")
- **Scripts README**: `/documentation/scripts/asset_management/README.md`

### Common Questions

**Q: Do I need to write alt text in markdown?**
A: No, it's automatically replaced with AI-generated caption during build. But you can write placeholder text for context.

**Q: How long does caption generation take?**
A: 2-5 seconds per image using Claude Vision.

**Q: Can I edit the AI-generated captions?**
A: Yes, edit the CSV file directly and rebuild the site. Future builds will use your edited caption.

**Q: What if I don't like the generated caption?**
A: Regenerate with a custom prompt, or manually edit the CSV `ai_caption_alt` field.

**Q: How do I delete an image?**
A: Currently manual via R2 dashboard. Remove from CSV and documentation references.

**Q: Can I use this for non-screenshot images?**
A: Yes! Works for any PNG, JPG, GIF, or WEBP image.

---

## Workflow Summary

```
1. Capture screenshot → 2. Upload with orchestrator → 3. Get public URL →
4. Add to documentation → 5. Build site → 6. AI caption automatically appears
```

**Time savings**: ~5 minutes per image (no manual caption writing, instant hosting, automatic inventory tracking)

**Quality benefits**: Consistent, accessible, SEO-optimized captions for all images

---

**Last Updated**: 2025-11-19
**Version**: 1.0.0
**Maintained By**: Tallyfy Documentation Team
