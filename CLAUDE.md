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

A production-ready system exists at `/temporary/footnote-annotator/` for batch processing. For individual articles during creation/editing, manually apply the protocol above.

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
URL: https://staging.products.tallyfy.com/products/pro/integrations/extract-tasks-from-meetings/
Path: documentation/src/content/docs/pro/integrations/extract-tasks-from-meetings.mdx

URL: https://tallyfy.com/products/pro/tracking-and-tasks/tasks/
Path: documentation/src/content/docs/pro/tracking-and-tasks/tasks/index.mdx
```

**Conversion Rules**:
1. Remove domain (`https://staging.products.tallyfy.com/` or `https://tallyfy.com/`)
2. Remove `/products/` prefix
3. Add relative base path: `documentation/src/content/docs/`
4. If URL ends with a specific page name: add `.mdx`
5. If URL ends with `/`: look for `index.mdx` in that directory

**Examples** (relative to GitHub root directory):
- `https://staging.products.tallyfy.com/products/pro/integrations/extract-tasks-from-meetings/`
  → `documentation/src/content/docs/pro/integrations/extract-tasks-from-meetings.mdx`
- `https://tallyfy.com/products/pro/documenting/templates/`
  → `documentation/src/content/docs/pro/documenting/templates/index.mdx`
- `https://staging.products.tallyfy.com/products/manufactory/overview/`
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
   - **description** field is generated server-side
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
   - All headings use sentence case (lowercase except proper nouns)
   - **Remove trademark symbols**: Never use Tallyfy<sup>®</sup> - always just "Tallyfy" without any trademark notation

4. **Related Articles Section** (CRITICAL RULES):
   
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

**CRITICAL**: All writing must follow the comprehensive humanizing guidelines in `humanizing-rules.md`. The rules below supplement but do not replace the humanizing requirements.


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

### Language Rules (Following Humanizing Guidelines)

**MANDATORY**: Apply ALL language rules from `humanizing-rules.md` including:
- Conversational tone with natural speech patterns
- Dramatic sentence length variation (3-30 words)
- Strategic use of contractions and colloquial language
- Specific examples with concrete details
- Elimination of AI-typical phrases

**Additional technical writing requirements**:
- **Active voice**: "The system sends an email" not "An email is sent by the system"
- **Present tense**: For instructions and descriptions
- **American English**: Spelling and grammar
- **Global audience**: No idioms, cultural references, or colloquialisms
- **Specific nouns**: Replace "it", "this", "the platform" with "Tallyfy", "the template", etc.
- **Clear pronoun references**: Apply humanizing-rules.md guidelines for pronoun clarity

### Words to Avoid (From Humanizing Rules)

**CRITICAL**: Follow ALL avoidance guidelines in `humanizing-rules.md` including:
- All AI-typical sentence starters and phrases
- Corporate jargon and empty buzzwords
- Vague statements without concrete evidence
- Made-up technical terminology
- Empty summary sentences
- Overused AI adjectives without context

**See humanizing-rules.md for complete list of words, phrases, and patterns to avoid.**

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
- **Public Staging URL**: Base URL is `https://staging.products.tallyfy.com/products/`
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

### Claude AI Best Practices (2025 Edition)

### CRITICAL: Core Requirements for Every Session

#### 1. ALWAYS Use Ultrathinking
- **MANDATORY**: Every task requires deep thinking ("ultrathink") before action
- **Think First**: Use extended thinking modes for complex problems
- **Multi-Step Analysis**: Break down problems systematically before coding
- **Reasoning Transparency**: Make your reasoning process visible and auditable

#### 2. ALWAYS Plan and Create Todo Lists
- **Before ANY Task**: Create a comprehensive todo list breaking down the work
- **Track Progress**: Mark items as in_progress when starting, completed when done
- **Atomic Tasks**: Each todo item should be a single, specific, completable action
- **Sequential Execution**: Complete current task before starting the next

#### 3. Work Sequentially to Avoid Tool Errors
- **One Tool at a Time**: Execute tools sequentially unless operations are truly independent
- **Avoid Parallel Conflicts**: Don't run multiple file edits or dependent operations simultaneously
- **Chain Dependencies**: Use && for dependent bash commands, separate calls for independent ones
- **Verify Before Proceeding**: Check outputs before moving to next step

### Preventing Hallucinations and Ensuring Accuracy

#### Verification Strategies
- **Search Online When Uncertain**: Use WebSearch to verify facts, APIs, or current best practices
- **Cross-Reference Documentation**: Always check official docs for library usage
- **Test Code Before Finalizing**: Run tests to verify functionality
- **Quote Sources**: When referencing documentation, quote exact text

#### Anti-Hallucination Techniques
- **Admit Uncertainty**: Say "I need to verify this" rather than guessing
- **Extract Quotes First**: For long documents, extract verbatim quotes before analysis
- **Multiple Verification Passes**: Run same prompt multiple times to check consistency
- **Ground in Actual Files**: Always read existing code before modifying

### Code Quality and Safety Patterns

#### Test-Driven Development (TDD)
- **Write Tests First**: Create tests based on requirements before implementation
- **Verify Test Failures**: Run tests to confirm they fail before implementing
- **Small Iterations**: Keep changes under 200 lines per iteration
- **Continuous Validation**: Run tests after each change

#### Security Best Practices
- **Never Include Secrets**: Keep API keys, passwords, credentials out of code
- **Validate All Inputs**: Sanitize and validate user inputs
- **Least Privilege**: Use minimal permissions required
- **Audit Trail**: Log significant operations for security monitoring

#### Error Handling
- **Comprehensive Try-Catch**: Handle all potential failure points
- **Specific Error Messages**: Provide actionable error information
- **Graceful Degradation**: Fail safely without crashing
- **Recovery Strategies**: Implement retry logic with exponential backoff

