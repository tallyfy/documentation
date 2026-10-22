> Source of truth for the documentation asset management system. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.

# The documentation asset management system

## DOCUMENTATION ASSET MANAGEMENT

### Overview

All documentation screenshots and media assets are hosted on Cloudflare R2 storage and served via the `screenshots.tallyfy.com` CDN. The asset management system in `scripts/asset_management/` handles uploading and inventory automatically, and captioning as a separate, human-run second phase. Captions that exist in the inventory are injected into documentation images as alt text at build time.

**🧭 Every session, know this:** `documentation_assets.csv` is the catalog of every documentation image. To find an existing image by what it shows, grep the `ai_caption_alt` / `ai_caption_descriptive` columns. To reference an image in an article, use its `production_url` (the alt text is injected automatically at build). To add a new image, first look for one to reuse (next paragraph), then run `orchestrator.py upload ...` (uploads + inventories; caption it in the same Claude Code session via native vision). To see what's missing or stale, run `orchestrator.py audit`.

**Look for an existing image before you add one.** Search `documentation_assets.csv` by what the image shows, in the `ai_caption_alt`, `ai_caption_descriptive` and `ai_caption_seo` columns. Search it by where the image is used, in `article_ids`, which holds each article's frontmatter `id` or its path slug. One plain search from the repo root covers all four columns:

```bash
rg -i "role selection" documentation_assets.csv
```

