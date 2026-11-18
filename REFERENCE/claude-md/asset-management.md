> Source of truth for the documentation asset management system. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.

# The documentation asset management system

## DOCUMENTATION ASSET MANAGEMENT

### Overview

All documentation screenshots and media assets are hosted on Cloudflare R2 storage and served via the `screenshots.tallyfy.com` CDN. The asset management system in `scripts/asset_management/` handles uploading and inventory automatically, and captioning as a separate, human-run second phase. Captions that exist in the inventory are injected into documentation images as alt text at build time.

**🧭 Every session, know this:** `documentation_assets.csv` is the catalog of every documentation image. To find an existing image by what it shows, grep the `ai_caption_alt` / `ai_caption_descriptive` columns. To reference an image in an article, use its `production_url` (the alt text is injected automatically at build). To add a new image, first look for one to reuse (next paragraph), then run `orchestrator.py upload ...` (uploads + inventories; caption it in the same Claude Code session via native vision). To see what's missing or stale, run `orchestrator.py audit`.

**A caption in the CSV always wins over alt text written in the page.** The build replaces a markdown image's alt text with its `ai_caption_alt` whenever the CSV has one. It keeps the page's alt only when the image has no row or an empty caption, and a JSX `<img>` always keeps its own. Measured on 2026-10-22, 353 of the 388 markdown images on `main` carried page alt text that differed from the CSV and never rendered. So to change what a screen reader hears, edit the CSV row, not the page. The owner chose this on 2026-10-22 over letting page alt text win, because the CSV captions were written by looking at each image (tallyfy/documentation#387).

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

Since 2026-11-05 (#462) `audit` also finds images an article links by repository path (`/screenshots/...`), matches them to rows by `repo_path`, and lists any path with no row on its own. `sync` leaves those paths alone, because their rows belong to the job that uploads them. A skeleton row `sync` adds gets `source=legacy-unknown`.

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

`upload` records `source=manual` and the SHA-256 of the bytes it sent in `content_sha256`. It
refuses any key under `launchbrightly/`, which is kept for LaunchBrightly images the pipeline
uploads from `screenshots/launchbrightly/` (#462).

#### Replace Existing Screenshot

```bash
# Same key overwrites existing file
cd /documentation/scripts/asset_management
python3 orchestrator.py replace \
  --file /path/to/updated-screenshot.png \
  --key "tallyfy/pro/desktop-light-existing-feature.png"
```

When the new bytes differ from the old ones, `replace` clears the three caption columns, sets
`needs_caption=yes` and prints the caption command, so `worklist` and `audit` offer the image
again. It compares `content_sha256`, or the etag for a row that has no hash yet, and treats the
image as changed when the row has neither. Pass `--keep-captions` when the swap is cosmetic and
the captions still describe the image. `upload` to a key that already has a row does the same.
Until 2026-11-05 (#462) a replaced image kept its old captions and was never queued again.

#### What LaunchBrightly makes

LaunchBrightly makes product screenshots for the product manual, which is this repository's
articles, and none for the website (owner decision 2026-11-16, #542).

In the manual, LaunchBrightly makes only the main shots of a page. Smaller views and places are
not LaunchBrightly's. Until another way to show them exists, nothing changes in how screenshots
are made.

#### Screenshots committed to this repository (LaunchBrightly)

Since 2026-11-06 (#464) an image can also live in this repository. LaunchBrightly, a screenshot
service, opens pull requests that add images under `screenshots/launchbrightly/` and point
article images at them by repository path:

```markdown
![Task list with due dates](/screenshots/launchbrightly/tasks/task-list.png)
```

How such a pull request flows:

1. The "LaunchBrightly PR guard" job in `pr-validate.yml` runs `scripts/lb-pr-guard.py` on
   GitHub's test merge. A pull request from the LaunchBrightly app (`launchbrightly[bot]`) may
   only add, change or delete images under `screenshots/launchbrightly/` and change image lines
   in existing articles. Each line it adds to an article must be blank or one image on its own
   line, with alt text that is not empty and does not name LaunchBrightly. Each line it removes
   must be blank or hold an image. It may never touch `documentation_assets.csv`. For every pull
   request, each `/screenshots/` link must name a file in the merged tree, and anyone else who
   touches the folder gets a warning, because pages showing those images credit LaunchBrightly.
   The job runs the base branch's copy of the guard, so a pull request cannot edit its own check.
   Dated 2026-11-17 (#548): a pull request into a branch that has no guard yet runs its own copy,
   except one by their app, which is refused. The deciding step runs before any code from the pull
   request does. The job is now named "LaunchBrightly PR guard (#<number> into <base>)" after the pull request
   and the base it judged, so the push gate trusts only "LaunchBrightly PR guard (#N into staging)"
   for pull request #N. The workflow's concurrency group is keyed on the pull request number, so
   another pull request from a branch of the same name cannot cancel that run.
2. After the merge into `staging`, the `repo-screenshots` pipeline job runs
   `scripts/asset_management/repo_screenshots.py ingest`. It uploads each new or changed image to
   screenshots.tallyfy.com under a key carrying the first 12 hex characters of its SHA-256, such
   as `launchbrightly/tasks/task-list.0123456789ab.png`, reads it back from the public URL and
   compares the hash. Then it writes the row: `source=launchbrightly`, `repo_path`,
   `content_sha256`, `production_url`, where the image is used, and the page's alt text in
   `markdown_alt`. It commits only the CSV, as "Inventory repository screenshots", and commits
   nothing when nothing changed.
3. The support-docs build is to swap each `/screenshots/...` link for its row's
   `production_url`, and fail on a link with no row. That resolver was not on support-docs
   `staging` on 2026-11-06, so no article may link a `/screenshots/` path until it is.
4. On `main` the job only checks that every linked image has a row whose hash matches its bytes,
   and that its public URL serves those bytes. It never uploads from `main`.
5. Ship each LaunchBrightly pull request to tallyfy.com as it arrives (owner decision
   2026-11-13). Once it is reviewed, merged into `staging` and showing on staging.tallyfy.com,
   promote it to `main` with a subset ship, as `linking-and-deployment.md` section "Deploying
   staging to production" says. The image it replaces stays on screenshots.tallyfy.com, because
   old image URLs keep working. Their screenshots show the next-gen client, so a page can show
   next-gen screens while customers still use the legacy app. The owner accepted that.
   Dated 2026-11-17 (#548): their app may now merge its own pull request into `staging` itself,
   once the guard has finished and passed against `staging` (see "The push gate" below). A merge
   before that stops the pipeline until the guard has passed and the run is started again, or a
   person accepts it. So the review in this step happens on staging.tallyfy.com after that merge,
   before the promotion to `main`.

The file rules live in `scripts/asset_management/repo_screenshot_rules.py`, shared by the guard
and the job:

- PNG, JPEG, GIF or WebP, judged by the file's first bytes, and the extension must agree. No SVG.
  At most 3 MiB. Nothing else may sit under `screenshots/`.
- Names are lower case letters, digits and hyphens, in folders named the same way.
- An image may have a sidecar beside it, the same name ending `.json`, of at most 8 KB. Its keys
  are `title`, `screen`, `description`, `app_url`, `captured_at` (ISO 8601) and `recipe_id`;
  other keys are ignored with a notice. `app_url` is stored as a path, and a full URL must be on
  tallyfy.com. `screen` (or else `title`) fills `app_screen`, `description` fills
  `source_description`, `recipe_id` fills `source_ref`, and `location_source` becomes
  `launchbrightly`. With no sidecar, `app_screen` is the article title plus the nearest heading
  above the image, and `location_source` is `inferred`.

Nothing is ever deleted from R2. A changed image gets a new key, and its old URL keeps working.
When the bytes change, the three captions are cleared and `needs_caption` becomes `yes`, so
`worklist` offers the image again; `captured_at`, `source_description`, `source_ref` and
`app_url` are cleared too unless the sidecar gives new values. A file deleted from git keeps
its row, marked `orphaned`. Any problem (a bad file, a link to a missing file, a failed upload
or read-back) fails the job before the CSV is written, so `staging` stays as it was and `sync`
does not publish. The job also refuses to run when any commit to `documentation_assets.csv` was
authored by LaunchBrightly, because the guard should have stopped it. A revert does not clear
that, since the commit stays in history. After reading such a commit and reverting any wrong
rows, a person adds its full SHA to `scripts/asset_management/launchbrightly-csv-reviewed.txt`,
and the next run goes ahead. A line there that is not a full SHA stops the job (exit 2). The
LaunchBrightly PR guard refuses their pull requests that touch `scripts/`, so they cannot add
to it themselves.

The upload credentials are `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and
`CLOUDFLARE_ACCOUNT_ID` in the `r2-screenshots` GitHub environment: an R2 token scoped to the
`screenshots` bucket, used through R2's S3-compatible API with boto3. The Cloudflare REST
objects API that `r2_uploader.py` uses refuses a bucket-scoped token (403 on get, head and list,
measured 2026-11-06), which is why this job does not use `r2_uploader.py`. The three secrets
reach one step, the staging ingest. `scripts/pipeline-guard.py --check-wiring` fails if a
workflow a pull request starts names a secret or an environment, if anything but this job names
the environment, or if the secrets reach any other step.

##### The push gate

The LaunchBrightly app can write to the repository, so it could push to `staging` or `main`
without a pull request, and GitHub would not let a ruleset stop that without also stopping the
pipeline's own pushes (owner decision 2026-11-06). So a `push-gate` job runs first in
`generate-ids.yml` and in `documentation-pipeline.yml`, and every job that holds a secret, an
environment or a push waits for it. It runs no code from the repository, only an inline script
in the workflow, the same in both files, which an app without the workflows permission cannot
change.

It reads the commits from the head of the last successful `generate-ids.yml` run on the branch
through this run's head, at most 250. A commit stops the run when a bot other than
github-actions[bot] and tallyfy-workhorse[bot] authored or committed it and no merged pull
request has it as its merge commit. So a squash-merged LaunchBrightly pull request passes, and a
LaunchBrightly pull request merged with a merge commit or a rebase does not, because its own
commits then sit on the branch outside a merge commit: squash-merge them. A push or merge by such
a bot also stops the run, read from the repository activity API, which records who pushed whatever
the commit says about who wrote it. When the gate cannot read something, it fails.

One exception (#548): LaunchBrightly's merge of its own pull request into `staging`. On
`staging`, a commit LaunchBrightly (`launchbrightly[bot]`, user id 270903805) authored or
committed passes only as the merge commit of its own pull request #N into `staging`, when, of the
`pr-validate.yml` runs on that pull request's head, the newest one that has a job named
"LaunchBrightly PR guard (#N into staging)" shows that job passed. A run without that job is
passed over: it is another pull request's run on the same commit, which anyone can open in a
public repository, or a run that has not started its jobs, such as one waiting for approval. The
number and base in the job's name are the ones the guard judged, so a pass for another pull
request with the same head, or one recorded before the base was changed to `staging`, does not
count. The gate reads it from the Actions API (workflow runs and their jobs, with
`actions: read`), because a job is defined by the workflow file, while any token with
`checks: write` could create a check run of any name. Every list it reads must come back whole,
or it cannot decide. In that job the step that decides runs the base branch's copy of the guard
before any code from the pull request runs, and when the base has no guard it refuses a pull
request by their app instead of running the pull request's own copy; `push-gate-cases.mjs`
checks both. That holds whoever merged it and however. On `staging` every commit in the range, and
every merge in the activity API, is looked up by the pull request it merged, and when the pull
request is theirs its guard must have passed, whatever the commits say about who wrote them. So a
merge is judged even before the activity API lists it. GitHub may link a commit to its pull request
a little after the merge, so when a commit's own list has none, the gate also reads the 100 pull
requests most recently closed into the branch, since a pull request records its merge commit when
it is merged. A person's merge whose pull request still cannot be found stops the run, because
nobody can tell whose it was. A read that fails on GitHub's side is tried once more, at once. A
squash commit keeps the pull request author's name (measured on #273: a pull request
tallyfy-workhorse[bot] opened and a person merged has tallyfy-workhorse[bot] as its commit
author). A merge by their app itself passes on the same terms. Commits that name their app and
arrive by a merge commit, or by a rebase of more than one commit, still stop, as above; a rebase of
a single commit passes like a squash, because that commit is the pull request's merge commit.

The gate never waits. Their app is to merge only after the guard has passed. A merge before that
stops the run and opens the issue. Once the guard has passed, re-running the failed workflow, or
the next push to `staging`, judges the merge again and lets it through, so close the issue as
completed then; a person can also accept it on the issue at any time. A wait was tried in review
and dropped: in `documentation-pipeline.yml` it would let commits that land during the wait run
unjudged, because that workflow's later jobs check out the branch tip when they start. The push
or merge that produced the anchor is judged again on every run, so an entry the activity API
listed only after an earlier run still gets judged; an acceptance on the issue covers it on every
later run.

Two known limits. First, the gate trusts the guard job by its name, and a pull request run takes
its workflow file from the pull request. So someone who can change workflow files could add a job
of that name to their own pull request. Their app cannot, because it has no workflows permission
(it has contents and pull requests write), and anyone who can change workflow files can already
change the gate itself. Second, a pass counts however old it is. A pull request run starts only
when the pull request is opened, reopened or gets new commits, so a pass recorded before someone
tightened `scripts/lb-pr-guard.py` or `repo_screenshot_rules.py` on `staging` still lets their
merge through. Re-running the old job does not help, because a re-run judges the same test merge
with the same base. After tightening either file, close every open pull request by their app, so
it cannot be merged, and reopen it: the reopened pull request gets a new run against the new rules,
and once that run lists its guard job, that job is the one that counts.

Any push by their app, any push or merge by it on `main`, any other app, and a push or merge when
the gate cannot read who made it all still stop the run; an activity entry that names no commit is
skipped with a warning, since every commit in the range is judged anyway. On `main` a person's
merge is judged as before, their own included. One known stop: if a person ever merges one of
their pull requests straight into `main`, the next merge of `main` back into `staging` stops once
on that commit, because on `staging` their commit must come from a pull request into `staging`;
accept it on the issue. `scripts/push-gate-cases.mjs` runs the gate's own script from both
workflow files against a fake GitHub, in each file's mode, both ways, checks why each stop
happened, and plants faults that must turn it red; `pr-validate.yml` runs it on every pull request.

On a stop it opens one issue, "Docs pipeline stopped: the push gate did not let commits on
<branch> through", listing each commit, who made it and why it stopped, and adds to that issue on
later stops. Before #548 the title was "Docs pipeline stopped: commits reached <branch> without a
pull request"; an issue under either title is still read, for adding to and for accepting. Review the
commits. To accept them, close the issue as completed and re-run the failed workflow. Closing it
as not planned keeps the pipeline stopped, and a close by a bot accepts nothing.
`scripts/pipeline-guard.py --check-wiring` checks the wiring in both workflows.

`screenshots/launchbrightly/pipeline-canary.png` is a plain image that reads "Screenshot
pipeline canary". No article links it, so its row says `orphaned`. It proves the path end to
end and is the control for the support-docs build check, so leave it in place.

Check it locally, with no credentials and no upload:

```bash
cd scripts/asset_management
python3 repo_screenshot_rules.py --self-test
python3 repo_screenshots.py --self-test
python3 repo_screenshots.py ingest --dry-run   # what the job would upload and write
python3 repo_screenshots.py verify             # rows against the files; --online also fetches
cd ../.. && python3 scripts/lb-pr-guard.py --self-test
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
- `source` - who made the image: `manual` (sent with `orchestrator.py upload` or `replace`), `launchbrightly` (committed under `screenshots/launchbrightly/` and uploaded by the `repo-screenshots` pipeline job, see "Screenshots committed to this repository (LaunchBrightly)" above), or `legacy-unknown` (a row from before 2026-11-05, or a skeleton row `sync` added)
- `repo_path` - for an image committed to this repository, the root-relative path articles link, such as `/screenshots/launchbrightly/task-list.png`; the support-docs build is to swap it for `production_url`. Empty for an image that lives only on R2
- `app_screen` - where in the app the image was taken, in plain words, such as `Template editor, step settings`
- `app_url` - the app URL of that screen, path only
- `location_source` - who supplied `app_screen` and `app_url`: `launchbrightly`, or `inferred` when it was worked out from the image and its article
- `captured_at` - when the image was captured, ISO 8601
- `content_sha256` - SHA-256 of the bytes on R2; `upload` and `replace` write it
- `markdown_alt` - the alt text written in the article, kept as a fallback
- `source_description` - the description that came with the image from whoever made it
- `source_ref` - that maker's own reference for the image, such as a LaunchBrightly recipe id

Dated 2026-11-05 (#462): the schema had the first 16 columns above until then. One migration
commit added the other ten, set `source=legacy-unknown` on every row, and left the first 16
fields of every row unchanged byte for byte. A write now keeps any column the file has that
the scripts don't know, and a key with no column stops the write with an error. Until then
`asset_inventory.py` wrote only the 16 columns it knew, so both disappeared without a word.
`python3 asset_inventory.py migrate-columns --check` says whether the file is on the current
schema, and the PR validation workflow runs it.

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

# Prove the scripts on temporary files (no credentials, no upload, never the real CSV)
python3 asset_inventory.py --self-test
python3 orchestrator.py --self-test
python3 audit_sync.py --self-test
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

Product screenshots come from LaunchBrightly going forward (see "Screenshots committed to this repository (LaunchBrightly)" above, #539). These steps are for any other image.

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
