> Source of truth for the project overview and finding and updating documentation. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.

# The project overview and finding and updating documentation

## PROJECT OVERVIEW

This is a **documentation website** for Tallyfy's suite of products built with **Astro and Starlight**.

**📁 COMPLETE DOCUMENTATION STRUCTURE**: See `DOCUMENTATION_STRUCTURE.md` for comprehensive organization guide including 715 .mdx files across 148 directories, search strategies, and file patterns.

> **Counts in this file go stale. Re-derive, do not trust.** The two figures above read 585 and 99
> until 2026-08-06, when they were measured at 742 and 156 - a 27% undercount that had been sitting
> here long enough to mis-scope work. Every count below was measured on **2026-08-06** and re-verified
> unchanged on **2026-08-11**; treat any of them older than a few weeks as indicative only:
> ```bash
> find src/content/docs -name '*.mdx' -type f | wc -l                          # total files
> find src/content/docs -name '*.mdx' -type f -exec dirname {} \; | sort -u | wc -l   # directories
> ```

### Tallyfy Products Overview
- **Tallyfy Pro** (Primary focus): Create, launch, track and improve repeatable business processes
  - Location: `/src/content/docs/pro/` (693 files - 90% of all documentation)
  - Core areas: documenting/ (81 files), tracking-and-tasks/ (52 files), integrations/ (295 files)
- **Tallyfy Answers**: Vector-based search engine
  - Location: `/src/content/docs/answers/` (13 files)
- **Tallyfy Denizen**: Localized images based on user location
  - Location: `/src/content/docs/denizen/` (2 files)

