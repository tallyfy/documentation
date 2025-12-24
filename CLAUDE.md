# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: Repository Separation Rules

**ABSOLUTE RULE - WHERE TO MAKE CHANGES:**

### ✅ Changes that go in THIS repository (/documentation):
- **ALL article content** (.mdx files in src/content/docs/)
- **ALL documentation text updates**
- **ALL D2 diagrams in articles**
- **ALL images and screenshots for articles**
- **ALL frontmatter changes** (titles, descriptions, etc.)
- **ALL content fixes** (typos, broken links, outdated information)
- **Python scripts** for content processing
- **Documentation-specific automation**

### ❌ NEVER make these changes in /documentation:
- Astro configuration changes
- Starlight theme modifications
- CSS framework changes
- Component framework updates
- Build system modifications
- Deployment configuration

### 📍 Changes that go in /support-docs repository ONLY:
- **Astro configuration** (astro.config.mjs)
- **Starlight framework settings**
- **Global CSS and styling** (including D2 diagram styles)
- **Component overrides** in src/components/overrides/
- **Build and deployment settings**
- **Framework dependencies** in package.json
- **Worker configuration** (Cloudflare Workers)

**WHY THIS MATTERS**: The /support-docs repository contains the Astro/Starlight framework that renders the documentation. The /documentation repository contains ONLY the content. Mixing these concerns breaks the deployment pipeline and causes build failures.

**CRITICAL - NEVER MANUALLY SYNC CONTENT**: 
- **NEVER copy MDX files from /documentation to /support-docs manually**
- **NEVER run sync commands between the repositories**
- **NEVER edit content directly in /support-docs**
- Content synchronization happens AUTOMATICALLY through CI/CD pipelines
- Manual syncing breaks the automated deployment process

**ENFORCEMENT**: If you accidentally edit the wrong repository, immediately revert those changes before proceeding.

## 🚨 CRITICAL: Humanizing Rules Integration

**ALL AI content operations MUST incorporate the comprehensive humanizing guidelines from `humanizing-rules.md`**. These rules ensure content appears natural, human-written, and undetectable as AI-generated.

**Before any AI content work**: Review and apply the humanizing rules found in `/Users/amit/Documents/GitHub/documentation/humanizing-rules.md`

**Required in every AI prompt**: Include humanizing guidelines for conversational tone, varied sentence rhythm, specific examples, answer-first structure, and elimination of AI-typical phrases.

## 📝 Hover Annotations (Footnotes) Guidelines

### When to Use Hover Annotations

Hover annotations use littlefoot.js to display supplementary information as interactive popovers. Use them SPARINGLY and INTELLIGENTLY - most articles need NO footnotes.

#### 🎯 CRITICAL: Intelligent Footnote Addition Protocol

**When creating or editing any article, evaluate for HIGH-VALUE footnote opportunities:**

1. **Scan for these specific patterns** that benefit from footnotes:
   - Technical terms/jargon that ~30% of users might not know
   - Performance claims that benefit from evidence
   - API/code parameters needing clarification
   - Architecture decisions with non-obvious reasons
   - Integration points with external systems
   - Industry standards or protocols mentioned
   - **Tallyfy-specific terminology** when first introduced or in complex contexts

2. **Apply the 5-Point Value Test** before adding ANY footnote:
   - Will some (not all) users benefit from this clarification?
   - Is the information supplementary (not critical)?
   - Can it be explained in 50-150 characters?
   - Does it add genuine value without disrupting flow?
   - Would an expert user find this helpful, not patronizing?

3. **Target Metrics**:
   - **Most articles**: 0 footnotes (default)
   - **Technical articles**: 1-3 footnotes maximum
   - **API/integration docs**: 2-5 footnotes maximum
   - **Character limit**: 50-150 characters per footnote
   - **Success rate**: Only ~10-15% of articles should have footnotes

#### ✅ HIGH-VALUE Footnote Patterns:

1. **Technical Clarifications** (Use when term is industry-specific)
   ```markdown
   The system uses OAuth 2.0[^1] for authentication.
   [^1]: Industry-standard protocol for secure third-party authorization without sharing passwords
   ```

2. **Performance Evidence** (Use for specific claims)
   ```markdown
   Processes complete 80% faster[^2] with automation.
   [^2]: Based on analysis of 10,000+ workflows comparing manual vs automated execution times
   ```

3. **API Implementation Details** (Use for non-obvious parameters)
   ```markdown
   Set temperature=0.3[^3] for consistent results.
   [^3]: Lower values (0-1) make AI more deterministic, reducing variation across runs
   ```

4. **Architecture Context** (Use for design decisions)
   ```markdown
   Uses speaker diarization[^4] to identify task owners.
   [^4]: Audio processing that separates different speakers, crucial for accurate task assignment
   ```

5. **Integration Specifics** (Use for external system details)
   ```markdown
   Connects via webhook[^5] to your CRM.
   [^5]: HTTP callbacks triggered by Tallyfy events, enabling real-time data synchronization
   ```

6. **Tallyfy-Specific Terms** (Use when context needs clarification)
   ```markdown
   The template becomes a process[^6] when launched.
   [^6]: Running instance with tracked tasks, assignments, and deadlines - like a template brought to life
   ```

#### ❌ NEVER Use Footnotes For:
1. **Basic UI instructions** - "Click the button" explanations
2. **Critical warnings** - Security, compliance, validation rules
3. **Core definitions** - Fundamental concepts everyone needs
4. **Obvious clarifications** - Information users can infer
5. **Marketing fluff** - Benefits or features already clear in context
6. **Long explanations** - Anything over 150 characters
7. **Mobile-critical info** - Touch devices can't hover

### Implementation Requirements

**CRITICAL - Both parts required**:
```markdown
Article text with term[^1] that needs clarification.

<!-- More article content -->

[^1]: Brief 50-150 character explanation providing genuine value

## Related articles
<CardGrid>...</CardGrid>
```

**Placement Rules**:
- Footnote definitions go BEFORE "Related articles" section
- Number sequentially starting from [^1]
- Group all definitions together
- Don't mix definitions with main content

### Quality Control Checklist

Before adding ANY footnote, verify:
- [ ] Does this pass the 5-Point Value Test?
- [ ] Is it 50-150 characters?
- [ ] Would removing it still leave the article complete?
- [ ] Does it clarify without patronizing?
- [ ] Is it factual and specific (no vague statements)?
- [ ] Have you limited to 5 footnotes maximum per article?

### Examples of Intelligent vs Poor Usage

#### ✅ INTELLIGENT (High-Value):
- "Uses ELK layout[^1]" → [^1]: Layered graph drawing algorithm optimized for complex hierarchical diagrams
- "Rate limit is 100 req/min[^2]" → [^2]: Resets every 60 seconds with burst allowance up to 150 requests
- "Supports SAML 2.0[^3]" → [^3]: XML-based standard enabling single sign-on across independent security domains

#### ❌ POOR (No Value):
- "Click Submit[^1]" → [^1]: This saves your work
- "Fill required fields[^2]" → [^2]: Required fields must be filled
- "Fast performance[^3]" → [^3]: Tallyfy is very fast
- "User-friendly interface[^4]" → [^4]: Easy to use for everyone

### Tallyfy Terms That May Benefit from Footnotes

**Consider footnotes for these Tallyfy-specific terms when context needs clarification:**

- **blueprints** → API term for templates, different from UI terminology
- **job titles** → Dynamic role-based routing vs. specific user assignment
- **snippets** → Centralized content that updates everywhere
- **tracker view** → Process-level overview vs. task-level view
- **light users** → Limited permissions, view-only access
- **kick-off form** → Data collection before process starts
- **deadline rules** → Automatic due date calculations
- **public forms** → External data collection without login
- **runs** → Individual process instances from same template
- **automations** → If-this-then-that workflow rules

