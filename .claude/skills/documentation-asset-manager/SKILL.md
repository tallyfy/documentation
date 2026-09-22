---
name: documentation-asset-manager
description: Manages Tallyfy documentation image assets on Cloudflare R2 (screenshots.tallyfy.com) - upload and inventory, then captioning as a separate second phase that must run inside a Claude Code session (uploading does NOT caption), plus the documentation_assets.csv inventory (audit/sync + build-time alt-text injection). Use when managing docs screenshots, captions, or the asset inventory.
version: 3.0.0
author: Tallyfy Dev Team
---

# Documentation Asset Manager (repo pointer)

The maintained implementation is in this repo at **`scripts/asset_management/`** (single source of truth). Run it directly:

```bash
cd scripts/asset_management
python3 orchestrator.py audit --out /tmp/docs-audit.md   # read-only audit
python3 orchestrator.py sync --dry-run                    # safe-auto inventory sync (preview)
python3 orchestrator.py upload --file shot.png --key "tallyfy/pro/x.png" --articles "id1"
python3 orchestrator.py caption --url "https://screenshots.tallyfy.com/tallyfy/pro/x.png"
python3 orchestrator.py stats | verify | replace
```

⚠️ **`upload` does not caption, and never did.** It uploads and inventories; the row's three
caption columns are left empty, so the image ships with empty alt text until you run `caption`
for it in a Claude Code session. Treat the two as one task. Until 2026-08-12 both commands
claimed otherwise, and `caption` in particular printed a success tick while writing nothing
(tallyfy/documentation#117).

`audit` and `sync` need no R2 credentials. `upload` and `replace` do, and `config.py` loads them.

The inventory is `documentation_assets.csv` at the repo root (16 columns). Captions reach the published docs at build time through the support-docs remark plugin, which reads `production_url` and the three `ai_caption_*` columns.

Full architecture, CSV schema, captioning rules, and the build-time alt-text injection are documented in this repo's **`CLAUDE.md` → "DOCUMENTATION ASSET MANAGEMENT"**. The one-off asset-sync Large Job that captioned the backlog is finished and its working folder is gone, so there is no runner to hand work to. Find any image still missing a caption with `python3 orchestrator.py audit` and caption it with `python3 orchestrator.py caption --url ...` inside a Claude Code session. This file is a pointer only - do not add a duplicate script fork here.