### Workflow Optimization

#### Context Management
- **Keep Context Focused**: Work with 100-200 lines maximum per operation
- **Clear Regularly**: Use /clear to reset context when switching tasks
- **Localize Rules**: Use per-folder CLAUDE.md for specific subsystem rules
- **Prune File Sets**: Only keep relevant files in context

#### Planning and Execution
- **3-Step Plans**: Propose concise plans with small, testable changes
- **Get Approval First**: Present plan before implementation
- **Use Checkpoints**: Save state at key milestones
- **Provide Feedback Loops**: Request test results and adjust accordingly

### Code Generation Best Practices

#### Code Structure
- **Extend, Don't Duplicate**: Modify existing code rather than creating new files
- **Consistent Patterns**: Follow established patterns in the codebase
- **Clear Naming**: Use descriptive, self-documenting names
- **Modular Design**: Create reusable, single-purpose functions

#### Documentation
- **Inline Comments**: Explain complex logic and non-obvious decisions
- **Docstrings**: Use appropriate style for all functions and classes
- **Update Immediately**: Modify documentation alongside code changes
- **Examples**: Include usage examples in docstrings

### Performance and Optimization

#### Efficient Processing
- **Batch Operations**: Group related operations when possible
- **Lazy Loading**: Load resources only when needed
- **Cache Results**: Store expensive computations
- **Profile First**: Measure before optimizing

#### Resource Management
- **Context Managers**: Use appropriate resource cleanup patterns
- **Memory Awareness**: Clean up large objects when done
- **Connection Pooling**: Reuse connections when possible
- **Async Operations**: Use async/await for I/O operations

### Collaboration and Maintenance

#### Code Review Readiness
- **Small, Focused Changes**: Keep PRs under 200 lines when possible
- **Clear Commit Messages**: Explain the "why" not just the "what"
- **Test Coverage**: Include tests with new features
- **Breaking Changes**: Document and communicate API changes

#### Long-term Maintainability
- **Avoid Clever Code**: Prioritize readability over brevity
- **Document Decisions**: Explain architectural choices
- **Deprecation Paths**: Provide migration guides for changes
- **Version Compatibility**: Maintain backward compatibility when feasible

### Critical Reminders

1. **ALWAYS create a todo list before starting any multi-step task**
2. **ALWAYS use ultrathinking for complex problems**
3. **ALWAYS verify uncertain information through online search**
4. **NEVER skip sequential processing to avoid tool conflicts**
5. **NEVER guess when you can verify**
6. **NEVER include secrets or credentials in code**
7. **ALWAYS run tests to validate changes**
8. **ALWAYS update documentation immediately after code changes**

### When in Doubt

- **Ask for Clarification**: Request more details rather than assuming
- **Search and Verify**: Use WebSearch to check current best practices
- **Test Incrementally**: Validate each step before proceeding
- **Document Uncertainty**: Note areas that need review
- **Seek Human Review**: Flag critical decisions for human validation## Common Documentation Automation Patterns

1. **Changelog-Driven Updates**: Automatically update docs based on changelog entries
2. **Screenshot Updates**: Generate prompts to update screenshots when UI changes
3. **Cross-Reference Validation**: Verify all internal links remain valid
4. **Style Compliance**: Check and fix articles not following guidelines
5. **Missing Content Detection**: Identify and create stub articles for new features

## 📊 D2 Diagram Guidelines for Tallyfy Documentation

### 🚨 MANDATORY NOTATION RULES

**CRITICAL**: D2 provides cleaner, more maintainable diagram notation. These rules are MANDATORY for consistent rendering.

#### ❌ FORBIDDEN NOTATION (Never Use These)

1. **NO backticks in labels**: 
   - ❌ WRONG: `Node["`**Text**`"]` or `Node[`Text`]`
   - ✅ RIGHT: `Node["Text"]` or `Node[Text]`

2. **NO HTML tags**:
   - ❌ WRONG: `Node["Text<br/>More text"]`
   - ✅ RIGHT: `Node["Text"]` (keep it short)

3. **NO markdown formatting**:
   - ❌ WRONG: `Node["**Bold Text**"]`
   - ✅ RIGHT: `Node["Bold Text"]`

4. **NO inline styles or colors**:
   - ❌ WRONG: `style Node fill:#E8F4FF`
   - ✅ RIGHT: Let global config handle colors

5. **NO excessive text** (max 4-5 words):
   - ❌ WRONG: `Node["This is a very long description that wraps"]`
   - ✅ RIGHT: `Node["Long Description"]`

6. **NO special characters**:
   - ❌ WRONG: `Node["Data & Analytics"]`
   - ✅ RIGHT: `Node["Data and Analytics"]`

7. **NO parentheses for node definitions**:
   - ❌ WRONG: `Node("Text")` or `Node([Text])`
   - ✅ RIGHT: `Node["Text"]` or `Node[Text]`

8. **NO positioning attributes inside node blocks**:
   - ❌ WRONG: `Label: "Title" { near: top-center }`
   - ✅ RIGHT: Just use comments like `# Title` or simple labels

9. **PREVENT TEXT BLEEDING** (words splitting across lines):
   - ❌ WRONG: `Node["AI Transcription"]` (may split as "AI Transcripti" + "on")
   - ✅ RIGHT: `Node["AI Transcript"]` or `Node["Transcribe AI"]`
   - Keep labels under 15 characters when possible
   - Avoid words longer than 10 characters
   - Test rendering to ensure no word breaks

#### ✅ CORRECT NOTATION PATTERNS