**Remember**: Only add footnotes when the term appears in a context where ~30% of users might need clarification. Never footnote basic UI terms or actions.

### Automated Intelligence System

A production-ready system exists at `/documentation/scripts/footnote-annotator.py` for batch processing. For individual articles during creation/editing, manually apply the protocol above.

**Key Stats from Testing**:
- ~85% of articles need NO footnotes
- ~12% benefit from 1-2 footnotes
- ~3% (technical/API docs) benefit from 3-5 footnotes
- Average character count: 95 characters per footnote
- Most valuable categories: Technical terms (30%), API parameters (25%), Performance metrics (20%), Tallyfy-specific terms (15%)

## D2 Diagrams Resources

**Production-Ready Diagram Assets**: 63 D2 diagrams are available as external SVG files for reuse across all platforms. See the **D2 Diagrams Inventory** section in `/README.md` for complete details.

### Quick Access Information:
- **Base URL**: `https://tallyfy.com/products/d2-diagrams/docs/`
- **URL Pattern**: `https://tallyfy.com/products/d2-diagrams/docs/[path]/[filename]-[index].svg`
- **Important**: Note the `/docs/` prefix after `/d2-diagrams/` - this is required
- **Full Metadata**: Available in `/temporary/d2_inventory.json`

### Available Categories (63 Total):
- **API Integration Flows** (32 diagrams - 50.8%): Zapier, Power Automate, n8n, Make.com workflows
- **Computer AI Agents** (13 diagrams - 20.6%): Claude, ChatGPT, Skyvern, local agents
- **Authentication & SSO** (4 diagrams - 6.3%): Azure AD, Okta, OneLogin, Auth0
- **Process Workflows** (5 diagrams - 7.9%): Multi-level approvals, process launching
- **Webhook Integrations** (4 diagrams - 6.3%): Event triggers, external integrations
- **System Architecture** (2 diagrams - 3.2%): Distributed tracing, WebSocket connections
- **Manufactory** (4 diagrams): Event lifecycle, collectors

### Example Working URLs:
- Zapier Integration: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/middleware/zapier/how-to-automate-tasks-in-tallyfy-using-zaps-0.svg`
- OAuth Flow: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/open-api/oauth-authorization-flow-0.svg`
- Multi-level Approvals: `https://tallyfy.com/products/d2-diagrams/docs/pro/documenting/templates/automations/examples/multi-level-approval-loops-0.svg`
- Azure AD SSO: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/authentication/how-to-integrate-azure-ad-samlsso-with-tallyfy-0.svg`

## ROLE & PRIMARY OBJECTIVE

You are working with Tallyfy's comprehensive product documentation. Your role is to act as a workflow expert and exceptionally skilled technical writer creating documentation for Tallyfy - a workflow and business process management SaaS platform.

**Primary Mission**: Write clear, concise articles that help non-technical users understand how to use specific Tallyfy features. Every piece of content must serve the singular goal of making users successful with the product while following all humanizing rules to ensure natural, human-like writing.

## PROJECT OVERVIEW

This is a **documentation website** for Tallyfy's suite of products built with **Astro and Starlight**.

**📁 COMPLETE DOCUMENTATION STRUCTURE**: See `DOCUMENTATION_STRUCTURE.md` for comprehensive organization guide including 585 .mdx files across 99 directories, search strategies, and file patterns.

### Tallyfy Products Overview
- **Tallyfy Pro** (Primary focus): Create, launch, track and improve repeatable business processes
  - Location: `/src/content/docs/pro/` (512 files - 89% of all documentation)
  - Core areas: documenting/ (155 files), tracking-and-tasks/ (65 files), integrations/ (149 files)
- **Tallyfy Answers**: Vector-based search engine
  - Location: `/src/content/docs/answers/` (16 files)
- **Tallyfy Denizen**: Localized images based on user location
  - Location: `/src/content/docs/denizen/` (2 files)
- **Tallyfy Manufactory**: Events ingestion and lifecycle engine
  - Location: `/src/content/docs/manufactory/` (45 files)

### Product Name Capitalization
**CRITICAL**: When referring to our products, always capitalize product names properly:
- Use "Pro", "Answers", "Changelog", "Manufactory", "Denizen" (capitalized)
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
- **Automations**: "If this then that" rules that trigger actions
- **Snippets**: Reusable content blocks that update everywhere when edited
- **Variables**: Dynamic placeholders that get filled with actual data
- **Form Fields**: Input elements that collect data during task completion
- **Kick-off Form**: Initial data collection before process launch
- **Deadline Rules**: Automatic due date calculations based on business rules

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
- `https://staging.tallyfy.com/products/manufactory/overview/`
  → `documentation/src/content/docs/manufactory/overview.mdx` or `overview/index.mdx`

### Documentation Discovery Strategies
When identifying where to update documentation, use this search hierarchy:

1. **Check existing file coverage first**:
   ```bash
   # Find by feature area (from documentation directory)
   find src/content/docs/pro/documenting/templates -name "*.mdx"
   find src/content/docs/pro/tracking-and-tasks/tasks -name "*.mdx"
   
   # Search by keywords (from documentation directory)
   grep -r "assignment\|assign" src/content/docs/pro --include="*.mdx"
   grep -r "automation\|rule" src/content/docs/pro --include="*.mdx"
   ```

2. **Use the comprehensive structure map**: `DOCUMENTATION_STRUCTURE.md` contains complete file inventory

3. **Follow established patterns**:
   - User management issues → `pro/documenting/members/` or `pro/documenting/guests/`
   - Task/assignment problems → `pro/tracking-and-tasks/tasks/`
   - Template creation → `pro/documenting/templates/edit-templates/`
   - Process launching → `pro/launching/` or `pro/tracking-and-tasks/processes/`
   - Integration setup → `pro/integrations/[vendor]/`
   - Automation rules → `pro/documenting/templates/automations/`

### Quick File Location Commands
```bash
# Most common documentation areas (from documentation directory)
ls src/content/docs/pro/documenting/templates/     # 84 files - Template creation
ls src/content/docs/pro/tracking-and-tasks/tasks/ # 25 files - Task management  
ls src/content/docs/pro/integrations/             # 149 files - All integrations
ls src/content/docs/pro/documenting/members/      # 19 files - User management

# Find specific topics (from documentation directory)
grep -l "how to assign" src/content/docs/pro/**/*.mdx
grep -l "template\|blueprint" src/content/docs/pro/**/*.mdx
```

### Update vs. Create Decision Matrix
- **UPDATE existing file**: When topic fits within current article scope (90% of cases)
- **CREATE new file**: Only when entirely new feature/workflow needs dedicated coverage
- **Reference DOCUMENTATION_STRUCTURE.md**: For complete context before making changes

### Maintaining Documentation Structure Map
**CRITICAL**: When adding/removing/moving documentation files, update the structure map:

```bash
# Regenerate documentation structure map after any file changes
cd /documentation/vimeo_transcripts
python3 -c "
import os, glob
from pathlib import Path

# Count all .mdx files and update DOCUMENTATION_STRUCTURE.md
docs_dir = '/Users/amit/Documents/GitHub/documentation/src/content/docs'
all_files = glob.glob(os.path.join(docs_dir, '**/*.mdx'), recursive=True)
total_files = len(all_files)

# Update the file count in DOCUMENTATION_STRUCTURE.md
structure_file = '/Users/amit/Documents/GitHub/documentation/DOCUMENTATION_STRUCTURE.md'
with open(structure_file, 'r') as f:
    content = f.read()

# Replace the total file count
import re
content = re.sub(r'\*\*Total\*\*: \d+ \.mdx files', f'**Total**: {total_files} .mdx files', content)

with open(structure_file, 'w') as f:
    f.write(content)

print(f'Updated DOCUMENTATION_STRUCTURE.md with {total_files} total files')
"

# Also update CLAUDE.md references if the count changed significantly
# (Manual step - update the "576 .mdx files" references in CLAUDE.md if needed)
```

