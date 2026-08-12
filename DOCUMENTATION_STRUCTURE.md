<!-- Last updated: 2026-08-12 17:56:43 -->
# Documentation Structure Guide

This file provides a comprehensive overview of the documentation organization to help with navigation, updates, and content creation.

## 📁 High-Level Structure

```
/src/content/docs/
├── 404.mdx          (1 file)    - the not-found page
├── answers/         (17 files)  - Tallyfy Answers AI search documentation
├── changelog/       (6 files)   - product changelog
├── denizen/         (2 files)   - Tallyfy Denizen localization documentation
└── pro/             (671 files) - Tallyfy Pro main product documentation (90% of all content)
```

**Total**: 697 .mdx files across 145 directories

> Measured **2026-08-06**. These figures read 585 and 99 until then, having drifted 27% low, and
> `changelog/` and `404.mdx` were missing from the tree entirely. Re-derive rather than trust:
> `find src/content/docs -name '*.mdx' -type f | wc -l`

## 🎯 Tallyfy Pro Structure (Primary Focus)

### Core Feature Categories

Ordered by size, largest first, so the biggest areas are the ones you see.

```
pro/                                   (671 files)
├── integrations/          (277 files) - Third-party connections
│   ├── open-api/          (75 files)  - REST API documentation
│   ├── vendors/           (46 files)  - Per-vendor integration guides
│   ├── middleware/        (43 files)  - Zapier, Make, Power Automate, Workato, Celigo
│   ├── analytics/         (20 files)  - Analytics and reporting tools
│   ├── byo-ai/            (19 files)  - Bring-your-own-AI guides
│   ├── authentication/    (9 files)   - SSO and identity providers
│   ├── cli/               (9 files)   - The Tallyfy CLI
│   ├── computer-ai-agents/ (9 files)  - Claude, ChatGPT, agent tooling
│   ├── mcp-server/        (7 files)   - MCP server
│   ├── tallyfy-desktop-ai/ (7 files)  - Desktop AI
│   ├── document-management/ (6 files) - Document systems
│   ├── email/             (6 files)   - Email integrations
│   ├── robotics/          (6 files)   - RPA and robotics
│   ├── webhooks/          (5 files)   - Webhook integrations
│   ├── azure-translation/ (4 files)   - Azure translation
│   ├── business-systems/  (2 files)   - Business system connections
│   ├── interactive-email-actions/ (1 file)
│   └── (3 files sit directly in integrations/)
│
├── changelog/             (128 files) - Release notes (date-organized)
│
├── documenting/           (79 files)  - Creating and managing content
│   ├── templates/         (54 files)  - Process templates and blueprints
│   ├── members/           (9 files)   - User management and permissions
│   ├── guests/            (7 files)   - External user management
│   ├── documents/         (6 files)   - Document templates
│   ├── groups/            (2 files)   - User groups
│   └── (1 file sits directly in documenting/)
│
├── tracking-and-tasks/    (50 files)  - Process execution and monitoring
│   ├── tasks/             (22 files)  - Individual task management
│   ├── processes/         (12 files)  - Launched process management
│   ├── tracker-view/      (9 files)   - Process tracking dashboard
│   ├── tasks-view/        (3 files)   - Task dashboard and filtering
│   └── (4 files sit directly in tracking-and-tasks/)
│
├── tutorials/             (50 files)  - Guided walkthroughs
├── miscellaneous/         (32 files)  - Support, troubleshooting, general topics
│
├── settings/              (29 files)  - Configuration and preferences
│   ├── billing/           (10 files)  - Plans, invoices, payment
│   ├── org-settings/      (10 files)  - Organization-wide settings
│   ├── personal-settings/ (8 files)   - Individual user settings
│   └── (1 file sits directly in settings/)
│
├── launching/             (14 files)  - Process initiation
├── by-role/               (4 files)   - Role-based navigation hub
├── compliance/            (3 files)   - Security and compliance
├── pricing/               (3 files)   - Plans and billing
├── lists/                 (1 file)    - Lists
└── index.mdx              (1 file)    - Pro product landing page
```

