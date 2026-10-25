> Source of truth for the linking rules and the deployment pipeline. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.
> Dated 2026-10-21 (#384): three bold labels below became level 4 headings, with the same
> words, so CLAUDE.md can name them in pointers.

# The linking rules and the deployment pipeline

## LINKING & REFERENCES

### Internal Links
- **Format**: Absolute paths without .mdx extension
- **Example**: `/products/pro/tracking-and-tasks/processes/`
- **Public Production URL**: Base URL is `https://tallyfy.com/products/`
- **Public Staging URL**: Base URL is `https://staging.tallyfy.com/products/`

### Deployment Pipeline Architecture

**Branch-to-deployment mapping:**

| This repo branch | Syncs to support-docs branch | CF Pages environment | Worker | Public URL |
|---|---|---|---|---|
| `staging` (default) | `staging` | preview | `tallyfy-products-v2` | `staging.tallyfy.com/products/*` |
| `main` | `production` | production | `tallyfy-products` | `tallyfy.com/products/*` |

**How it works:**
1. Push to this repo triggers `generate-ids.yml` → then `documentation-pipeline.yml`
2. Pipeline processes content. **On `staging`**: IDs, snippets, related articles, lastUpdated dates are all auto-regenerated. **On `main`**: only validation + Answers upload + deleted-file cleanup + sync run; the 3 regen jobs early-exit (see tallyfy/documentation#56).
3. Sync job rsyncs `src/content/docs/` to `support-docs` on the mapped branch
4. Cloudflare Pages auto-builds and deploys `support-docs`
5. Cloudflare Workers strip `/products` prefix and proxy to the Pages deployment

**Important:** There is NO auto-promotion from `staging` to `main`. Merging to `main` is a manual step to push content to production. The `staging` branch is the active working branch (default HEAD).

⚠️ **Runs take turns now, and a third push can still drop work (#296).** Since #311 (2026-10-02), `documentation-pipeline.yml` and `generate-ids.yml` carry a concurrency group per branch with `cancel-in-progress: false`, so runs take turns. GitHub keeps one waiting run per group, so a third push while one run works and one waits drops the waiting one. Whole-tree jobs are covered by the next run, but `generate-ids`, `generate-snippets` and `check-deleted-files` lose that commit's work (#296 stays open for that case). Until it is decided, still prefer merging into `staging` one at a time.
Dated 2026-10-03 (owner decision 218): those three now reconcile the whole tree on every run, with no stored state, so the run that replaces a dropped one does the dropped run's work. Read only before the change, staging held one page still on the all-zero placeholder id since 2026-01-15 (`pro/integrations/mcp-server/google-gemini/index.mdx`), the staging index held 3 entries for no page and the production index 1. A first run on the whole tree therefore had 1 id and 0 descriptions to write on staging, and 4 index deletes: the 3 orphans plus the placeholder page's old entry once that page has its id.

#### Deploying staging to production

**Current practice (2026-09-23): a full promotion is a pull request from `staging` into `main`, merged as a true merge commit after an independent check of the running staging site.** #283 (`d4fab7fc`) and #294 (`6fcb47e6`) both landed that way, each with two parents in `git rev-list --parents -n1`. Merge with `gh pr merge <n> --repo tallyfy/documentation --merge`. A subset ship, such as #263 or #268, is a different operation: a squash pull request into `main` carrying only named changes. The commands below are the underlying git, kept for reference; steps 4 and 5 still apply after the pull request merges.

```bash
# 1. Ensure staging is clean and pipeline has passed
git checkout staging && git pull

# 2. Merge staging into main
git checkout main && git pull
git merge staging

# 3. Merge conflicts on auto-generated fields (lastUpdated, related articles)
#    should NOT occur under the current pipeline (see tallyfy/documentation#56):
#    staging is the sole owner of auto-regen, so main inherits the staging-frozen
#    values via merge and never regenerates them. If a conflict does appear, accept
#    the staging side — it's the regen source-of-truth.
git push origin main

# 4. Wait for pipeline to complete on main branch
#    - Check: https://github.com/tallyfy/documentation/actions
#    - Pipeline syncs to support-docs 'production' branch
#    - Cloudflare Pages auto-builds from support-docs

# 5. Purge Cloudflare cache (if needed for immediate visibility)
#    - Use Cloudflare dashboard or API with cloudflare_credentials.json

# 6. Return to staging
git checkout staging
```

**Whether a promote reached the live site: read `canonical_deployment`, never the newest deployment.**

Step 4 above ends at "Cloudflare Pages auto-builds from support-docs", and that is where the two
failures below live. Both were measured on 2026-09-19 and both make a working promote look broken or
a broken one look finished.

**A Pages production build can hang after cloning and never start.** Deployment `5ea5ff83` sat in
`build/active` for 22 minutes and published nothing. Nothing failed, so nothing said so, and the
deployment list showed a build in progress exactly as a healthy one does. Cancelling it and letting
the next commit build was what published.

⚠️ **The only usable signal is ELAPSED TIME against this project's own normal build, which was
5 to 7 minutes on that day. Two things that look like tells are NOT tells, and both were misread
here before the run finished.** A build whose log ends at `Success: Finished cloning repository
files` is normal: the build step has not flushed yet. So is a `modified_on` frozen seconds after
creation. Measured the same afternoon, deployment `bd71a9cc` read BOTH ways at about 4 minutes and
deployed successfully at about 7, so a retry fired against it on that reading was unnecessary and
both builds of the same commit then succeeded. **Wait out the project's normal duration with a
margin before calling a build hung, and derive that duration from its own recent deployments rather
than from this paragraph.**

**What the public sees is the project's `canonical_deployment`, which is not the same thing as its
`latest_deployment`.** Throughout that hang the canonical deployment was `e219dc2a` from 2026-09-17
while the latest was the hung `5ea5ff83`, so the live site was two days behind the branch and every
page read normally. Ask the Pages project for both and compare the canonical commit against the
commit you promoted:

```
GET /accounts/{account}/pages/projects/support-docs
  .result.canonical_deployment.short_id
  .result.canonical_deployment.deployment_trigger.metadata.commit_hash
  .result.latest_deployment.short_id
```

Same credentials as step 5 above. **Cancel a hung build rather than waiting it out**
(`POST /accounts/{account}/pages/projects/support-docs/deployments/{id}/cancel`), because cancelling
leaves the canonical deployment untouched while leaving it queued does not: a build that finishes
after a later one republishes the older tree. Then a new commit, or a retry, starts a fresh build.

**Note the direction: it fails toward "the promote did not work".** The page is unchanged, the
pipeline was green, and the next move a person reaches for is to promote again or to hunt a sync bug
that is not there.

🔴 **And the `sync` job runs `rsync -av --delete src/content/docs/` into support-docs, so a
promote REVERTS anything published there that `main` does not have, and DELETES any page that exists
only there.** Measured the same day: a subset promote of
three unrelated pages produced support-docs commit `c7ed9c24c`, which also took
`src/content/docs/pro/settings/org-settings/system-log.mdx` back by +13 / -67, undoing a correction
that had reached production through a support-docs promotion two days earlier. In that file,
`18 months` went from 7 hits to 0 and `not Administrator` from 0 to 1. Restored by #265, and it
never reached a customer only because the build that would have published it was the hung one above.

**So before any promote, check that `main` is not behind what is published.** This file already says
not to ship content through the support-docs promotion, which is the other half of the same rule;
the mechanical guard for that half is `tallyfy/support-docs#270`.

#### Holding a path back from production (`.github/promotion-holds.txt`)

Sometimes content is ready to write but not ready to publish, usually because the screen it
describes isn't in production yet. Put the path on hold instead of relying on someone
remembering. Nine SSO pages went live on 2026-06-18 and stayed live for seven weeks against a
screen that didn't exist, because the only thing holding them back was a sentence in a GitHub
issue (#88, #118).

- Add a line to `.github/promotion-holds.txt`: `<id>  <glob>  <reason>`. The `promotion-hold-gate`
  job then fails any promotion whose tree contains a matching file, before `sync` can copy
  anything to support-docs.
- The check is presence-based, not diff-based - it fails if the promoted tree *contains* the
  path, whether or not this promotion changed it. A full promotion here lands as a merge commit
  from a `staging` to `main` pull request (#283, #294 and earlier), and the
  `workflow_run` event carries no previous-main SHA, so a diff-based check would have no base
  and would pass when it couldn't compute an answer.
- ⚠️ **A hold blocks a PUBLICATION and cannot block a DELETION.** This follows from the line
  above and is exactly backwards from what most people assume when they reach for a hold. The
  candidate set is `git ls-tree` of the promoted commit (`promotion-hold-check.py:176`, matched
  at `:131`), and a file being deleted is absent from that tree, so it matches no glob and the
  gate passes green while the deletion ships. Measured 2026-08-13 with the checker's own
  fixture builder, both directions on one invocation: same hold list, same branch, held path
  present → `rc=1` blocked, held path absent → `rc=0` ships (tallyfy/documentation#135). There
  is no mechanism here for holding a deletion back: read the promotion's diff by hand, or do
  not promote. Covering deletions would need a previous-`main` base to diff against, which is
  the thing the presence-based design deliberately avoided.
- ⚠️ **The hold only guards the road through this repo.** Production content can also be
  published by merging `support-docs` `staging` into `support-docs` `production`. That is a
  merge in another repository which this pipeline never observes, `support-docs` `staging`
  already carries an rsynced copy of this repo's `staging` content, and Cloudflare Pages builds
  that branch on push. So that road publishes this repo's unpromoted content with the gate
  never invoked, and it is a road in routine use (`support-docs#227`, merged 2026-08-12,
  carried 74 files under `src/content/docs`). **Never use the `support-docs` promotion to ship
  content ahead of this repo's `main`.** Promote here first, let the pipeline sync, and keep
  the `support-docs` merge for framework changes. Tracked as tallyfy/documentation#135.
- ✅ **That second road is now gated too, as of 2026-08-13.** The `sync` job emits the hold
  list into `support-docs/promotion-holds.txt` (via `--emit-effective-holds`, so a hold
  released by a `[release-hold:]` marker does not fail a build over there), and
  `support-docs/scripts/promotion-hold-build-gate.mjs` is chained first into that repo's
  `npm run build`, failing the build on the `production` branch when a held path is present.
  It is a build step and not a workflow on purpose: Cloudflare Pages builds that repo on push
  through its git integration, so a workflow reacting to the push would go red **after**
  publication. Pages will not publish a failed build, which is what makes the build the only
  real gate on that road. The two gates share glob semantics deliberately, and that agreement
  is measured rather than assumed: `fnmatch.fnmatchcase` and the JS translation returned
  identical matches over 8 globs x 704 real content paths on 2026-08-13.
- Release a hold by deleting its line (a reviewable diff), or for one promotion only by naming
  it in the merge commit: `git merge --no-ff staging -m "Promote staging to main [release-hold: <id>] <why>"`.
  A plain `git merge` fast-forwards and carries no message of yours, so the marker needs `--no-ff`.
  With a pull request promotion, put the marker in the merge commit instead:
  `gh pr merge <n> --merge --subject "Promote staging to main [release-hold: <id>] <why>"`. The gate
  reads the whole message of the promoted commit (`git log -1 --format=%B`), so subject or body both work.
- Check it locally before pushing: `python3 scripts/promotion-hold-check.py --self-test`. The
  same self-test runs in CI on every promotion, so the gate proves it can go red rather than
  only ever being seen passing.

#### Verifying deployment
- Staging: `curl -s https://staging.tallyfy.com/products/pro/ | head -50`
- Production: `curl -s https://tallyfy.com/products/pro/ | head -50`
- Check CF Pages build: GitHub Actions logs show sync status
- **Verifying a PROD (main) deploy:** `gh run list` mislabels the `workflow_run`-triggered main pipeline as `[staging]` (it runs in the default-branch context), so don't trust its branch label. Instead confirm: (1) what the run's `sync` job did, and (2) when it committed, that the CF Pages `support-docs` production deployment for that commit reached `deploy/success`.

  **Step 1 has two correct outcomes, and only one of them makes a commit.** Read the `sync` job's own log, never the whole run's, because several jobs in this workflow print the same `No changes to commit` words. And match only what the step printed when it ran. GitHub prints each step's whole script at the top of that step's log, so the script's own `echo "No changes to commit"` and `git commit -m "Sync docs from tallyfy/documentation"` lines are in every `sync` log, whatever the run did. A plain grep for either phrase matches on every run and cannot tell a commit from a no-op.

  ```bash
  JOB=$(gh run view <run-id> --repo tallyfy/documentation --json jobs --jq '.jobs[] | select(.name=="sync") | .databaseId')
  LOG=$(mktemp)
  [ -n "$JOB" ] && gh run view --job "$JOB" --repo tallyfy/documentation --log > "$LOG" && [ -s "$LOG" ] || echo "COULD NOT READ THE SYNC LOG"
  /usr/bin/grep -E 'Z \[production [0-9a-f]{7,}\] Sync docs from tallyfy/documentation$' "$LOG" && echo COMMITTED
  /usr/bin/grep -E 'Z No changes to commit$' "$LOG" && echo NO-OP
  ```

  Both patterns start at the `Z ` that ends each log line's timestamp and run to the end of the line. git's own commit line, `[production 5574fe3] Sync docs from tallyfy/documentation`, and the `echo` output sit straight after the timestamp. Every printed script line has a colour code (`^[[36;1m`) in between, so the script never matches. Exactly one of the two should print. If neither does, this log cannot tell you, so do not guess. A staging run commits to `staging` and prints `[staging <sha>]`, so the first pattern stays silent on it by design: swap in `staging` to check a staging sync. The printed script also carries `TARGET_BRANCH=production` or `TARGET_BRANCH=staging`, which tells you which branch the run was for when `gh run list` will not. Measured 2026-09-23 UTC on six real `sync` logs: the plain grep matched both phrases in all six, and these patterns (branch name set to each run's target) gave the right answer in all six. That was four commits, runs 35806223175 and 34427272145 to `production` and 35804809862 and 35779685248 to `staging`, and two no-ops from 2026-08-12, 31621930044 to `production` and 31614981833 to `staging`.

  - **It committed.** support-docs `production` has a new `Sync docs from tallyfy/documentation` commit whose body carries a `Source commit: <sha>` trailer naming the documentation `main` tip the job checked out (`gh api 'repos/tallyfy/support-docs/commits?sha=production&per_page=1' --jq '.[0].commit.message'`). Check your promotion is in it with `git merge-base --is-ancestor <promotion sha> <trailer sha>`, since another push to `main` can land before the job checks out. Then do step 2 for that commit.
  - **It printed `No changes to commit`.** Nothing the run would write differs from what `production` already carries, so there is no commit, no push and no Pages build. That is a correct no-op, not a failed deploy, and step 2 has nothing new to find: the newest deployment is the previous one. Confirm instead that the page you changed already serves the new content.
  - **It printed `DO NOT PUBLISH:`** (since #311). The publish guard found a commit after the gated one that was not the pipeline's own generated commit, so this run published nothing and the run for that push publishes it. That is correct, not a failed deploy. Read it with `/usr/bin/grep -E 'Z (PUBLISH|DO NOT PUBLISH): ' "$LOG"`; a run that publishes prints `PUBLISH:` first.

  **PR #273 reached `main` on 2026-09-23, in the promotion PR #283 (`d4fab7fc`), so a production run can be a no-op again.** Before that, `main`'s copy of `scripts/promotion-hold-check.py`, which the `sync` job runs from its `main` checkout, wrote a per-promotion `# Source commit:` line into `promotion-holds.txt`. While that copy was on `main`, the file changed on every run, so every production run committed. The #283 sync, support-docs `5574fe3f`, removed the line, and the next production sync, `885bfba6` for promotion #294, did not touch the file. The `Source commit:` trailer on the sync commit comes from the workflow file, which a `workflow_run` workflow reads from the default branch, `staging`.

  ⚠️ **Step 2 cannot be done with `gh`, and the failure looks exactly like a failed deploy.** `gh` only ever talks to GitHub, so it routes a Cloudflare path there and answers `Not Found (HTTP 404)` with a `documentation_url` of `docs.github.com`. That reads as "the deployment isn't there", and the natural response is to re-run a publish that already succeeded. This file prescribed `gh api 'accounts/<account_id>/pages/...'` until 2026-08-14; it never worked (tallyfy/documentation#139). Use `curl`:

  ```bash
  AID=$(jq -r .account_id ../cloudflare_credentials.json)
  TOK=$(jq -r .api_token   ../cloudflare_credentials.json)
  curl -s -H "Authorization: Bearer $TOK" \
    "https://api.cloudflare.com/client/v4/accounts/$AID/pages/projects/support-docs/deployments?env=production&per_page=1" \
    | jq -r '.result[] | "\(.short_id) \(.latest_stage.name)/\(.latest_stage.status) skipped=\(.is_skipped) \(.created_on)"'
  ```

  Read `is_skipped` as well as the stage. A skipped build (commit message carrying `[skip ci]` or a sibling marker) still appears in the deployments list with a `github:push` trigger and looks like a real build, but its stages never start. Two controls, both cheap: `?env=preview` must return *different* rows (the `staging` ones), and a fabricated project name must return `success: false` rather than an empty-looking pass.
- **Cache purge timing:** purge tallyfy.com only AFTER the Pages build is `deploy/success` (purging mid-build re-caches the old bundle). Purge needs the legacy `X-Auth-Email` + `X-Auth-Key` headers (the Bearer token lacks Zone:Cache Purge); purge the specific changed `/products/...` URLs for a surgical refresh.
- **Core Concepts Linking Pattern**: 
  - Link sparingly to core concepts from the reference list when first mentioned in article body
  - Format: `[templates](mdc:products/pro/documenting/templates)`, `[tasks](mdc:products/pro/tracking-and-tasks/tasks)`
  - Only link when it adds value for understanding the current topic
- Link only first occurrence in a section
- Use descriptive anchor text (not "click here")
- Add "See also" sections when helpful
- Verify all links are valid
- Don't over-link (distracts readers)

### External Link Requirements
**All links to domains NOT ending in tallyfy.com must be nofollow and open in new tab:**

**Astro Starlight Format**:
```markdown
[Link Text](https://example.com)<a href="https://example.com" rel="nofollow noopener noreferrer" target="_blank"><sup>[1]</sup></a>
```

**Example**:
```markdown
Learn more at [Google Analytics](https://analytics.google.com)<a href="https://analytics.google.com" rel="nofollow noopener noreferrer" target="_blank"><sup>[1]</sup></a>
```

**Note**: The superscript number should increment for each external link on the page