**Workflow Integration**: 
- Run structure update after creating new articles
- Update file counts in CLAUDE.md if they change by >5%
- Regenerate complete structure map monthly or after major reorganizations

## DEVELOPMENT COMMANDS

```bash
# Development
npm install                    # Install dependencies
npm run dev                   # Start development server

# Content Automation (Python scripts)
python scripts/generate-snippets.py --files [files] --dir [directory] --token [api-key] --prompt [base64-prompt]
python scripts/generate-related-articles.py --dir [directory] --answers_api_key [key]
python scripts/markdown-lint.py --dir [directory]
python scripts/check-deleted-files.py --dir [directory]
python scripts/update-documentation-structure.py     # Update structure map after file changes
python scripts/update-last-modified.py --dir [directory]  # Update lastUpdated dates from Git history
```

## LOCAL PRE-COMMIT CHECKS

Before committing documentation changes, run these validation scripts locally:

### Validate Internal Links

```bash
python3 scripts/validate-internal-links.py --dir src/content/docs
```

This checks that all internal `/products/...` links point to existing MDX files. **Run this before every commit to avoid build failures from broken links.**

The script:
- Scans all MDX files in the documentation directory
- Extracts internal links (markdown `[text](/products/...)` and href `href="/products/..."` patterns)
- Validates each link points to an existing file
- Reports broken links by file with full paths

### Validate Markdown Structure

```bash
python3 scripts/markdown-lint.py --dir src/content/docs
```

This validates frontmatter, imports, and related articles sections.

## PLATFORM & TECHNICAL REQUIREMENTS

### Documentation Platform
- **Platform**: Astro Starlight
- **Format**: Markdown files (.mdx)
- **Editing**: All edits must be in markdown using standard syntax

### Article Structure Rules
1. **Headers** (DO NOT EDIT except for new articles):
   ```yaml
   ---
   id: c15bf2be31c3a7fbded5d13fce7aaab9
   sidebar:
     order: 15
   description: [AI-generated comprehensive description]
   title: [Article title in sentence case]
   lastUpdated: 2025-08-15  # Auto-generated from Git history
   ---
   ```
   - New articles must use ID: `0000000000000000000000000000000000`
   - **description** field: Auto-generated by CI/CD, but if writing manually:
     - **Length**: 200-350 characters (optimal for SEO and meta tags)
     - **Structure**: Start with "Tallyfy [feature]..." then explain what/how
     - **Style**: Action verbs, specific terminology, no fluff
     - **Avoid**: Generic phrases like "This feature helps..." or "Learn how to..."
     - **Example**: "Tallyfy administrators can configure organization-wide working days and hours to automatically adjust task deadlines based on your business calendar."
   - **sidebar.order**: Use sequential numbers (1, 2, 3...) for articles within a section to control display order
   - **title**: Must be short, practical, and in sentence case with only first letter capitalized unless proper nouns
   - **lastUpdated**: Automatically updated from Git history by GitHub Actions (YYYY-MM-DD format)
   - **CRITICAL Title vs. Heading Rule**: The frontmatter title MUST be different from the main H2 heading
     - Title: Short and practical (e.g., "Create a table of contents")
     - H2 Heading: Slightly different, clarifying context (e.g., "Using table of contents in Tallyfy")
     - **VIOLATION EXAMPLE from actual codebase** (`/pro/integrations/extract-tasks-from-meetings.mdx`):
       - ❌ BAD: Title: "Extract tasks" → Heading: "# Extract tasks from meetings (Coming Soon)" (just adds words)
       - ✅ BETTER: Title: "Extract tasks from meetings" → Heading: "# Converting meeting recordings into actionable tasks" (different angle)
       - The heading should provide a different perspective, not just extend the title with more words

2. **Component Imports**:
   - **Required placement**: Immediately after the frontmatter YAML, before any content
   - **For Related articles**: `import { CardGrid, LinkTitleCard } from "~/components";`
   - **For procedural content**: `import { Steps } from '@astrojs/starlight/components';`
   - **For tabs/asides**: `import { Tabs, TabItem, Aside } from '@astrojs/starlight/components';`
   - **For navigation trees in index pages**: `import PageTree from '@/components/PageTree.astro';` then use `<PageTree />` to display child pages
   - **Multiple imports example**:
     ```markdown
     ---
     title: Your article title
     ---
     
     import { CardGrid, LinkTitleCard } from "~/components";
     import { Steps } from '@astrojs/starlight/components';
     import PageTree from '@/components/PageTree.astro';
     
     ## Your content starts here
     ```
   - **CRITICAL**: Missing imports will cause build failures - always check if components are used but not imported

3. **Content Hierarchy**:
   - Start with H2 (`##`), never H1
   - Don't skip heading levels (H2 → H3 → H4)
   - **Remove trademark symbols**: Never use Tallyfy<sup>®</sup> - always just "Tallyfy" without any trademark notation