> Measured **2026-08-11**, and the whole tree above was rewritten in that pass because every
> single count in it was wrong. Three directories were missing outright (`tutorials/` at 50 files,
> `by-role/`, `lists/`), and `integrations/zapier/` had not existed for some time: it now lives at
> `integrations/middleware/zapier/`. The worst individual drift was `integrations/`, listed at 149
> against an actual 277.
>
> The top-level figures add up to the 671 stated for `pro/`, and each parent equals the sum of its
> children plus its own loose files. If you change these, keep that reconciliation true, because it
> is the only thing that catches a partial update.

## 🔍 Finding Documentation - Search Strategies

### By Feature/Topic
```bash
# Find template-related documentation
find /src/content/docs/pro/documenting/templates -name "*.mdx"

# Find task management articles
find /src/content/docs/pro/tracking-and-tasks/tasks -name "*.mdx"

# Find integration guides
find /src/content/docs/pro/integrations -name "*.mdx" | grep -v changelog
```

### By Content Type
```bash
# How-to guides
grep -r "how-to-" /src/content/docs/pro --include="*.mdx"

# Troubleshooting articles  
grep -r "troubleshoot\|problem\|issue\|error" /src/content/docs/pro --include="*.mdx"

# API documentation
find /src/content/docs/pro/integrations/open-api -name "*.mdx"
```

### By Common Keywords
```bash
# Assignment and user management
grep -r "assign\|member\|guest\|role" /src/content/docs/pro --include="*.mdx"

# Automation and rules
grep -r "automat\|rule\|trigger" /src/content/docs/pro --include="*.mdx"

# Forms and data collection
grep -r "form\|field\|data\|variable" /src/content/docs/pro --include="*.mdx"
```

## 📂 Common File Patterns

### Naming Conventions
- **How-to guides**: `how-to-[action].mdx`
- **Concept explanations**: `what-is-[concept].mdx` or `what-are-[concepts].mdx`
- **Question format**: `how-can-i-[action].mdx`
- **Index pages**: `index.mdx` (overview/navigation for each directory)

### Content Organization
- **Feature overview** → Main directory index.mdx
- **Specific actions** → Individual how-to files
- **Troubleshooting** → Usually in miscellaneous/troubleshooting/
- **Advanced topics** → Subdirectories with specialized content

## 🎯 Quick Navigation Map

### Most Commonly Updated Areas
1. **Templates & Workflows**: `pro/documenting/templates/` (54 files)
2. **Task Management**: `pro/tracking-and-tasks/tasks/` (22 files)
3. **Process Management**: `pro/tracking-and-tasks/processes/` (12 files)
4. **Integrations**: `pro/integrations/` (277 total files; per-vendor guides live under
   `pro/integrations/vendors/` and `pro/integrations/middleware/[vendor]/`, not `pro/integrations/[vendor]/`)
5. **User Management**: `pro/documenting/members/` + `pro/documenting/guests/` (16 files)

### Essential Index Pages
- `/pro/index.mdx` - Main product overview
- `/pro/documenting/templates/index.mdx` - Template system overview
- `/pro/tracking-and-tasks/index.mdx` - Process execution overview
- `/pro/integrations/index.mdx` - Integration hub overview

### Common Pain Points → Documentation Locations
- **Assignment issues** → `pro/tracking-and-tasks/tasks/how-to-assign-tasks-in-tallyfy.mdx`
- **Template creation** → `pro/documenting/templates/edit-templates/`
- **Process launching** → `pro/launching/` or `pro/tracking-and-tasks/processes/`
- **Integration setup** → `pro/integrations/[specific-vendor]/`
- **User permissions** → `pro/documenting/members/` or `pro/settings/`
- **Automation rules** → `pro/documenting/templates/automations/`
- **Form fields** → `pro/tracking-and-tasks/tasks/what-are-form-fields-in-tallyfy.mdx`

## 🔄 Update vs. Create Guidelines

### Update Existing File When:
- Topic clearly fits within existing article scope
- Adding clarification to existing instructions
- Expanding on current feature explanations
- Fixing gaps in existing content

### Create New File When:
- Entirely new feature or workflow
- Complex topic deserving its own article
- Cross-cutting concern not covered elsewhere
- Specific integration or vendor guide

Use this structure guide to efficiently locate existing documentation and determine the best placement for new content.