```d2
Start: Simple Label
Next: Another Label
Decision: Question? {
  shape: diamond
}
Action: Do Something
End: Complete

Start -> Next
Next -> Decision
Decision -> Action: Yes
Decision -> End: No
```

**Key Rules**:
- Use clear node names and labels: `NodeName: Label Text`
- Keep labels under 30 characters (ideally under 20)
- Use 3-4 words maximum per label
- Put detailed explanations in the article text, not the diagram
- Use consistent node naming: `Start`, `Process1`, `Decision1`, etc.

#### 🔍 PREVENTING TEXT BLEEDING

**Problem**: Text like "AI Transcription" displays as "AI Transcripti" with "on" on the next line.

**Solutions**:
1. **Shorten labels**: "AI Transcription" → "AI Transcript" or "Transcribe"
2. **Avoid long words**: Break "Implementation" into "Implement"
3. **Character limits**: Keep total label length under 15 characters
4. **Test common problems**:
   - "Transcription" (13 chars) → Use "Transcript" (10 chars)
   - "Configuration" (13 chars) → Use "Config" (6 chars)
   - "Authorization" (13 chars) → Use "Auth" (4 chars)
   - "Synchronization" (15 chars) → Use "Sync" (4 chars)

### 🔧 D2 Syntax Troubleshooting

**CRITICAL SYNTAX ERRORS TO AVOID** (from Cloudflare Pages build failures):

1. **Dollar signs trigger variable substitution**:
   - ❌ WRONG: `Check: "Amount > $5000?"` 
   - ✅ RIGHT: `Check: "Amount > 5000?"`
   - D2 interprets `$` as start of variable substitution


4. **Invalid node syntax with square brackets**:
   - ❌ WRONG: `TallyfyInputs[Tallyfy Process]: { ... }`
   - ✅ RIGHT: `TallyfyInputs: "Tallyfy Process" { ... }`
   - Square brackets in node names aren't valid D2 syntax

5. **No mixed node definitions and edges on same line**:
   - ❌ WRONG: `Request: "Task Request" -> Planner: "Sets goals"`
   - ✅ RIGHT: Separate into two lines:
     ```
     Request: "Task Request"
     Request -> Planner: "Sets goals"
     ```
   - Node definitions and edge definitions must be on separate lines

6. **Self-loops on containers not supported**:
   - ❌ WRONG: Container with note/children having `Container -> Container`
   - ✅ RIGHT: Move self-loop action into the note text
   - D2's dagre layout engine doesn't support self-loops on containers

