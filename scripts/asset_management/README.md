# Documentation Asset Management System

Automated system for managing screenshots and images in Tallyfy documentation, including R2 uploads, AI caption generation, and inventory tracking.

## 🚀 Quick Start

### 1. Installation

```bash
cd /documentation/scripts/asset_management

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and add your Cloudflare credentials:

```env
CLOUDFLARE_ACCOUNT_ID=your_account_id_here
CLOUDFLARE_R2_TOKEN=your_r2_api_token_here
```

**Where to find these**:
- Account ID: Cloudflare Dashboard > R2 > Settings
- R2 Token: Cloudflare Dashboard > My Profile > API Tokens > Create Token
  - Permissions: R2 Read & Write for "screenshots" bucket

### 3. Verify Setup

```bash
python orchestrator.py verify
```

You should see:
```
✅ Configuration is valid and complete
```

## 📖 Usage

### Upload New Screenshot

```bash
python orchestrator.py upload \
  --file ~/Desktop/screenshot.png \
  --key "tallyfy/pro/feature-name.png" \
  --articles "pro-features,pro-getting-started"
```

**Returns**:
- Public URL: `https://screenshots.tallyfy.com/tallyfy/pro/feature-name.png`
- Automatically adds to inventory
- Generates AI captions (when run via Claude Code)

### Replace Existing Screenshot

```bash
python orchestrator.py replace \
  --file ~/Desktop/updated-screenshot.png \
  --key "tallyfy/pro/existing-feature.png"
```

**Benefits**:
- Same URL (no documentation updates needed)
- Preserves article associations
- Regenerates captions automatically

### Generate Captions for Existing Image

```bash
python orchestrator.py caption \
  --url "https://screenshots.tallyfy.com/tallyfy/pro/image.png"
```

### View Inventory Statistics

```bash
python orchestrator.py stats
```

**Shows**:
- Total assets count
- Assets with/without AI captions
- Orphaned assets (not referenced in docs)
- Missing assets (404s)
- Breakdown by file type and source

## 🏗️ Architecture

### System Components

```
orchestrator.py       Main CLI - coordinates complete workflow
├── r2_uploader.py   Uploads files to Cloudflare R2
├── image_captioner.py   Generates AI captions (via Claude Code)
├── asset_inventory.py   Manages CSV inventory
└── config.py        Configuration loader

Data Flow:
  upload → caption → inventory → documentation_assets.csv
```

### Inventory CSV Schema

The master inventory at `/documentation/documentation_assets.csv` contains:

- `filename` - Asset filename
- `r2_key` - Full R2 bucket path
- `production_url` - Public CDN URL
- `source_type` - `native` | `orphaned` | `missing`
- `file_type` - File extension
- `file_size` - Human-readable size
- `file_size_bytes` - Size in bytes
- `url_exists` - Boolean (URL accessible)
- `article_ids` - Comma-separated article IDs
- `article_count` - Number of articles referencing
- `last_modified` - Last modified timestamp
- `etag` - R2 ETag checksum
- `ai_caption_alt` - Alt text caption (accessibility)
- `ai_caption_descriptive` - Detailed caption
- `ai_caption_seo` - SEO-optimized keywords
- `needs_caption` - `yes` | `no`

## 🎨 AI Caption Generation

### Caption Types

1. **Alt Text** (Accessibility)
   - 1-2 sentences, 50-150 characters
   - Direct description of interface
   - No "screenshot of" phrases
   - Example: `"Task assignment interface with role and user selection dropdown menus"`

2. **Descriptive** (Detailed)
   - 2-4 sentences
   - Specific UI elements and functionality
   - Mentions Tallyfy features
   - Example: `"Tallyfy task assignment screen showing dropdown options..."`

3. **SEO** (Keywords)
   - 15-30 words
   - Feature names, UI elements, actions
   - Natural phrasing
   - Example: `"assign tasks Tallyfy role-based assignment user group workflow"`

### How Captions Work

**Important**: Caption generation requires Claude Code execution context.