4. **Heading Sentence Case Rules** (MANDATORY):

   All headings at ALL levels (##, ###, ####) MUST use sentence case. This makes content look less AI-generated and more human-written.

   **What sentence case means:**
   - Only the FIRST word is capitalized
   - Proper nouns remain capitalized
   - Acronyms remain ALL CAPS
   - Everything else is lowercase

   **Always capitalize:**
   - First word of the heading
   - **Proper nouns**: Tallyfy, Microsoft, Windows, Google, Azure, Zapier, Power Automate, SharePoint, Chrome, Firefox, Safari, AWS, etc.
   - **Product names**: Claude, ChatGPT, OpenAI, GitHub, Salesforce, HubSpot, Slack, Teams, etc.
   - **Acronyms**: API, RPA, SSO, OAuth, HTTP, ID, CSV, JSON, SQL, SLM, VRAM, CRM, ERP, etc.

   **Never capitalize (unless first word):**
   - Generic terms: workflow, process, task, template, automation, integration
   - Descriptive words: advanced, basic, comprehensive, complete, simple
   - Actions: creating, using, understanding, getting, building
   - After colons: the word following a colon is lowercase unless it's a proper noun

   **Examples:**

   ✅ CORRECT:
   - `## How to create a template` (only first word capitalized)
   - `### Understanding Power Automate basics` (Power Automate is proper noun)
   - `### Getting started with Claude computer use` (Claude is proper noun)
   - `## API endpoint reference` (API is acronym)
   - `### Example workflow: restaurant reservation` (lowercase after colon)
   - `### Microsoft UFO2: enterprise-grade Windows integration` (proper nouns kept)

   ❌ INCORRECT:
   - `## How To Create A Template` (Title Case - every word capitalized)
   - `### Understanding Power Automate Basics` (Basics should be lowercase)
   - `### Getting Started With Claude Computer Use` (Started, With, Computer, Use should be lowercase)
   - `## API Endpoint Reference` (Endpoint, Reference should be lowercase)
   - `### Example Workflow: Restaurant Reservation` (Workflow, Restaurant, Reservation should be lowercase)

5. **Related Articles Section** (CRITICAL RULES):
   
   ⚠️ **ABSOLUTE PROHIBITION FOR EXISTING ARTICLES**: 
   - **NEVER EVER modify the Related articles section in existing articles**
   - **This section is AUTOMATICALLY GENERATED by GitHub Actions**
   - **Any manual changes WILL BE OVERWRITTEN**
   - **DO NOT touch even if descriptions seem wrong or spacing is off**
   - **The ONLY exception**: When creating a NEW article that doesn't exist yet
   
   - **For NEW articles ONLY**: Can include initial sample Related articles section
   - **For EXISTING articles**: HANDS OFF - no exceptions, no edits, no fixes
   - **Required format**:
     ```markdown
     ## Related articles
     <CardGrid>
     <LinkTitleCard header="<b>Category > Title</b>" href="/full/path/to/article/" > Description of the article content. </LinkTitleCard>
     </CardGrid>
     ```
   - **Import requirement**: Must have `import { CardGrid, LinkTitleCard } from "~/components";` at top of file
   - **Header format**: Use category prefix like "API >", "Members >", "Settings >"
   - **URLs**: Always include trailing slash in href
   - **Descriptions**: Write complete sentences describing the article content
   - **GitHub Actions Warning**: The `generate-related-articles.py` script runs automatically on GitHub and will overwrite ANY manual changes to Related articles sections

### Content Creation Rules
- Only create new articles when absolutely necessary
- When handling GitHub tickets, evaluate if documentation changes are needed
- Include prerequisites section for procedural articles
- Follow consistent structure based on content type (concept/task/reference/troubleshooting)
- **Directory structure requirement**: When creating new folders, always include an `index.mdx` file as the landing page for that directory to prevent build errors and provide proper navigation
- **Title formatting requirements**:
  - Use sentence case: Only capitalize first letter and proper nouns
  - Examples: "Create a table of contents" not "Create a Table of Contents"
  - Keep titles short and practical (under 60 characters when possible)
  - Make titles different from main H2 headings

### Content Automation System
This repository uses a sophisticated Python-based content automation system:

1. **Content IDs**: Generated server-side with MD5 hashes for unique page identification
2. **AI-Generated Descriptions**: `generate-snippets.py` uses Claude AI to create page descriptions
3. **Related Articles**: `generate-related-articles.py` fetches cross-references via Answers API
4. **Content Validation**: `markdown-lint.py` validates frontmatter structure and MDX syntax
5. **Last Updated Dates**: `update-last-modified.py` extracts Git modification dates for each file

### Content Validation
Run `python scripts/markdown-lint.py --dir src/content/docs` to validate frontmatter YAML structure, required fields, UUID format, and sidebar order requirements.

## WRITING STYLE GUIDELINES

### Core Humanization Framework

All AI-generated technical documentation must appear natural, human-written, and undetectable as AI-generated content. These guidelines are MANDATORY for all content operations.

#### Natural Voice & Conversational Tone

**Direct & Clear Communication**:
- **Write as if explaining to a colleague**: Use first and second person naturally
- **Conversational approach**: Include "you", "you're", "can't", "won't", "it's" throughout
- **Global accessibility**: Simple language understandable by a 20-year-old
- **Professional but friendly**: Avoid overly formal or academic language
- **No fluff or filler**: Every sentence must provide genuine value

**Human Connection Patterns**:
- **Empathetic acknowledgment**: "You might be wondering...", "This can be confusing..."
- **Shared experience**: "Most users find...", "A common question is..."
- **Reassuring guidance**: "Don't worry - this is straightforward", "You've got this"
- **Personal touches**: Brief, helpful asides that add human perspective

#### Sentence Structure & Natural Rhythm

**Burstiness and Flow Variation**:
- **Dramatic length variation**: Follow complex 30-word sentences with punchy 5-word ones
- **Natural speech patterns**: Mix detailed explanations with conversational breaks
- **Rhythm markers**: Every 3-4 paragraphs, include one notably short sentence (under 8 words)
  - Examples: "That's it." "Problem solved." "Here's how." "Simple." "Done."
- **Conversational pacing**: Allow for natural pauses and emphasis through structure

**Strategic Sentence Patterns**:
- **Opening impact**: Start sections with clear, direct statements
- **Building complexity**: Move from simple to complex within paragraphs
- **Emphasis through brevity**: Use short sentences for important points
- **Natural transitions**: Connect ideas with conversational bridges

**Advanced Rhythm Techniques**:
- **Paragraph length variation**: Mix 1-sentence paragraphs with 5-sentence ones
- **Asymmetric information density**: Some sections detail-heavy, others concise
- **Natural word clustering**: Group related terms in bursts rather than even distribution
- **Strategic repetition with variation**: Restate key concepts using different structures

#### Language Humanization Techniques

**Conversational Elements**:
- **Strategic fragments**: Use sparingly (1-2 per article) for emphasis
  - "Want to automate task assignments? Simple. Just configure the automation rules."
  - "The result? Significant reduction in process completion time."
- **Conversational asides in parentheses**: Add brief, helpful context
  - "(yes, it's that straightforward)"
  - "(not just specific people)"
  - "(this takes about 5 minutes)"
- **Rhetorical questions**: Use to introduce new sections or concepts
- **Natural connectors**: "Now here's the thing...", "But here's what's interesting..."

**Emotional Variation in Technical Content**:
- **Express appropriate emotions**:
  - Relief: "Finally, no more manual data entry"
  - Satisfaction: "This is where it gets good"
  - Understanding: "We know this part can be tricky"
- **Micro-reactions to common pain points**:
  - "(we've all been there)" after describing a tedious process
  - "Yes, it's really that simple" after a surprisingly easy solution
- **Enthusiasm markers**: Show genuine excitement about powerful features
  - "Here's my favorite part..."
  - "This next feature? Game-changer."
- **Empathetic acknowledgments**: Recognize user challenges
  - "If you're thinking this sounds complex, stay with me"
  - "Nobody likes reading error messages, but..."

**Rhythm and Emphasis Tools**:
- **Spaced hyphens for natural speech**: Use ( - ) not em-dashes (—) or en-dashes (–)
  - "Templates define your process - think of them as reusable blueprints - while processes are running instances"
- **Personal phrasing within professional bounds**: Ground claims in experience
  - "After helping many companies implement workflows, we've found..."
  - "You'll notice the difference immediately - tasks that took hours now take minutes"
- **Intentional repetition for clarity**: Restate complex concepts in simpler terms

#### Answer-First Content Structure

**Immediate Value Delivery (Critical for Natural Flow)**:
- **Complete answer in first 2-3 sentences**: Solve the user's problem immediately
- **Direct solution statement**: State what to do before explaining why
- **Context follows action**: Provide the "how" first, then the "why"
- **Front-loaded key information**: Most critical details in first 50 words

**Natural Information Architecture**:
```
Structure Pattern:
1. Direct Answer (1-2 sentences): Immediately solve the problem
2. Brief Context (1 sentence): Why/when this matters
3. Detailed Explanation: Expand with steps, examples, edge cases
```

Example:
- **Good**: "To assign a task in Tallyfy, click the **Assign** button on any task card and select team members from the dropdown. This ensures the right people are notified immediately."
- **Bad**: "Task assignment is an important feature in Tallyfy. Let's explore how the system handles this important process."

#### Technical Concept Humanization

**Making Complex Ideas Accessible**:
- **Analogies for technical concepts**: Connect abstract ideas to familiar experiences
  - "Templates are like reusable blueprints for your business processes"
  - "Think of it as creating a digital assembly line for office work"
- **Concrete specificity**: Replace vague statements with evidence and examples
  - Bad: "Some experts say this feature improves productivity"
  - Good: "Customer case studies show this feature reduces task completion time significantly"

**⚠️ CRITICAL RULE - NEVER FABRICATE STATISTICS**:
- **ONLY use real data**: Statistics, percentages, and specific numbers must come from verifiable sources
- **No invented metrics**: Never make up accuracy percentages, time savings, or research findings
- **Qualitative over false precision**: Use "significant", "many", "often" instead of fake numbers
- **Examples of fabrication to avoid**:
  - ❌ "98% accuracy" (unless from real testing data)
  - ❌ "Reduces time by 40%" (unless from actual case studies)
  - ✅ "Significantly improves accuracy"
  - ✅ "Reduces processing time"

**Clear Technical Communication**:
- **Subject-verb proximity**: Keep subjects and verbs close together at sentence beginning
  - Bad: "The system, after checking user permissions and validating data integrity, sends an email"
  - Good: "The system sends an email after checking permissions and validating data"
- **Active voice consistency**: "The system sends an email" not "An email is sent"
- **Clear pronoun references**: Ensure "this", "that", "these" have obvious antecedents

#### Statistical AI Detection Patterns (Research-Based)

**Based on GPTZero analysis of 3.3 million texts, these words appear 10x to 200x more frequently in AI content:**

**Tier 1 - Worst Offenders (200x+ frequency) - NEVER USE**:
- delve, navigate (figurative), landscape, tapestry, multifaceted

**Tier 2 - High Frequency (50-200x) - AVOID**:
- pivotal, comprehensive, seamless, robust, leverage, facilitate, paramount, meticulous, unwavering

**Tier 3 - Transition Words (20-50x) - LIMIT SEVERELY**:
- moreover, furthermore, indeed, subsequently, additionally

**Tier 4 - Opening Phrases (Dead Giveaways) - NEVER START WITH**:
- "In today's fast-paced digital world..."
- "This serves as a testament to..."
- "Let's dive into..."
- "As we navigate..."

**Syntax Patterns That Reveal AI**:

**"Not X, but Y" Emphatic Contrast** - AI overuses this. Limit to ONCE per article maximum:
- ❌ AI pattern: "Success is not about talent. It is about persistence."
- ✅ Human: "Persistence matters more than raw talent."

**Participial Phrase Formula** - Pattern: "Subject + verb + object, present participle + detail":
- ❌ AI pattern: "She entered the room, carrying a stack of papers."
- ❌ AI pattern: "The system processes data, ensuring accuracy at every step."
- ✅ Human: "She walked in with papers under her arm."

**Correlative Conjunctions** - Sound robotic when overused:
- Limit severely: "whether...or", "neither...nor", "not only...but also"

**Why This Matters: Perplexity and Burstiness**

AI detection works by measuring two things:
1. **Perplexity**: How surprising word choices are (AI picks statistically probable words)
2. **Burstiness**: How much sentence length varies (AI maintains eerily uniform lengths)

**The Gary Provost Demonstration**:
> "This sentence has five words. Here are five more words. Five-word sentences are fine. But several together become monotonous. Listen to what is happening. The writing is getting boring."
>
> "Now listen. I vary the sentence length, and I create music. Music. The writing sings."

This is why we vary dramatically between 3-word punches and 30-word explorations.

#### Documentation-Specific Humanization

**Procedural Content**:
- **Action-oriented language**: Start instructions with strong verbs
- **One idea per step**: Keep instructions focused and clear
- **Context provision**: "In the **Dashboard**, click..." (location before action)
- **Verification steps**: Include "You should see..." confirmations
- **Expected outcomes**: State what happens after each major step

**Strategic Reader Engagement**:
- **Progress indicators**: "We're halfway there" or "One more step"
- **Checkpoint questions**: "See the green checkmark? Perfect."
- **Anticipatory guidance**: "Before you click save, double-check..."
- **Success moments**: "You've just automated your first workflow"
- **Troubleshooting preemption**: "Not seeing the button? Make sure you're in edit mode"

#### High Information Density

**Value-Packed Content**:
- **Every sentence must add value**: No filler or redundant information
- **Specific over general**: Use concrete examples and measurable outcomes
- **Problem-focused writing**: Address actual user challenges
- **Strategic organization**: Front-load critical information

**Efficient Communication**:
- **Paragraph guidelines**: 3-5 sentences maximum, 50-120 words
- **One idea per paragraph**: Maintain focus and clarity
- **Scannable structure**: Use headings, lists, and formatting strategically
- **Clear section transitions**: Connect ideas logically

#### Entity Reinforcement & Brand Voice

**Natural Brand Integration**:
- **Use "Tallyfy" 3-5 times per article**: Never "the platform", "the system", "our tool"
- **Feature connection**: "Tallyfy's automation engine" not just "the automation engine"
- **Benefit-focused language**: Connect features to user outcomes
- **Conversational brand voice**: Confident but approachable, never arrogant

#### Quality Assurance Checklist

**Pre-Publication Humanization Checklist**:
- [ ] **Read-aloud test**: Content sounds natural when spoken
- [ ] **Sentence variety**: Mix of 3-30 word sentences throughout
- [ ] **Conversational elements**: At least 3 contractions, questions, or asides
- [ ] **Specific details**: Includes concrete examples (from real sources only)
- [ ] **No fabricated data**: All statistics and percentages are from verifiable sources
- [ ] **No AI patterns**: Eliminates all typical AI-generated phrases
- [ ] **Clear pronoun references**: All "this", "that" have obvious antecedents
- [ ] **Answer-first structure**: Value delivered in first 2-3 sentences
- [ ] **Natural rhythm**: Includes rhythm markers and varied pacing

#### Multi-Pass Rewriting Strategy

1. **Initial Generation**: Create base technical content
2. **Humanization Pass**: Add emotional variation and engagement elements
3. **Pattern Breaking Pass**: Identify and disrupt repetitive structures
4. **Voice Consistency Pass**: Ensure brand voice throughout
5. **Final Polish**: Add micro-touches that enhance naturalness

---

### Critical Content Quality Rules - NO FLUFF ALLOWED

**MANDATORY**: Every article must follow these anti-fluff guidelines:

#### Title Guidelines
- **NO "Complete guide to..."** - Just use clear, descriptive titles
- **NO "How to master..."** - Use direct action phrases
- **Keep titles under 60 characters** when possible
- **Examples**:
  - Bad: "Complete guide to task assignment options"
  - Good: "Task assignment options"
  - Bad: "How to master workflow automation"
  - Good: "Workflow automation"

#### Heading Guidelines  
- **Use varied, meaningful headings** that add context
- **Avoid repetitive question patterns** like "How do I..." for every section
- **Make headings actionable and clear**
- **Examples**:
  - Bad: "How do I master task assignment options in Tallyfy?"
  - Good: "Options for assigning tasks"
  - Bad: "What are the benefits of using Tallyfy?"
  - Good: "Key benefits"

#### Content Elimination Rules
**IMMEDIATELY DELETE these types of sentences**:
- Empty benefit statements without evidence
  - Delete: "Good task assignment makes a huge difference for team productivity and getting work done efficiently."
  - Delete: "This feature will transform how your team works."
  - Delete: "Proper configuration is crucial for success."
  
- Vague promises without specifics
  - Delete: "This guide covers everything you need to know."
  - Delete: "Master these concepts to become more productive."
  - Delete: "Understanding this is key to getting the most out of Tallyfy."

- Unnecessary meta-commentary
  - Delete: "Let's explore how this works."
  - Delete: "In this section, we'll cover..."
  - Delete: "Now let's dive into..."

#### What to Keep
**ONLY include sentences that**:
- Provide specific instructions or steps
- State concrete facts or numbers (from real sources - NEVER fabricate data)
- Explain actual functionality
- Give real examples
- Solve specific problems
- Answer direct questions

**⚠️ CRITICAL RULE ON STATISTICS**: 
- ONLY use statistics, percentages, or specific numbers when you have real, verifiable sources
- NEVER invent or fabricate data points, accuracy percentages, or research findings
- If no real data exists, use qualitative descriptions instead ("significant", "many", "often")
- Better to be vague than to be falsely precise with made-up numbers

#### Practical Meaningfulness Test
Before including ANY sentence, ask:
1. Does this sentence help the user complete a task?
2. Does it provide specific, actionable information?
3. Would removing it make the article less useful?
4. Is there evidence or specificity backing any claims?

If the answer to ANY of these is "no", DELETE THE SENTENCE.

### Acceptable Writing Patterns (Often Mistaken as "AI-Like")

These patterns are effective when used intentionally with substance:

- **Intentional repetition for clarity**: Repeating complex concepts in simpler terms
  - Good: "Vector databases store embeddings - mathematical representations that capture meaning. In other words, vector databases help find results that are 'close' in meaning, not just exact text matches."
- **Signposting phrases**: Use when followed by valuable content
  - Good: "Essentially, instead of classifying the document as a whole, we classify each section independently."
  - Only use when the following content genuinely clarifies or adds value
- **Parallel structure**: For organizing related ideas
  - Good: "The system scales across inputs, stays responsive under load, and returns consistent results even with noisy prompts."
- **Declarative openings**: Bold claims work when backed by evidence
  - Good: "LLM evaluations are hard to get right. Many rely on user-defined gold labels or vague accuracy metrics, which fail for subjective or multi-step tasks."
- **Hyphens for rhythm and clarity**: Use spaced hyphens for emphasis and natural speech patterns
  - Good: "Templates define your process - think of them as reusable blueprints - while processes are the actual running instances."
  - **Important**: Always use regular hyphens with spaces ( - ) not em-dashes (—) or en-dashes (–)
  - Format: `space hyphen space` like "this - not this—or this–"
- **Strategic fragments for emphasis**: Occasionally use sentence fragments for impact (use EXTREMELY sparingly)
  - Good: "Want to automate task assignments? Simple. Just configure the automation rules in your template."
  - Good: "The result? A 40% reduction in process completion time."
  - Only use 1-2 fragments per article maximum, and only when it genuinely adds emphasis
- **Conversational asides with parentheses**: Add brief, helpful context in a natural voice
  - Good: "You can assign tasks to job titles (not just specific people), which means new team members automatically get the right work."
  - Good: "The API returns results in JSON format (yes, it's that straightforward)."
  - Keep asides brief and genuinely helpful—never forced
- **Personal phrasing within professional bounds**: Use specific, experience-based language
  - Good: "After helping 500+ companies implement workflows, we've found that simple templates work best."
  - Good: "You'll notice the difference immediately—tasks that took hours now take minutes."
  - Ground claims in concrete experience or data

## CONTENT ORGANIZATION

### Document Structure
- **Focused content**: One main topic per article
- **Clear sections**: Descriptive headings and subheadings
- **Logical flow**: Include transitions between sections
- **Front-loaded information**: Key points first
- **Paragraph guidelines**:
  - 3-5 sentences maximum
  - 50-120 words per paragraph
  - One idea per paragraph
- **High information density**: Every sentence must provide value
  - Bad: "As someone who manages workflows, you've probably noticed inefficiencies. This post guides you through optimization. We'll cover the pitfalls that make processes feel slow."
  - Good: "Manual task assignment wastes 2 hours daily for most managers. Here's how to automate assignments based on workload and expertise."
- **Strategic bullet points**: Use lists only when items are truly parallel and independent
  - Overuse of nested bullets makes content harder to scan
  - When ideas connect or need context, use paragraphs instead
  - Reserve bullets for truly independent items like feature lists or prerequisites

### Content Types
- **Conceptual**: What and why
- **Procedural**: How-to instructions
- **Reference**: Technical details
- **Troubleshooting**: Problem/cause/solution format

### Emphasis & Highlighting
- Limit to 1-3 emphasized items per page
- Use **Note:** prefix for important tips
- Convert key insights to list items for scannability

## FORMATTING CONVENTIONS

### Text Formatting
- **Bold** (`**text**`): UI elements (buttons, menus, fields, options)
- *Italics* (`*text*`): New terms with definitions, placeholders
- `Code` (`` `text` ``): Code snippets, commands, literal text
- No quotes for UI elements
- No underlining (reserved for links)

### Markdown Elements
- **Headings**: Start with `##` (H2), maintain hierarchy
- **Lists**: 
  - Bullets (`-` or `*`) for unordered items
  - Numbers for sequential steps
  - Indent 4 spaces for sub-items
- **Callouts**: Use sparingly
  ```markdown
  :::note[Title]
  Content
  :::
  ```
- **Videos**:
  ```html
  <lite-vimeo videoid="905736219"></lite-vimeo>
  ```

### Code Block Language Identifiers (CRITICAL)

**Syntax highlighting uses Shiki** (200+ languages supported via VS Code engine). Using unsupported languages causes build failures.

#### ✅ APPROVED Languages (Use These)

**Primary (High Confidence)**:
- `javascript`, `typescript`, `json`, `yaml`, `python`, `bash`, `shell`
- `html`, `css`, `xml`, `markdown`, `sql`

**Programming Languages**:
- `java`, `go`, `csharp`, `cpp`, `c`, `rust`, `ruby`, `php`, `swift`, `kotlin`

**Specialized**:
- `d2` (diagrams), `graphql`, `http`, `dockerfile`, `toml`, `ini`
- `powershell`, `diff`, `csv`, `dax` (Power BI)

**Plain Text (No Highlighting)**:
- `text`, `txt`, `plain` - Use for unsupported formats or sample outputs

#### ❌ NEVER USE (Not Supported - Cause Build Failures)

| Invalid | Use Instead | Reason |
|---------|-------------|--------|
| `lookml` | `yaml` | LookML is YAML-based |
| `urscript` | `python` | URScript is Python-like |
| `email` | `text` | Not a programming language |
| `config` | `ini` or `yaml` | Use specific format |
| `output` | `text` | Use plain text |
| `terminal` | `bash` or `text` | Use bash for commands |

#### Fallback Rules

1. **Unknown language?** → Use `text` (safe fallback, bypasses highlighting)
2. **Proprietary syntax?** → Find closest standard (YAML, Python, JSON)
3. **Sample output/logs?** → Use `text` or `json`
4. **Email/letter/document format?** → Use `text`

#### Validation

- **Full language list**: https://shiki.style/languages
- **Local validation**: Run `python scripts/markdown-lint.py --dir src/content/docs`
- **If unsure**: Check the Shiki list or use `text`

### Special Components
- **Steps Component**: Only for product instructions
  ```markdown
  <Steps>
  1. Single-level hierarchy only
  2. Images must be inside list items
  </Steps>
  ```
  - Example with image:
  ```markdown
  1. **Step 1:** Configure your settings.
     
     ![Screenshot description](mdc:image-url.png)
  ```

## INSTRUCTIONAL CONTENT

### Writing Procedures
- Start with action verbs: "Click **Submit**"
- One action per step
- Include context: "In the **Dashboard**, click..."
- Mark optional steps: "*(Optional)* If you want to..."
- Add verification steps
- Include prerequisites at beginning
- State expected outcomes

### Images & Screenshots
- **When to use**: Only when adding clarity
- **Requirements**:
  - Descriptive alt text
  - Brief introduction before image
  - Annotations (arrows, circles) for key elements
  - High quality, legible text
  - Cropped to relevant portions
- **Alt text format**: `![Tallyfy dashboard showing workflow](mdc:image.png)`

### Examples & Code
- Use realistic scenarios (e.g., "ACME Corp")
- Include comments in code samples
- Ensure valid, properly formatted code
- Show complete functionality
- Include expected outputs
- Use appropriate markdown syntax for code blocks

### Advanced Writing Techniques

- **SWBST Pattern** (Somebody Wanted But So Then): Use for explaining decisions or system evolution
  - Somebody: The actor (user, team, system)
  - Wanted: The goal
  - But: The obstacle
  - So: The response
  - Then: The outcome
  - Example: "We used GPT-4 for summarization. We wanted fluent answers, but it hallucinated facts. So we added a retrieval step. Then we re-ranked outputs based on citation accuracy."
- **Contribution commensurate with length**: Ensure value matches article length
  - A 500-word article must provide 500 words of genuine insight
  - Cut content that doesn't directly serve the reader's goal
  - Ask: "Will the reader feel their time was well spent?"


## LINKING & REFERENCES

### Internal Links
- **Format**: Absolute paths without .mdx extension
- **Example**: `/products/pro/tracking-and-tasks/processes/`
- **Public Production URL**: Base URL is `https://tallyfy.com/products/`
- **Public Staging URL**: Base URL is `https://staging.tallyfy.com/products/`
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

## ACCESSIBILITY & INCLUSIVITY

### Inclusive Language
- Gender-neutral pronouns ("they" not "he/she")
- No ableist or biased terms
- Diverse examples and scenarios
- No exclusionary or discriminatory language

### Accessibility Requirements
- Don't rely on sensory characteristics ("click **Start**" not "click the green button")
- Always include image alt text
- Standard capitalization for screen readers
- Proper heading structure for navigation
- State required prior knowledge explicitly

## SEO & AI OPTIMIZATION

### Technical SEO Writing Rules

**URL-Friendly Titles**:
- Use descriptive, keyword-rich titles that work as URLs
- Example: "How to Assign Tasks in Tallyfy" → `/how-to-assign-tasks/`
- Avoid special characters, numbers, or dates in titles
- Keep titles under 60 characters

**Search-Optimized Content Patterns**:

**HowTo Content Pattern**:
```markdown
## How to [specific action]

**Time required**: 5 minutes
**Difficulty**: Easy
**Prerequisites**: Administrator or Standard user role

### Steps

1. **Navigate to Templates**: Click the **Templates** tab in the main menu
2. **Create New Template**: Select **Create New** button
3. **Configure Settings**: Add your process steps and automation rules
```

**FAQ Content Pattern**:
```markdown
## Frequently Asked Questions

### Can I assign tasks to multiple people?

Yes, use the group assignment feature. Click **Assign** and select **Group Assignment** to assign the same task to multiple team members.

### How do I track task progress?

The tracker view provides real-time visibility. Navigate to **Tracker** to see all running processes and their current status.
```

### Content Structure for AI
- Small, focused semantic chunks (300-500 words per section)
- Descriptive headings formatted as questions when appropriate
- Standalone paragraphs that make sense out of context
- Front-loaded key information in first 50 words
- Clear subject-verb-object sentences
- Include specific numbers and data points when available

### Optimization Techniques
- Natural keyword variations (e.g., "workflows", "processes", "procedures")
- Entity mentions: Always use "Tallyfy" not "the platform" or "our tool"
- Parenthetical explanations for acronyms: "Service-Level Agreement (SLA)"
- Structured formats (lists, tables, steps) for easy parsing
- Semantic HTML: proper use of `<article>`, `<section>`, `<nav>`
- Internal linking with descriptive anchor text (3-5 per article)


### LLM-Specific Optimization Patterns

**Conversational Markers for AI Understanding**:
- Start procedural content with "To [achieve goal]:" followed by steps
- Use "For example:" to introduce concrete scenarios
- Include "Note:" for important contextual information
- Add "Prerequisites:" sections for complex procedures

**Citation-Worthy Content Structure**:
- **Claim + Evidence**: "Tallyfy automates task assignment based on workload and availability"
- **Problem + Solution**: "If tasks are getting stuck, enable automatic reassignment in the automation rules"
- **Question + Direct Answer**: Use H2/H3 headings as questions when appropriate

**Entity Reinforcement**:
- Mention "Tallyfy" 3-5 times per article naturally
- Connect features to Tallyfy explicitly: "Tallyfy's automation engine" not just "the automation engine"
- Build topic clusters around core entities (templates, processes, automations)

**Semantic Completeness**:
- Define terms on first use: "Templates (reusable process blueprints) help standardize workflows"
- Include related concepts: When discussing tasks, mention assignments, deadlines, and notifications
- Create mini-glossaries for complex topics

**Required Context Clusters**:
When discussing any feature, include ALL related concepts:

*Task Discussion Must Include*:
- Assignment methods (individual, group, job title)
- Due dates and deadline management
- Form fields and data collection
- Comments and collaboration features
- Dependencies and prerequisites
- Completion criteria and validation

*Template Discussion Must Include*:
- Creation and configuration process
- Step/task setup
- Assignment rules and logic
- Automation options
- Launch procedures
- Version control and updates

**LLM Selection Triggers**:
- Use specific numbers: "5 steps", "10-minute setup", "3 approval levels"
- Include comparison phrases: "Unlike spreadsheets, Tallyfy provides..."
- Add outcome statements: "This results in...", "The benefit is..."
- Use if-then constructions: "If you need X, then Tallyfy's Y feature..."
- Problem-solution pairs: "Can't track progress? Tallyfy's dashboard shows real-time status"
- Feature-benefit connection: "Automatic reminders ensure deadlines are never missed"
- Use case specificity: "For HR onboarding, Tallyfy provides complete checklists"

## TROUBLESHOOTING CONTENT

### Format
- Clear problem/cause/solution structure
- Use tables or lists for multiple issues
- Include exact error messages in `code` format
- Specific solutions (not "check your settings")
- Preventative measures when applicable
- Link to support resources for complex issues


## LAST UPDATED DATES SYSTEM

### Overview
Every documentation page displays its last modification date, automatically maintained through Git history. This provides transparency about content freshness for users and improves SEO.

### How It Works
1. **GitHub Actions Workflow** (`answers.yml`):
   - Runs on every commit to main branch
   - Executes `update-last-modified.py` script
   - Extracts last modified date from Git history for each MDX file
   - Updates `lastUpdated` field in frontmatter

2. **Date Format**:
   - Format: `YYYY-MM-DD` (e.g., `2025-08-15`)
   - Stored in frontmatter: `lastUpdated: 2025-08-15`
   - Displayed as: "Last updated: August 15, 2025"

3. **Automation Benefits**:
   - No manual date maintenance required
   - Accurate dates based on actual Git commits
   - Consistent across all 600+ documentation files
   - Automatically synced to rendering repository

### Script Usage
```bash
# Update all lastUpdated dates from Git history
python scripts/update-last-modified.py --dir=src/content/docs

# The script will:
# - Process all .mdx files recursively
# - Extract last commit date for each file
# - Update or add lastUpdated field in frontmatter
# - Skip files already up-to-date
# - Report summary of changes
```

### Important Notes
- Requires full Git history (`fetch-depth: 0` in GitHub Actions)
- Dates reflect when content was last modified in Git
- If a file has no Git history, it won't get a lastUpdated date
- The rendering repository (/support-docs) uses these dates from frontmatter


## CLAUDE CODE AUTOMATION PHILOSOPHY

### Overview

This codebase supports automated documentation workflows using Claude Code's non-interactive mode. Break large documentation tasks into atomic units that can be executed sequentially via command line, enabling systematic content updates without manual intervention.

### Non-Interactive Command Pattern

Execute specific documentation tasks using:
```bash
claude -p "YOUR_PROMPT_HERE" --dangerously-skip-permissions
```

This command runs Claude with a specific prompt, completes the task, and exits - perfect for scripting and automation.

### Task Queue Pattern

For large documentation projects, use a file-based task queue:

1. **Create prompt files**: Each `.prompt` file contains one specific documentation task
2. **Process sequentially**: Scripts read and execute prompts one by one
3. **Track progress**: Completed tasks are deleted or moved, making workflows resumable

Example directory structure:
```
doc_automation_queue/
├── 001_analyze_missing_docs.prompt
├── 002_create_api_reference.prompt
├── 003_update_changelog.prompt
└── completed/
```

### Example Automation Scripts

#### 1. Bulk Documentation Updates
```bash
#!/bin/bash
# process_doc_queue.sh

for prompt_file in doc_automation_queue/*.prompt; do
    echo "Processing: $prompt_file"
    
    # Read prompt and execute
    prompt=$(cat "$prompt_file")
    claude -p "$prompt" --dangerously-skip-permissions
    
    # Move completed
    mv "$prompt_file" doc_automation_queue/completed/
done
```

#### 2. Generate Missing Documentation
```python
#!/usr/bin/env python3
# generate_missing_docs.py

import subprocess
import os
from pathlib import Path

def generate_doc_for_feature(feature_path):
    prompt = f"""
    Create documentation for {feature_path} following the style guidelines in CLAUDE.md.
    Include: overview, prerequisites, step-by-step instructions, and troubleshooting.
    """
    
    subprocess.run([
        "claude", "-p", prompt, "--dangerously-skip-permissions"
    ])

# Process all features needing documentation
features = Path("src/content/docs/pro").glob("**/*.mdx")
for feature in features:
    if "TODO" in feature.read_text():
        generate_doc_for_feature(feature)
```

## Common Documentation Automation Patterns

1. **Changelog-Driven Updates**: Automatically update docs based on changelog entries
2. **Screenshot Updates**: Generate prompts to update screenshots when UI changes
3. **Cross-Reference Validation**: Verify all internal links remain valid
4. **Style Compliance**: Check and fix articles not following guidelines
5. **Missing Content Detection**: Identify and create stub articles for new features

## 📊 D2 Diagram Guidelines

**ALL D2 DIAGRAM CONTENT HAS BEEN MOVED**: See `/documentation/D2-DIAGRAMS.md` for complete D2 diagram guidelines, including:
- When to use diagrams (only 10-15% of articles)
- Mandatory notation rules and syntax requirements
- Color palettes and styling guidelines
- Mobile-friendly design patterns
- Complete diagram templates for OAuth, webhooks, processes, etc.
- Troubleshooting and debug commands
- ULTRATHINKING approach for diagram decisions

## DOCUMENTATION ASSET MANAGEMENT

### Overview

All documentation screenshots and media assets are hosted on Cloudflare R2 storage and served via the `screenshots.tallyfy.com` CDN. The asset management system in `scripts/asset_management/` automates the complete workflow for uploading, captioning, and inventory management. AI-generated captions are automatically injected into documentation images at build time.

**📋 Build-Time Integration**: See `/documentation/BUILD_TIME_ALT_TEXT_INTEGRATION.md` for complete technical documentation on how AI-generated captions are automatically added as alt text during the Astro build process.

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

```bash
# Automatic workflow: upload + AI captions + inventory update
cd /documentation/scripts/asset_management
python3 orchestrator.py upload \
  --file /path/to/screenshot.png \
  --key "tallyfy/pro/desktop-light-new-feature.png" \
  --articles "pro-feature-guide,pro-getting-started"
```

**Returns**:
- Public URL: `https://screenshots.tallyfy.com/tallyfy/pro/desktop-light-new-feature.png`
- AI-generated alt text, descriptive, and SEO captions
- Automatic inventory CSV update

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

The skill automatically generates three types of captions using Claude Vision:

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

**Current Inventory Stats**:
- Total assets: 812
- Active (used in docs): 290
- Orphaned (not referenced): 499
- Missing (404s): 23
- With AI captions: 288+

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

## QUICK REFERENCE CHECKLIST

Before submitting documentation:

### Content Structure & Writing
- [ ] Uses H2 for main headings, maintains hierarchy
- [ ] Answer-first structure: Complete answer in first 2-3 sentences
- [ ] Written in simple, clear language (20-year-old comprehension level)
- [ ] UI elements are **bold**
- [ ] One main topic per article
- [ ] High information density - every sentence adds value
- [ ] Active voice and present tense throughout
- [ ] Procedures start with action verbs
- [ ] Varied sentence lengths for natural rhythm

### D2 Diagrams (If Applicable)
- [ ] ULTRATHINKING applied - diagram truly adds value (10-15% of articles)
- [ ] Diagram type matches content (sequence for APIs, flowchart for logic)
- [ ] One idea per diagram, <30 nodes ideal
- [ ] Labels ≤5 words, verbs on edges
- [ ] At least 2 links added for navigation
- [ ] Placed appropriately (after overview, before steps, etc.)
- [ ] Includes "What to notice" bullets after diagram
- [ ] Mobile-friendly and readable on small screens
- [ ] Uses appropriate flow direction (vertical for mobile, horizontal only when necessary)

### Content Optimization
- [ ] "Tallyfy" mentioned 1-3 times naturally (not "the platform")
- [ ] Answer provided in first 2-3 sentences
- [ ] Title under 60 characters when possible
- [ ] Includes specific numbers where available (NEVER fabricate statistics - only use real, verifiable data)
- [ ] Front-loads key information in first paragraph
- [ ] Uses natural keyword variations
- [ ] Includes 3-5 internal links with descriptive anchor text
- [ ] All related concepts included when discussing a feature
- [ ] Content follows HowTo or FAQ patterns when applicable

### Technical Requirements
- [ ] Component imports included after frontmatter when needed
- [ ] Links use absolute paths without .mdx extension
- [ ] Images include descriptive alt text
- [ ] New directories include `index.mdx` files
- [ ] Content automation scripts run successfully
- [ ] No empty summary sentences at paragraph ends
- [ ] Uses spaced hyphens ( - ) not em-dashes (—)

### Quality Checks
- [ ] Pronouns (this, that) have clear references
- [ ] Specific examples instead of vague claims
- [ ] Subject-verb proximity maintained
- [ ] Bullet points used strategically, not excessively
- [ ] Technical terms are real and established
- [ ] Content length justified by value provided
- [ ] Prerequisites stated for complex procedures
- [ ] Expected outcomes clearly defined

## PR Review Intelligence

### Code Change Minimization (ABSOLUTE PRIORITY)

**Fundamental Principle**: Every PR must implement the MINIMAL content changes necessary to properly address the issue.

**Review Requirements**:
- **MINIMIZE CHANGES** - only modify what's necessary to fix the content issue
- **No Scope Creep** - implement only what's specified in the issue
- **Preserve Existing Structure** - follow established documentation patterns
- **Targeted Fixes** - address the specific problem without rewriting entire articles

### Documentation-Specific Review Focus

**Critical Review Areas**:
1. **MDX Syntax**: Valid frontmatter, correct imports, proper component usage
2. **Link Validation**: Internal links point to existing files, trailing slashes present
3. **Heading Structure**: H2 start, no skipped levels, sentence case
4. **Content Quality**: No AI-typical phrases, answer-first structure, high information density
5. **Asset References**: Screenshot URLs resolve, alt text present

### Common Anti-Patterns to Reject

1. **Scope Creep**: Editing unrelated sections while fixing a specific issue
2. **Related Articles Edits**: These are auto-generated - NEVER manually modify
3. **AI-Typical Phrases**: "delve", "leverage", "comprehensive", etc.
4. **Fabricated Statistics**: All numbers must be from verifiable sources
5. **Broken Links**: Always validate internal link targets exist
6. **Missing Imports**: Components used but not imported at top of file

### PR Review Checklist

- [ ] Changes are minimal and targeted to the issue
- [ ] No unnecessary rewriting beyond scope
- [ ] MDX syntax valid (frontmatter, imports, components)
- [ ] Internal links validated (exist and have trailing slashes)
- [ ] Heading structure correct (H2 start, no skipped levels)
- [ ] Sentence case used in all headings
- [ ] No AI-typical phrases present
- [ ] No fabricated statistics or percentages
- [ ] Related articles section NOT modified
- [ ] Screenshots have proper alt text

### Content Quality Gates

**Before Approving Any Documentation PR**:
1. Run `python scripts/validate-internal-links.py --dir src/content/docs`
2. Run `python scripts/markdown-lint.py --dir src/content/docs`
3. Verify frontmatter fields are valid
4. Check that any new component imports are present
5. Confirm no manual edits to Related articles sections