> **Manufactory is gone and its 45 pages were removed on 2026-08-12** (tallyfy/documentation#127).
> The product was dismantled: its Argo tunnel was deleted 2025-11-11, its DNS record and fronting
> Worker on 2026-08-11. The pages told readers to send events to `collector.tallyfy.com`, which
> returns HTTP 530, and real browser traffic was still following them. The old URLs now 301 to
> `/products/pro/` via `public/_redirects` in support-docs. Do not restore these pages or write
> new ones; if Manufactory ever returns it needs a fresh decision, not this content.

### Product Name Capitalization
**CRITICAL**: When referring to our products, always capitalize product names properly:
- Use "Pro", "Answers", "Changelog", "Denizen" (capitalized)
- Never use lowercase versions like "pro", "answers", "changelog", etc.
- Examples:
  - ✅ CORRECT: "Tallyfy Pro provides workflow automation"
  - ❌ INCORRECT: "Tallyfy pro provides workflow automation"
  - ✅ CORRECT: "Using Answers for vector search"
  - ❌ INCORRECT: "Using answers for vector search"
- This applies to all documentation, articles, and content where our product names appear

### Tallyfy Pro Terminology & Concepts

#### Core Workflow Terms
- **Templates**: Where you define your process (API calls these "blueprints")
  - **Procedure templates**: Step-by-step workflows with tasks and assignments
  - **Document templates**: Structured documents with fillable fields
- **Processes**: Running instances of launched templates that you can track
- **Steps vs Tasks**: 
  - In a procedure template: single items are called "steps"
  - In a launched process: single items are called "tasks"
- **Runs**: Individual process instances (each launch creates a new run)

#### Assignment & User Management
- **User Roles**: 
  - **Administrator**: Full access to all features and settings
  - **Standard**: Can create/edit templates and manage processes
  - **Light**: View-only access, cannot edit/create templates
- **Guests**: Email addresses outside your company (unlimited free)
- **Job Titles**: Role-based assignments that dynamically find the right person
- **Groups**: Collections of users for bulk assignments
- **Org Chart**: Hierarchical structure for approval routing

#### Content & Automation
- **Automations**: conditions (the If side) paired with actions (the Then side)
- **Snippets**: Reusable content blocks that update everywhere when edited
- **Variables**: Dynamic placeholders that get filled with actual data
- **Form Fields**: Input elements that collect data during task completion
- **Kick-off Form**: Initial data collection before process launch
- **Deadline Automations**: Automatic due date calculations based on conditions you set

#### Views & Navigation
- **Tasks View**: Individual tasks assigned across all processes
- **Tracker View**: Birds-eye view at per-process level
- **Dashboard**: Personal overview of assignments and deadlines
- **Templates**: Collection of all templates available to launch

#### Technical & Integration Terms
- **API**: RESTful interface (API-first architecture)
- **Webhooks**: Event-driven HTTP callbacks
- **SSO**: Single Sign-On (free for all customers)
- **Middleware**: Integration platform connections (Zapier, Make, etc.)
- **Tallyfy Analytics**: Built-in process performance metrics
- **Public Forms**: External-facing forms for data collection

#### Process States & Actions
- **Draft**: Template under construction
- **Active**: Live template available for launching
- **Archived**: Retired template (kept for historical reference)
- **Paused**: Process temporarily halted
- **Completed**: All tasks finished
- **Cancelled**: Process terminated before completion

**Note on Footnotes**: Consider adding brief footnotes for these terms when they first appear in technical articles or when the context might confuse new users. Keep explanations under 150 characters.

### Core Concepts Reference Links (Pro Product)
Use these absolute paths for internal linking:
```
Procedure templates: `/products/pro/documenting/templates/`
Document templates: `/products/pro/documenting/documents/`
Templates (overall): `/products/pro/documenting/templates/`
Processes: `/products/pro/tracking-and-tasks/processes/`
Automations: `/products/pro/documenting/templates/automations/`
Tasks: `/products/pro/tracking-and-tasks/tasks/`
Members: `/products/pro/documenting/members/`
Member roles: `/products/pro/documenting/members/`
Invite a member: `/products/pro/documenting/members/how-to-invite-and-activate-members-on-tallyfy/`
Guests: `/products/pro/documenting/guests/`
Form fields: `/products/pro/tracking-and-tasks/tasks/what-are-form-fields-in-tallyfy/`
Pricing: `/products/pro/pricing/`
Security: `/products/pro/compliance/`
Compliance: `/products/pro/compliance/`
Language translation: `/products/pro/miscellaneous/how-can-i-translate-content-in-tallyfy/`
Snippets: `/products/pro/documenting/templates/snippets/`
Variables: `/products/pro/documenting/templates/variables/`
Job titles: `/products/pro/documenting/templates/edit-templates/understanding-assignment-types/`
Launching a process: `/products/pro/launching/`
Tasks view: `/products/pro/tracking-and-tasks/tasks-view/`
Tracker view: `/products/pro/tracking-and-tasks/tracker-view/`
Personal settings: `/products/pro/settings/personal-settings/`
Organization settings: `/products/pro/settings/org-settings/`
Integrations: `/products/pro/integrations/`
Tallyfy Analytics: `/products/pro/integrations/analytics/`
Middleware: `/products/pro/integrations/middleware/`
API: `/products/pro/integrations/open-api/`
Webhooks: `/products/pro/integrations/webhooks/`
Contact support: `/products/pro/miscellaneous/support/how-can-i-contact-tallyfys-support-team/`
```

## FINDING & UPDATING DOCUMENTATION

### Deriving Local File Paths from URLs

When given a staging or production URL, derive the local file path using this pattern:

**URL to Local Path Conversion**:
```
URL: https://staging.tallyfy.com/products/pro/integrations/extract-tasks-from-meetings/
Path: documentation/src/content/docs/pro/integrations/extract-tasks-from-meetings.mdx

URL: https://tallyfy.com/products/pro/tracking-and-tasks/tasks/
Path: documentation/src/content/docs/pro/tracking-and-tasks/tasks/index.mdx
```

**Conversion Rules**:
1. Remove domain (`https://staging.tallyfy.com/` or `https://tallyfy.com/`)
2. Remove `/products/` prefix
3. Add relative base path: `documentation/src/content/docs/`
4. If URL ends with a specific page name: add `.mdx`
5. If URL ends with `/`: look for `index.mdx` in that directory

**Examples** (relative to GitHub root directory):
- `https://staging.tallyfy.com/products/pro/integrations/extract-tasks-from-meetings/`
  → `documentation/src/content/docs/pro/integrations/extract-tasks-from-meetings.mdx`
- `https://tallyfy.com/products/pro/documenting/templates/`
  → `documentation/src/content/docs/pro/documenting/templates/index.mdx`
- `https://staging.tallyfy.com/products/answers/`
  → `documentation/src/content/docs/answers/index.mdx`

### Documentation Discovery Strategies
When identifying where to update documentation, use this search hierarchy:

1. **Check existing file coverage first**:
   ```bash
   # Find by feature area (from documentation directory)
   find src/content/docs/pro/documenting/templates -name "*.mdx"
   find src/content/docs/pro/tracking-and-tasks/tasks -name "*.mdx"
   
   # Search by keywords (from documentation directory)
   grep -r "assignment\|assign" src/content/docs/pro --include="*.mdx"
   grep -ri "automation\|rule" src/content/docs/pro --include="*.mdx"
   ```

2. **Use the comprehensive structure map**: `DOCUMENTATION_STRUCTURE.md` contains complete file inventory

3. **Follow established patterns**:
   - User management issues → `pro/documenting/members/` or `pro/documenting/guests/`
   - Task/assignment problems → `pro/tracking-and-tasks/tasks/`
   - Template creation → `pro/documenting/templates/edit-templates/`
   - Process launching → `pro/launching/` or `pro/tracking-and-tasks/processes/`
   - Integration setup → `pro/integrations/[vendor]/`
   - Automations → `pro/documenting/templates/automations/`

### Quick File Location Commands
```bash
# Most common documentation areas (from documentation directory)
ls src/content/docs/pro/documenting/templates/     # 24 entries (54 .mdx recursively) - Template creation
ls src/content/docs/pro/tracking-and-tasks/tasks/ # 19 entries (22 .mdx recursively) - Task management
ls src/content/docs/pro/integrations/             # 20 entries (277 .mdx recursively) - All integrations
ls src/content/docs/pro/documenting/members/      # 9 entries (9 .mdx recursively) - User management

# Find specific topics (from documentation directory)
grep -l "how to assign" src/content/docs/pro/**/*.mdx
grep -l "template\|blueprint" src/content/docs/pro/**/*.mdx
```

### Update vs. Create Decision Matrix
- **UPDATE existing file**: When topic fits within current article scope (90% of cases)
- **CREATE new file**: Only when entirely new feature/workflow needs dedicated coverage
- **Reference DOCUMENTATION_STRUCTURE.md**: For complete context before making changes

### Maintaining Documentation Structure Map
**CRITICAL**: When adding, removing or moving documentation files, run the structure script:

```bash
python3 scripts/update-documentation-structure.py           # rewrite both files
python3 scripts/update-documentation-structure.py --check   # report only, non-zero if stale
```

It resolves its own paths from the script location, so it works from any working directory and
on either machine. It rewrites the tree rows, the loose-file rows, the `**Total**` line, the
Quick Navigation Map, and this file's own per-area figures, then prints any count-shaped figure
it could not attribute to a real directory so the gap is visible rather than assumed.

Three refusals are deliberate, and each exists because its absence caused a real defect
(tallyfy/documentation#126):

- It exits non-zero and writes nothing when it counts zero files. The previous version silently
  matched nothing for months, and a repair that fixed only some of its paths would have written a
  zero total over a correct number.
- It exits non-zero when a target file is missing, rather than returning early and reporting
  success.
- It refuses to write when the arithmetic does not reconcile: each parent must equal the sum of
  its children plus its own loose files, and the top-level rows must sum to the stated total.
  That reconciliation is the only check that catches a partial update.

To re-derive the headline counts by hand, for example to confirm the script:

```bash
cd src/content/docs
find . -name '*.mdx' -type f | wc -l                                  # total files
find . -name '*.mdx' -type f -exec dirname {} \; | sort -u | wc -l    # directories
```

**Workflow Integration**:
- Run the script after creating or deleting articles, and commit the result with them.
- Use `--check` in review to confirm a branch has not left the counts stale.