To see what an article already uses, search for its `id` the same way. If a row fits, reuse its `production_url` and check its `url_exists` reads `True`. Upload a new image only when nothing fits: a reused image is already captioned, and every new one adds an R2 object, an inventory row and three captions to write. These are this CSV's own header names. website-astro's inventory calls its columns `ai_description` and `referenced_in`, so its search commands do not work here (tallyfy/documentation#301).

**Source of truth:** `scripts/asset_management/` is the single implementation. The `documentation-asset-manager` skill (global `~/.claude/skills/` and the repo `.claude/skills/` copy) is a thin pointer to these scripts - never re-fork the code into the skill.

**📋 Build-Time Integration**: See `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md` for complete technical documentation on how AI-generated captions are automatically added as alt text during the Astro build process. The support-docs remark plugin reads `production_url` -> the three caption columns.

**🔁 Auditing & syncing the inventory** (no R2 credentials needed - read-mostly):

```bash
cd scripts/asset_management
python3 orchestrator.py audit --out /tmp/docs-audit.md   # report: referenced-not-in-inventory, dead(404), orphaned, uncaptioned
python3 orchestrator.py sync --dry-run                    # preview adding skeleton rows for referenced-not-in-inventory images
python3 orchestrator.py sync                              # apply (atomic; refreshes article refs; destructive items stay report-only)
```

`audit` scans `src/content/docs/**` for `screenshots.tallyfy.com` URLs and cross-references the CSV (URL-encoding-aware). `sync` is safe-auto: it only ADDS skeleton rows + refreshes `article_ids`; it never deletes dead/orphaned rows (those are surfaced in the report for human decision).

**🗂️ Bulk caption backlog.** Captioning hundreds of uncaptioned images is multi-hour and rate-limited, so do NOT try to caption the whole backlog in one session. The one-off asset-sync Large Job that captioned the earlier backlog is finished and its working folder is gone, so there is no runner to hand work to. Work what is left in small batches from `scripts/asset_management/`: `python3 audit_sync.py worklist --limit 10` prints the next uncaptioned image URLs (it skips the blank captures listed in `caption-skip.txt`), and `python3 orchestrator.py caption --url ...` captions one of them inside a Claude Code session. If you already have the three captions, `python3 audit_sync.py set-caption --url ... --alt ... --descriptive ... --seo ...` writes them to the CSV; like `audit` and `sync`, it never builds the R2 uploader. The CSV is the done-ledger, so a batch can stop anywhere and the next `worklist` call picks up where it left off. `python3 orchestrator.py audit` gives the full count of what is still missing.

### Asset Storage Architecture

**Storage Location**: Cloudflare R2 bucket (`screenshots`)
**Public CDN**: `https://screenshots.tallyfy.com/`
**Inventory**: `/documentation/documentation_assets.csv` (master catalog)
**Scripts Location**: `/documentation/scripts/asset_management/`

### Asset URL Patterns

**Structured Naming (Preferred)**:
```
https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-{action}-{context}.png
```

Examples:
- `tallyfy/pro/desktop-light-assign-task.png`
- `tallyfy/pro/desktop-light-sidebar-numerated.png`
- `manufactory-triggers-v2.png`

**Auto-Generated IDs** (Legacy):
```
https://screenshots.tallyfy.com/file-{randomID}.png
```

### Using the Documentation Asset Management System

The asset management scripts in `scripts/asset_management/` provide automated workflows for all asset operations:

#### Upload New Screenshot

Captioning is **two phase, on purpose**. `upload` puts the file on R2 and inventories it. It does
NOT caption. `caption` writes the caption text, and it only works inside a Claude Code session,
because that is what can actually read the image. Run both, in order:

```bash
# Phase 1: upload + inventory (no captions)
cd /documentation/scripts/asset_management
python3 orchestrator.py upload \
  --file /path/to/screenshot.png \
  --key "tallyfy/pro/desktop-light-new-feature.png" \
  --articles "pro-feature-guide,pro-getting-started"

# Phase 2: caption it, in a Claude Code session, using the URL phase 1 printed
python3 orchestrator.py caption \
  --url "https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-new-feature.png"
```

**`upload` returns**:
- Public URL: `https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-new-feature.png`
- An inventory row, with the three caption columns left **empty**
- A reminder that the image is uncaptioned until you run phase 2

An image that never gets phase 2 ships with empty alt text, so treat the pair as one task. Until
2026-08-12 `upload` printed "Generating AI captions..." and wrote three empty strings, and
`caption` printed a success tick while writing nothing at all, because it handed the generator's
`alt_text`/`descriptive`/`seo` keys to a CSV writer whose columns are `ai_caption_*` and which
drops unknown keys silently. Both now report what actually happened, and `caption` exits non-zero
when it produced nothing. See tallyfy/documentation#117.

#### Replace Existing Screenshot

```bash
# Same key overwrites existing file
cd /documentation/scripts/asset_management
python3 orchestrator.py replace \
  --file /path/to/updated-screenshot.png \
  --key "tallyfy/pro/desktop-light-existing-feature.png"
```

#### Upload Without Captions (Quick Upload)

```bash
cd /documentation/scripts/asset_management
python3 orchestrator.py upload \
  --file /path/to/screenshot.png \
  --key "tallyfy/pro/desktop-light-quick-upload.png" \
  --skip-captions
```

### AI-Generated Captions

The `caption` command writes three types of caption, and it only works inside a Claude Code
session, where the image can be read with native vision. Nothing generates these automatically:
an uploaded image has empty captions until someone runs that command. If it produces no usable
text it writes nothing and exits non-zero, rather than reporting success.

1. **Alt Text** (Accessibility):
   - Concise, 1-2 sentences
   - Describes what the image shows directly
   - No phrases like "screenshot of" or "image showing"

2. **Descriptive** (Detailed):
   - 2-4 sentences
   - Specific UI elements, functionality demonstrated
   - Key visual details and interface elements

3. **SEO** (Search Optimized):
   - Feature names, UI elements, user actions
   - Keywords for documentation search
   - Natural phrasing for search engines

### Master Asset Inventory

**Location**: `/documentation/documentation_assets.csv`

**CSV Schema**:
- `filename` - Asset filename
- `r2_key` - Full R2 bucket path
- `production_url` - Public CDN URL
- `source_type` - `native` (used in docs) | `orphaned` (not referenced) | `missing` (404)
- `file_type` - File extension
- `file_size` - Human-readable size
- `file_size_bytes` - Size in bytes
- `url_exists` - Boolean (URL accessible)
- `article_ids` - Comma-separated article IDs
- `article_count` - Number of articles referencing
- `last_modified` - Last modified timestamp
- `etag` - R2 ETag checksum
- `ai_caption_alt` - Alt text caption
- `ai_caption_descriptive` - Detailed caption
- `ai_caption_seo` - SEO-optimized caption
- `needs_caption` - `yes`|`no` (based on file type)

**Inventory snapshot** (re-derived 2026-06-02 by `orchestrator.py audit` - run it for live numbers):
- Total rows: 818
- With AI captions: 428
- Image rows still missing captions: ~350 (the `needs_caption=yes` flag was only set on 6 rows - it badly under-counts; trust `audit`, not the flag)
- Orphaned (source_type=orphaned, not referenced): 499  [GATED - human decides cleanup]
- Dead / 404 (source_type=missing): 23  [GATED]
- Referenced in docs but NOT yet inventoried: 55 images (16 `illustrations/*`, 39 `tallyfy/*`) - `sync` adds these as skeleton rows

### Credentials and Configuration

**Required Credentials**: `/cloudflare_credentials.json`

```json
{
  "account_id": "cloudflare-account-id",
  "r2_api_token": "R2-specific-api-token"
}
```

**Skill Scripts**:
- `r2_uploader.py` - Upload files to R2
- `image_captioner.py` - Generate AI captions with Claude Vision
- `asset_inventory.py` - Manage CSV inventory
- `orchestrator.py` - Complete workflow automation

### Asset Management Best Practices

#### Screenshot Naming Conventions

**DO**:
- ✅ Use descriptive, structured names: `desktop-light-assign-task.png`
- ✅ Include theme/context: `desktop-light-` or `mobile-dark-`
- ✅ Keep names under 50 characters
- ✅ Use hyphens for word separation

**DON'T**:
- ❌ Use generic names: `screenshot1.png`, `image.png`
- ❌ Include dates in filenames: `screenshot-2025-01-15.png`
- ❌ Use spaces or special characters
- ❌ Create duplicate names in different paths

#### Image Optimization

Before uploading:
1. **Resolution**: Capture at 2x resolution for Retina displays
2. **Format**: Use PNG for UI screenshots, JPG for photos/charts
3. **Compression**: Optimize file size without quality loss
4. **Cropping**: Remove unnecessary chrome/whitespace

#### Inventory Maintenance

**Regular Tasks**:
- **Weekly**: Verify inventory CSV integrity
- **Monthly**: Review orphaned assets for cleanup
- **Quarterly**: Audit missing images (404s) and fix references
- **As needed**: Regenerate captions for improved quality

**Verification Commands**:
```bash
cd /documentation/scripts/asset_management

# Check inventory statistics
python3 orchestrator.py stats

# Find specific asset
python3 asset_inventory.py find --filename "desktop-light-assign-task.png"

# Verify configuration
python3 orchestrator.py verify
```

### Troubleshooting Asset Issues

#### "Image not found" (404)

1. **Check inventory**: Verify asset exists in `documentation_assets.csv`
2. **Verify R2**: Confirm file uploaded successfully
3. **CDN propagation**: Wait 30-60s for CDN cache
4. **URL encoding**: Ensure special characters are URL-encoded

#### Upload Failures

1. **Credentials**: Verify `/cloudflare_credentials.json` exists
2. **R2 token**: Ensure `r2_api_token` has write permissions
3. **File size**: R2 has 5GB single file limit
4. **Network**: Check connection to Cloudflare

#### Caption Generation Issues

1. **Claude Code**: Captions use native Claude vision (no external API needed)
2. **Image format**: Supports PNG, JPG, GIF, WEBP
3. **File accessibility**: Image must be downloadable from URL
4. **Rate limits**: Automatic 1-2 second delays between captions

### Automated Workflows

#### Batch Upload Multiple Screenshots

```bash
#!/bin/bash
# Upload all screenshots in directory
cd /documentation/scripts/asset_management

for img in /docs/screenshots/*.png; do
    filename=$(basename "$img")
    python3 orchestrator.py upload \
        --file "$img" \
        --key "tallyfy/pro/$filename" \
        --skip-captions  # Generate captions separately for batch
    sleep 2  # Rate limiting
done
```

#### Generate Captions for Existing Assets

```bash
# Regenerate captions for specific image
cd /documentation/scripts/asset_management
python3 orchestrator.py caption \
    --url "https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-tasks.png"
```

#### Cleanup Orphaned Assets

```bash
# List orphaned assets (not referenced in any documentation)
cd /documentation/scripts/asset_management
python3 asset_inventory.py stats
```

### Integration with Documentation Workflow

#### In Article Creation

When adding screenshots to articles:

1. **Capture screenshot** at appropriate resolution
2. **Upload via orchestrator**: Use asset management system for complete workflow
3. **Copy public URL**: Use returned `production_url` in markdown
4. **Use AI captions**: AI-generated alt text is automatically injected at build time

Example in MDX:
```markdown
![Task assignment interface](https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-assign-task.png)
```

#### In Article Updates

When replacing outdated screenshots:

1. **Use same R2 key**: Maintains URL consistency
2. **Regenerate captions**: Ensure descriptions match new image
3. **Update inventory**: Automatic via orchestrator
4. **No markdown changes needed**: URL remains the same

### Asset Security and Access Control

**R2 Bucket Configuration**:
- Private bucket with custom domain mapping
- Public read access via `screenshots.tallyfy.com`
- Write access restricted to authenticated API tokens
- No direct bucket URL exposure

**API Token Management**:
- R2-specific tokens stored in parent directory
- Skill reads credentials via relative path (`../cloudflare_credentials.json`)
- No credentials embedded in skill files
- Token permissions: Object Read & Write on `screenshots` bucket only

### Future Enhancements

**Planned Features**:
- Automatic screenshot version history
- Bulk caption regeneration workflows
- Asset usage analytics across documentation
- Automated orphan cleanup scheduling
- Integration with documentation build process