7. **Position constants are limited**:
   - ❌ WRONG: `{near: middle-center}` (doesn't exist)
   - ✅ RIGHT: Valid positions: top-left, top-center, top-right, center-left, center-right, bottom-left, bottom-center, bottom-right

8. **Local validation before pushing**:
   ```bash
   # Validate all D2 diagrams locally
   ./scripts/validate-d2.sh
   ```

### Critical Implementation Notes

**RENDERING CONFIGURATION**: All D2 diagrams are rendered with global theme and configuration settings defined in `/support-docs`. Individual diagrams should focus on content structure, not styling. The global config handles:
- Brand colors (light green #f2faf4, #e1f7e6 with dark green borders #225930)
- Dark mode colors (#0D0D0D background, rgba(11, 40, 19, 0.4) nodes)
- Font settings (Inter Variable)
- Node spacing and padding
- Automatic text wrapping

### 🎨 D2 Diagram Color Palette

**MANDATORY**: Use ONLY these colors in D2 diagrams. Random colors are forbidden. Style attributes should be minimal and only when absolutely necessary for clarity.

#### Light Theme Colors (Manual and Website)
- **Primary Fill**: `#f2faf4` (rgb(242 250 244) - use without opacity in D2)
- **Secondary Fill**: `#e1f7e6` (rgb(225 247 230) - use without opacity in D2)
- **Border Color**: `#225930` (rgb(34 89 48) - dark green for borders and strokes)
- **Warning/Reminder**: `#fff3cd` (light yellow for special states)
- **Text**: Black (default) - Never override
- **Background**: White (default)

#### Dark Theme Colors  
- **Primary Fill**: `#0D0D0D` - Near black
- **Secondary Fill**: `#0b2813` (rgb(11 40 19) - dark green tint)
- **Border Color**: `#e1f7e6` (rgb(225 247 230) - light green border)
- **Text**: White (automatic) - Never override
- **Background**: `#0D0D0D`

#### D2 Usage in Code
```d2
# Use these exact colors in your D2 diagrams:
Node1: Primary Node {
  style.fill: "#f2faf4"
}
Node2: Secondary Node {
  style.fill: "#e1f7e6"
}
Decision: Decision Point {
  shape: diamond
  style.fill: "#f2faf4"
}
Warning: Overdue Task {
  style.fill: "#fff3cd"
}
Connection: {
  style.stroke: "#225930"
  style.stroke-dash: 3
}
```

#### Usage Rules
1. **NO random colors**: Never use red, blue, yellow, orange, etc. unless semantically meaningful
2. **NO inline styles**: Let global config handle 99% of styling
3. **Semantic colors ONLY when necessary**:
   - Success/Approval: Use default green theme
   - Error/Rejection: May use subtle red ONLY for clear error states
   - Warning: Avoid - use text labels instead
4. **Consistency**: All diagrams must look cohesive across the documentation
5. **Simplicity**: When in doubt, use NO color styling - let defaults handle it

**ENFORCEMENT**: These notation rules are MANDATORY. Every D2 diagram must follow them to ensure consistent rendering. When creating or editing diagrams, mentally check each rule before committing changes.

### When to Use Visual Diagrams - ULTRATHINKING Required

**CRITICAL RULE**: Only add D2 diagrams where they provide clear value for understanding complex flows or interactions. Based on extensive analysis, only **10-15% of documentation articles** should have diagrams. Most documentation is better with clear text.

**ULTRATHINKING APPROACH**: Before adding any diagram, you must:
1. Read the ENTIRE article to understand full context
2. Think from three perspectives: beginner, intermediate, expert
3. Ask: "Is the cognitive effort to understand a diagram LESS than understanding the text alone?"
4. Apply the "lagom" principle - not too much, not too little
5. Consider if visual learners specifically benefit
6. Evaluate long-term maintenance burden

#### ✅ Good Candidates for Diagrams (High Value Patterns)
1. **OAuth/API Authorization Flows** → Use `sequenceDiagram`
   - Multi-actor sequences with token exchanges
2. **Automation Logic with AND/OR Conditions** → Use `flowchart`
   - Complex conditional evaluation paths
3. **Webhook Event Processing** → Use `sequenceDiagram`
   - Async flows with queues, retries, callbacks
4. **Process Launch Triggers** → Use `flowchart`
   - Multiple trigger paths converging to single action
5. **Master Template vs Process Relationships** → Use `graph` or `erDiagram`
   - One-to-many spawning patterns
6. **Integration Flows** → Use `sequenceDiagram` or `flowchart`
   - Data moving between Tallyfy and external systems
7. **State Machines** → Use `stateDiagram-v2`
   - Process/task lifecycle transitions

#### ❌ Poor Candidates for Diagrams (Skip These)
- Simple linear processes (≤3 steps) - Use `<Steps>` component instead
- Single API calls without complex flow - Code blocks are clearer
- Basic CRUD operations
- UI navigation - Screenshots are better
- Content easily explained with bullet points
- Troubleshooting checklists - Bullet points work best
- Feature lists or changelogs - Text lists are appropriate
- Simple two-state toggles - Text description is sufficient

### Documentation Areas and Diagram Types

1. **API Documentation** (`/pro/integrations/open-api/`)
   - OAuth flows → sequence diagram (user-facing terms)
   - Request/response cycles → sequence diagram (API terminology)
   - Error handling flows → flowchart with decision diamonds

2. **Webhook Documentation** (`/pro/integrations/webhooks/`)
   - Event triggers → flowchart showing cause and effect
   - Webhook delivery → sequence diagram with retry logic
   - Event processing → flowchart with error branches

3. **Process Documentation** (`/pro/launching/`, `/pro/tracking-and-tasks/`)
   - Process triggers → flowchart with decision nodes
   - Process lifecycle → state diagram
   - Task dependencies → graph showing relationships

4. **Automation Logic** (`/pro/documenting/templates/automations/`)
   - Sequential rule evaluation → flowchart showing position-based order
   - AND/OR combinations → linear flow (NOT nested parentheses)
   - Action execution → sequential flowchart

5. **Integration Patterns** (`/pro/integrations/`)
   - Third-party flows → sequence diagram
   - SSO setup → sequence showing both user and admin actions
   - Data sync → bidirectional arrows in sequence

6. **Manufactory Documentation** (`/manufactory/`)
   - Event pipeline → graph diagram
   - WebSocket connections → state diagram
   - Collector architecture → graph with subgraphs

### Terminology Guidelines for Diagrams

**IMPORTANT**: Choose terminology based on your audience:

**API/Technical Documentation** - Use precise technical terms:
- `POST /api/v1/endpoints`
- `Bearer token`
- `HTTP 201 Created`
- `webhook_url`
- `automation_id`
- `rule.position`
- Database field names

**User-Facing Documentation** - Use friendly business terms:
- "Launch a process"
- "Complete a task"
- "Assign to team member"
- "Automation triggers"
- "When this happens"
- "Workflow rules"
- UI labels and button names

### D2 Syntax Requirements (MANDATORY)

**CRITICAL SYNTAX RULES** to prevent parse errors:

#### ✅ CORRECT Node Definition
```d2
NodeA: Simple Label
NodeB: Label with spaces
NodeC: |md
  Multi
  Line Label
|
```

#### ❌ SYNTAX ERRORS TO AVOID
```d2
# NEVER DO THESE:
Node A: Label     # Space in node name - use Node_A or NodeA
Node: "Label      # Missing closing quote
Node -> Target    # Using undefined Target node
Problem: "Text" {
  shape: rectangle
  near: center-right  # ❌ FATAL: near: inside blocks = build failure
}
```

#### Essential Syntax Rules:
1. **Node names**: No spaces, use letters/numbers/underscores (e.g., `Node1`, `Process_A`)
2. **Every node referenced in edges MUST be defined**
3. **Quote matching**: Each `"` needs closing `"`
4. **NEVER use `near:` inside blocks with other properties** - causes "unexpected text after map" build failures
   - ✅ VALID: `SomeText: {near: center-right}` (standalone)
   - ❌ INVALID: Mixing `near:` with `shape:`, `style:` etc. in same block
5. **NEVER use curly braces `{}` in edge labels** - D2 interprets them as variable substitutions
   - ❌ INVALID: `A -> B: "JSON {'key': 'value'}"`
   - ✅ VALID: `A -> B: "JSON [key: value]"` or `A -> B: "JSON (key=value)"`
6. **NEVER use double-double quotes `""`** - causes "unexpected text after double quoted string" error
   - ❌ INVALID: `Start: ""Agent Starts""`
   - ✅ VALID: `Start: "Agent Starts"`
7. **One node definition per line**
8. **Use `|md` blocks for multi-line text with markdown formatting

**Key Points**:
- Simple labels don't need quotes: `Node: Label Text`
- Use `style.bold: true` for emphasis
- Multi-line text uses `|md` blocks
- Edge labels are simple: `A -> B: label`

### Content-Specific Diagram Templates

#### For OAuth Documentation
```d2
App: Your App
Auth: Tallyfy Auth
API: Tallyfy API

OAuth Flow: {
  label: OAuth 2.0 Authorization Code Flow
  
  App -> Auth: GET /oauth/authorize\nclient_id, redirect_uri, scope
  Auth -> App: Show login page
  App -> Auth: User credentials
  Auth -> App: Redirect with code
  App -> Auth: POST /oauth/token\ncode, client_secret
  Auth -> App: Access token + Refresh token
}

API Usage: {
  label: API Usage Loop
  App -> API: API request + Bearer token
  API -> App: Response data
}

Token Refresh: {
  label: Token expired
  App -> Auth: POST /oauth/refresh\nrefresh_token
  Auth -> App: New access token
}
```

#### For Process Triggers
```d2
Start: Process Trigger { shape: oval }
Check: Which Trigger? { shape: diamond }

Manual: User clicks Run
API: POST /api/v1/processes/run
Schedule: Cron expression matches
Email: Email to process@
Form: Public form submitted
Webhook: External webhook received

Validate: Has Permission? { shape: diamond }
Launch: Launch Process

Start -> Check
Check -> Manual: Manual
Check -> API: API
Check -> Schedule: Schedule
Check -> Email: Email
Check -> Form: Form
Check -> Webhook: Webhook

Manual -> Validate
API -> Validate
Schedule -> Launch
Email -> Launch
Form -> Launch
Webhook -> Validate

Validate -> Launch: Yes
Validate -> Deny: No
```

#### For Webhook Events
```d2
Step: Step
Tallyfy: Tallyfy
Queue: Queue
Webhook: Webhook Service
External: External System

Step -> Tallyfy: Complete step
Tallyfy -> Tallyfy: Check webhook config

Webhook Type: {
  Template Level: {
    Tallyfy -> Queue: Queue template webhook
  }
  Step Level: {
    Tallyfy -> Queue: Queue step webhook
  }
}

Queue -> Webhook: Process webhook

Retry Loop: {
  label: Max 3 attempts
  Webhook -> External: POST {webhook_url}\nTimeout: 30 seconds
  
  Success: {
    External -> Webhook: Success response (2xx)
    Webhook -> Tallyfy: Mark delivered
    note: Log success
  }
  
  Failure: {
    External -> Webhook: Error or timeout
    Webhook -> Webhook: Wait (backoff)\n1st: 1min\n2nd: 5min\n3rd: 15min
  }
}

Final Failure: {
  Webhook -> Tallyfy: Mark failed
  note: Send failure notification
}
```

#### For Automation Logic (Reflecting Actual System)
```d2
Start: Event Triggers Automation { shape: oval }
Context: Determine Context
Rules: Load Rules by Position Order
Rule1: Rule 1 Met? { shape: diamond }
Op1: Logic Operator? { shape: diamond }
Rule2: Rule 2 Met? { shape: diamond }
Actions: Execute Actions

Start -> Context
Context -> Rules
Rules -> Rule1

Rule1 -> Op1: Yes
Rule1 -> NoAction: No

Op1 -> Rule2: AND/OR
Op1 -> Actions: None

Rule2 -> Actions: Yes
Rule2 -> NoAction: No

Actions -> End
NoAction -> End

note: Rules evaluated sequentially by position field
```

### Webhook and API Visualization Best Practices

#### API Call Representation

**Use API Terminology for Technical Documentation:**
```d2
Client: Client
API: Tallyfy API
DB: Database

Client -> API: POST /api/v1/processes\nBearer: {token}
API -> API: Validate token
API -> DB: Query permissions
DB -> API: User authorized
API -> DB: Create process
DB -> API: Process ID: abc123
API -> Client: 201 Created\n{id: "abc123"}
```

**Use User-Facing Terms for End-User Documentation:**
```d2
User: User
Tallyfy: Tallyfy
Email: Email Service

User -> Tallyfy: Launches process
Tallyfy -> Tallyfy: Creates tasks
Tallyfy -> Email: Send notifications
Email -> User: Task assigned email
```

#### Webhook Flow Patterns

**Standard Webhook with Retry Logic:**
```d2
Tallyfy: Tallyfy
Queue: Queue
Webhook: Webhook Service
External: External System

label: Event-Driven Architecture

Tallyfy -> Queue: Queue webhook event
Queue -> Webhook: Process event

Retry Loop: {
  label: Retry up to 3 times
  Webhook -> External: POST webhook_url
  
  Success: {
    External -> Webhook: Success (2xx)
    Webhook -> Tallyfy: Mark delivered
  }
  
  Failure: {
    External -> Webhook: Error/Timeout
    Webhook -> Webhook: Exponential backoff\n1min, 5min, 15min
  }
}
```

#### SSO and Authentication Flows

**Collaborative Setup (User + Admin Actions):**
```d2
Admin: Admin
Tallyfy: Tallyfy
IdP: Identity Provider
User: User

SSO Setup Process: {
  Admin -> Tallyfy: Configure SSO settings
  Tallyfy -> IdP: Register service provider
  IdP -> Tallyfy: Metadata exchange
  Tallyfy -> Admin: Configuration complete
}

User Login Flow: {
  User -> Tallyfy: Access Tallyfy
  Tallyfy -> IdP: Redirect to IdP
  User -> IdP: Enter credentials
  IdP -> IdP: Authenticate user
  IdP -> Tallyfy: SAML assertion
  Tallyfy -> Tallyfy: Create session
  Tallyfy -> User: Access granted
}
```

### Auto-Generation Rules

#### When You See These Patterns → Generate Diagrams

1. **Multiple Steps with Arrows** (→, then, after, next)
   - Generate: flowchart
   - Direction: TD or LR based on step count

2. **API Calls with Responses** (POST, GET, returns, responds)
   - Generate: sequenceDiagram
   - Include: Request/response pairs
   - Use API terminology for technical docs
   - Use user-facing terms for end-user docs

3. **Conditional Logic** (if, when, unless, either/or)
   - Generate: flowchart with diamond decision nodes
   - Include: All branches and outcomes

4. **State Transitions** (pending → active → complete)
   - Generate: stateDiagram-v2
   - Include: All states and transitions

5. **System Components** (connects to, sends to, receives from)
   - Generate: graph diagram
   - Include: All components and data flows

6. **Webhook Events** (triggers, fires, notifies)
   - Generate: sequence diagram with retry logic
   - Show queue processing
   - Include error handling

7. **Authentication Flows** (login, SSO, OAuth)
   - Generate: sequence diagram
   - Show both user and system actions
   - Include token/session management

### Diagram Placement & Article Structure

#### Recommended Article Structure with Diagrams
When including a D2 diagram, follow this proven structure:
1. **H2 heading** for the concept
2. **One-sentence "What this shows" line** - Brief context
3. **D2 code fence** - The diagram itself
4. **3 bullets titled "What to notice"** - Call out key insights
5. **Optional links** to deeper concepts embedded in the diagram

#### Placement Golden Rules
1. **For feature overviews**: Place diagram IMMEDIATELY after overview paragraph
2. **For troubleshooting**: Put at TOP before wall-of-text steps
3. **For concepts**: After the intro, before deep details  
4. **For quick starts**: At the very beginning for 5-second path understanding
5. **For complex flows**: Chapter with anchors and link between sections

#### Visual Best Practices
- **One idea per diagram** - Split if >30 nodes
- **Labels**: ≤5 words per node; edges are verbs ("sends", "approves")
- **Flow direction**: 
  - LR (left-right) for features and processes
  - TD (top-down) for troubleshooting and decision trees
- **Decisions**: Always use diamonds with at least two labeled exits
- **Swimlanes**: Use `subgraph` with recognizable titles ("Your Workspace", "Tallyfy Cloud")
- **Consistency**: Reuse node names across pages ("Task", "Approval")

#### Quality Checklist
- **Clarity**: Is the diagram easier to understand than text?
- **Completeness**: Are all paths and error states shown?
- **Accuracy**: Does it reflect the actual system behavior?
- **Simplicity**: One concept per diagram, <30 nodes ideal, 50 max
- **Mobile-friendly**: Readable on small screens
- **Value-add**: Would removing the diagram hurt understanding?
- **Maintenance**: Will this need frequent updates?

### Hyperlinks in D2 Diagrams

#### Making Diagrams Interactive Navigation Hubs
Transform diagrams into clickable navigation tools using D2's link syntax:

```d2
A: Create Template {
  link: /products/pro/documenting/templates/
  tooltip: Templates overview
}
B: Add Approval {
  link: /products/pro/documenting/templates/automations/
  tooltip: Automation rules
}

A -> B
```

#### Hyperlink Support in D2
- ✅ **Full support**: All node types support hyperlinks
- ✅ **Tooltips**: Rich tooltips on hover
- ✅ **External links**: Full URL support
- **Note**: D2 provides consistent link support across all diagram types

#### Link Patterns
1. **Internal docs**: `link: /products/pro/path/`
2. **Same-page anchors**: `link: #section-id`
3. **External sites**: `link: https://api.tallyfy.com`
4. **With tooltip**: `tooltip: Descriptive text`

**Best Practice**: Add at least 2 links per diagram to make it a navigation hub.

### Practical D2 Implementation

#### Creating Effective Prompts for AI
When asking AI to generate D2 diagrams, be specific:
- "Create a sequence diagram showing OAuth flow with token refresh"
- "Generate a flowchart for automation rule evaluation with AND/OR logic"
- "Visualize webhook retry mechanism with exponential backoff"

Include these details:
- Tallyfy entities (Template, Process, Task, Step)
- Error conditions and fallback paths
- Timing information (timeouts, retry delays)
- User roles and permissions
- Hyperlinks to related documentation

#### Animated Arrows in D2 Diagrams

**Two Types of Animations Available:**

1. **Multi-Board Animations** (Transitions between diagram states)
   - Configured via `animateInterval` in astro.config.mjs
   - Currently set to 1000ms in /support-docs
   - Used for showing progressive changes or steps
   - Requires multiple boards/states in the diagram

2. **Animated Connections** ("Marching Ants" effect)
   - Creates moving dashed lines on arrows to show flow direction
   - Requires `style.animated: true` on individual connections
   - Works with both normal and sketch modes
   - Best for showing data flow, critical paths, or active connections

**How to Add Animated Arrows:**
```d2
# Static arrow (default)
Client -> API: Request

# Animated arrow (marching ants effect)
Client -> API: Request {
  style.animated: true
}

# Multiple animated connections
database -> api: data flow {
  style.animated: true
}
api -> frontend: JSON response {
  style.animated: true
}
```

**When to Use Animated Arrows:**
- **Sparingly** - Too many animations can be distracting
- **Critical Flows** - Highlight the most important data paths
- **API Documentation** - Show request/response flow direction
- **Process Workflows** - Indicate the active path through a process
- **Event Propagation** - Visualize how events flow through the system

**Current Status:** Animated arrows are properly configured but not currently used in diagrams. Consider selectively adding them to enhance understanding of flow direction.

#### Golden Nuggets for Specific Diagram Types

**Sequence Diagrams**:
- Always add `autonumber` so support can reference "step 3" in tickets
- Use `Note` for explaining the "why" behind critical steps
- Show retry logic with loops and exponential backoff times

**Flowcharts**:
- Put verbs on edges ("sends", "approves", "triggers")
- Use `classDef` to highlight exceptions:
  ```
  classDef danger fill:#fee2e2,stroke:#ef4444
  class ErrorNode danger
  ```
- Create "hub" nodes for grouping related navigation links

**State Diagrams**:
- Add SLAs or timing on transitions: `Under_Review --> Approved: SLA 4h`
- Show triggers on state changes: `Draft --> Submitted: user clicks Submit`

**All Diagrams**:
- Title subgraphs with familiar boundaries ("Your Workspace", "Tallyfy Cloud")
- Keep to "lagom" - not too much, not too little
- Consider adding a "What to notice" bullet list after the diagram

#### Common Tallyfy Entities
**Core**: Template, Process, Step, Task, Form
**Users**: Admin, Member (Standard/Light), Guest, Owner
**Integration**: Webhook, API, WebSocket, Email trigger

#### Technical Constraints
- Maximum 30 nodes ideal, 50 absolute max (performance)
- Avoid nesting beyond 3 levels
- Split complex flows into multiple focused diagrams
- Ensure text remains readable on mobile devices
- One idea per diagram - chapter large flows with anchors

### Global Configuration & CSS (DO NOT OVERRIDE)

**IMPORTANT**: All D2 styling is handled globally through:
1. **Theme Configuration**: `/support-docs/src/styles/d2-theme.css` 
2. **Astro Config**: `/support-docs/astro.config.mjs`

These global settings ensure:
- Proper text spacing (letter-spacing: 0.02em, word-spacing: 0.1em)
- Minimum node sizes (100px width, 45px height)
- Dark mode compatibility (automatic text color switching)
- Mobile responsiveness (viewport-based adjustments)
- Font consistency (Inter Variable font family)

**DO NOT** add inline styles or color definitions in individual diagrams. The global configuration handles all visual aspects automatically.

### Mobile-Friendly D2 Design Guidelines

#### Layout Orientation for Device Compatibility

**CRITICAL**: Always prioritize vertical layouts for mobile readability:

1. **Default to Top-Down (TD) Layout**:
   - Use `flowchart TD` instead of `flowchart LR` for most diagrams
   - Vertical scrolling is natural on mobile devices
   - Horizontal diagrams become unreadable on small screens

2. **When to Use Each Layout**:
   - `TD` (Top-Down): Process flows, decision trees, hierarchies (PREFERRED)
   - `LR` (Left-Right): Only for simple 2-3 step flows or timelines (avoid for mobile compatibility)
   - `BT` (Bottom-Top): Rarely - only for reverse hierarchies
   - `RL` (Right-Left): Avoid - counterintuitive reading direction

3. **Node Text Guidelines**:
   - Maximum 3-4 words per line in nodes
   - Use multi-line labels: `Step 1\nInitialize`
   - Avoid concatenated words - ensure spaces between words
   - Test readability at 320px viewport width

#### Dark Mode Compatibility

**CRITICAL**: Never hardcode colors that break in dark mode:

1. **Avoid These Style Declarations**:
   ```d2
   ❌ Node.style.fill: "#E8F4FF"  # Don't hardcode colors
   ❌ Error.style.stroke: "#DC3545"  # Use themes instead
   ```

2. **Use Theme-Based Styling Instead**:
   ```d2
   ✅ Success.class: success  # Use predefined classes
   ✅ Error.class: error      # Theme handles colors
   ✅ Info.class: info        # Consistent across modes
   ```
   D2 themes automatically handle text visibility in dark mode

3. **Essential Dark Mode Rules**:
   - Always specify text color explicitly with `color:#000` or `color:#fff`
   - Use high-contrast color combinations
   - Test diagrams in both light and dark modes
   - Avoid relying on theme defaults for critical elements

#### Responsive Design Patterns

1. **Break Complex Diagrams**:
   Instead of one 50-node diagram, create:
   - Overview diagram (10 nodes) with navigation links
   - 3-4 detailed diagrams (10-15 nodes each) for subsections

2. **Progressive Disclosure**:
   ```d2
   Overview: Process Overview\nClick for details {
     link: #detailed-steps
     tooltip: View detailed steps
   }
   ```

3. **Mobile-First Node Sizing**:
   - Keep node labels under 20 characters
   - Use abbreviations with legend below diagram
   - Add full descriptions in surrounding text

#### Text Spacing and Readability

**CRITICAL**: Ensure proper text spacing in nodes:

1. **Common Issues and Fixes**:
   - Missing spaces: Check for `Task completionother` → Fix: `Task completion<br/>other`
   - Long labels: `UserclicksLaunchbutton` → Fix: `User clicks<br/>Launch button`
   - API endpoints: Keep on single line or use clear breaks

2. **Label Formatting Rules**:
   - Use `<br/>` for intentional line breaks
   - Ensure spaces between all words
   - Capitalize consistently (Title Case or sentence case)
   - Avoid special characters that might not render

3. **Testing Checklist**:
   - View at 320px, 768px, and 1024px widths
   - Toggle between light and dark modes
   - Verify all text is readable without zooming
   - Check for text overflow or truncation

### D2 Diagram Maintenance Rules

**CRITICAL**: When updating ANY article that contains D2 diagrams, you MUST:

1. **Review Existing Diagrams**: Check if the content changes affect the diagram's accuracy
2. **Update Diagram Content**: If the article changes modify any process, flow, or relationship shown in the diagram, update the D2 notation accordingly
3. **Maintain Consistency**: Ensure terminology in the diagram matches the updated article text
4. **Verify Links**: If the diagram contains `click` statements, verify all linked paths remain valid
5. **Apply ULTRATHINKING**: Re-evaluate if the diagram still adds value after the content update
   - If the process simplified to ≤3 steps, consider removing the diagram
   - If complexity increased, consider if a diagram is now needed
6. **Follow All Guidelines**: Apply the complete D2 guidelines when making updates:
   - Keep to <30 nodes ideal
   - Maintain appropriate diagram type for content
   - Update labels to ≤5 words
   - Ensure mobile readability
   - Add/update "What to notice" bullets if needed

**Examples of Required Updates**:
- Article changes API endpoint → Update sequence diagram to show new endpoint
- Process step removed → Remove corresponding node from flowchart
- New conditional logic added → Add decision diamond to flowchart
- State transition timing changed → Update SLA notation in state diagram
- Feature renamed → Update all node labels using that feature name
- Integration deprecated → Remove or mark as deprecated in diagram

**Remember**: An outdated diagram is worse than no diagram. Always keep diagrams in sync with article content.

### D2 Configuration in Astro Starlight

#### Supported Diagram Types with D2
All 17 diagram types are technically supported, but use these based on content needs:

**PRIMARY (Use frequently)**:
- `flowchart` - Processes, workflows, decision trees (30+ shape types)
- `sequenceDiagram` - API calls, webhooks, multi-system interactions
- `stateDiagram-v2` - Object lifecycles, status transitions

**SECONDARY (Use when appropriate)**:
- `erDiagram` - Database schemas, entity relationships
- `journey` - User experience flows
- `gantt` - Project timelines (use Timeline for long periods)
- `gitGraph` - Version control, branching strategies
- `mindmap` - Hierarchical concept breakdown
- `timeline` - Historical events, feature evolution

**RARELY (Only if perfect fit)**:
- `classDiagram` - Object-oriented structures
- `pie` - Simple percentages (include sample size in text)
- `quadrantChart` - 2x2 analysis matrices
- `requirementDiagram` - Formal specifications
- `C4Context/C4Container` - System architecture
- `sankey` - Flow volumes
- `block` - Beta feature

#### Platform Configuration
- **Version**: D2 (latest)
- **Theme**: Customizable themes (works with light/dark modes)
- **Rendering**: Server-side or client-side rendering options
- **Font**: Inter Variable (matches documentation font)
- **Colors**: 
  - Primary: `#0066CC` (Tallyfy Blue)
  - Success: `#00AA55` / `fill:#D4EDDA`
  - Error: `#DC3545` / `fill:#F8D7DA`
  - Info: `fill:#E8F4FF`
  - Warning: `fill:#FFF3CD`

### ⚠️ CRITICAL D2 DIAGRAM ISSUES TO AVOID

#### 1. Text Visibility Problem (MUST FIX)
**PROBLEM**: Text appears white/invisible on light backgrounds in light mode.
**SOLUTION**: Text color is now forced to black in light mode via global CSS. Never override this.

#### 2. Broken Hyperlinks (ALWAYS VERIFY)
**PROBLEM**: Many click directives point to non-existent URLs (404 errors).
**SOLUTION**: ALWAYS verify URLs exist before adding click directives:
```bash
# Check if a URL exists
ls /Users/amit/Documents/GitHub/documentation/src/content/docs/pro/[path]/index.mdx
```

Common correct URLs:
- Templates: `/products/pro/documenting/templates/`
- Processes: `/products/pro/tracking-and-tasks/processes/`
- Tasks: `/products/pro/tracking-and-tasks/tasks/`
- API: `/products/pro/integrations/open-api/`

### D2 Diagram Troubleshooting Guide

#### Common Build Errors and Solutions

1. **"unexpected text after map"**:
   - **Cause**: Comments placed inline with nodes/edges
   - **Fix**: Move all comments to separate lines using `#` syntax
   
2. **"undefined node referenced"**:
   - **Cause**: Using a node in an edge that wasn't defined
   - **Fix**: Define all nodes before using them in edges
   
3. **Text bleeding/splitting across lines**:
   - **Cause**: Labels too long for node width
   - **Fix**: Shorten to <15 characters or use abbreviations
   
4. **404 errors on diagram links**:
   - **Cause**: Incorrect URL paths in link properties
   - **Fix**: Verify paths exist, include trailing slashes

5. **Diagram not rendering**:
   - **Cause**: Invalid D2 syntax or unsupported keywords
   - **Fix**: Ensure using only D2-supported syntax, no legacy diagramming keywords


#### Debug Commands
```bash
# VALIDATE ALL D2 DIAGRAMS LOCALLY (RECOMMENDED BEFORE PUSHING)
./scripts/validate-d2.sh

# Find all D2 diagrams in documentation
grep -r "^\`\`\`d2" src/content/docs --include="*.mdx" | wc -l

# Check for invalid keywords that shouldn't be in D2 (legacy syntax check)
grep -r "sequenceDiagram\|participant\|autonumber" src/content/docs --include="*.mdx"

# Find incorrect edge label syntax
grep -r "->.*:.*\"" src/content/docs --include="*.mdx" | grep -v "-> [A-Za-z]*:"

# Verify linked URLs in D2 diagrams
for file in $(grep -r "link:" src/content/docs --include="*.mdx" -l); do
  echo "Checking $file"
  grep "link:" "$file" | sed 's/.*link: "\(.*\)".*/\1/' | while read url; do
    if [[ ! -f "src/content/docs${url}index.mdx" ]] && [[ ! -f "src/content/docs${url%.mdx}.mdx" ]]; then
      echo "  ❌ Missing: $url"
    fi
  done
done
```


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