When you run `orchestrator.py` from within Claude Code:
1. Image is analyzed using Claude's vision capabilities
2. Three specialized prompts generate each caption type
3. Captions are automatically added to inventory CSV
4. Build-time integration injects alt text into documentation

## 🔧 Individual Module Usage

### R2 Uploader (Standalone)

```bash
python r2_uploader.py screenshot.png "tallyfy/pro/image.png"
```

### Asset Inventory (Standalone)

```bash
# View stats
python asset_inventory.py stats

# Find asset
python asset_inventory.py find --url "https://screenshots.tallyfy.com/image.png"

# Verify URLs
python asset_inventory.py verify --limit 100
```

### Image Captioner (Standalone)

```bash
python image_captioner.py screenshot.png --types alt_text descriptive seo
```

## 📁 File Structure

```
scripts/asset_management/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── .env.example           # Credentials template
├── .env                   # Your credentials (gitignored)
├── config.py              # Configuration loader
├── orchestrator.py        # Main CLI interface
├── r2_uploader.py         # R2 upload functionality
├── image_captioner.py     # AI caption generation
└── asset_inventory.py     # Inventory management
```

## 🔒 Security & Credentials

### Credential Sources (Priority Order)

1. `.env` file in this directory
2. Environment variables
3. Parent `/cloudflare_credentials.json`

### Required Credentials

```env
# Minimum required
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_R2_TOKEN=xxx

# Optional
CLOUDFLARE_API_TOKEN=xxx  # For general API operations
R2_BUCKET_NAME=screenshots  # Override default
R2_PUBLIC_URL=https://screenshots.tallyfy.com  # Override default
```

### Security Best Practices

- ✅ `.env` is gitignored automatically
- ✅ Credentials never committed to repository
- ✅ Use R2-specific tokens (not account-wide)
- ✅ Rotate tokens periodically
- ❌ Never share credentials in chat/email

## 🐛 Troubleshooting

### Configuration Errors

```bash
# Check configuration
python orchestrator.py verify

# Common issues:
# - CLOUDFLARE_ACCOUNT_ID missing
# - CLOUDFLARE_R2_TOKEN missing
# - Inventory CSV not found
```

### Upload Failures

**Error: 403 Forbidden**
- Check R2 token has write permissions
- Verify token not expired
- Confirm bucket name is correct

**Error: File not found**
- Use absolute paths for file uploads
- Check file actually exists

### Caption Generation Issues

**Captions showing as placeholders**
- Caption generation requires Claude Code execution
- Run orchestrator via: `claude -p "Upload screenshot.png..."`
- Not available when running Python directly

### Inventory Issues

**Asset not found**
- Check URL encoding matches
- Try searching by r2_key instead of URL
- Verify CSV file is up-to-date

## 📚 Related Documentation

- `/documentation/ASSET_MANAGEMENT_GUIDE.md` - Complete user guide
- `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md` - Technical details
- `/documentation/CLAUDE.md` - AI assistant guidelines (includes asset management)

## 🤝 Contributing

When adding new features:

1. Update all affected modules
2. Add error handling and logging
3. Update this README
4. Test with `orchestrator.py verify`
5. Update parent documentation guides

## 📊 System Statistics

Current inventory (as of migration):
- **Total assets**: 812
- **With AI captions**: 428
- **Active (in docs)**: 290
- **Orphaned**: 499
- **Missing (404s)**: 23

## 🆘 Getting Help

**For asset management issues**:
1. Run `python orchestrator.py verify`
2. Check `.env` file exists and has valid credentials
3. Review error messages (usually indicate missing config)

**For caption quality issues**:
1. Captions are AI-generated - review and edit in CSV if needed
2. Regenerate with `python orchestrator.py caption --url "..."`
3. Manual edits to CSV persist across builds

**For build integration issues**:
1. See `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md`
2. Check `/support-docs/src/plugins/remark-inject-alt-text.ts`
3. Verify CSV synced to support-docs repository

---

**Last Updated**: 2025-11-23
**Version**: 1.0.0
**Maintainers**: Tallyfy Documentation Team
