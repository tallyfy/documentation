<!-- Last updated: 2025-07-08 15:40:15 -->
# Documentation Structure Guide

This file provides a comprehensive overview of the documentation organization to help with navigation, updates, and content creation.

## 📁 High-Level Structure

```
/src/content/docs/
├── answers/         (16 files)  - Tallyfy Answers AI search documentation
├── denizen/         (2 files)   - Tallyfy Denizen localization documentation  
├── manufactory/     (45 files)  - Tallyfy Manufactory observability documentation
└── pro/             (512 files) - Tallyfy Pro main product documentation (89% of all content)
```

**Total**: 578 .mdx files across 99 directories

## 🎯 Tallyfy Pro Structure (Primary Focus)

### Core Feature Categories

```
pro/
├── documenting/           (155 files) - Creating and managing content
│   ├── templates/         (84 files)  - Process templates and blueprints
│   ├── members/           (19 files)  - User management and permissions
│   ├── guests/            (17 files)  - External user management
│   └── documents/         (8 files)   - Document templates
│
├── tracking-and-tasks/    (65 files)  - Process execution and monitoring
│   ├── processes/         (15 files)  - Launched process management
│   ├── tasks/             (25 files)  - Individual task management
│   ├── tasks-view/        (12 files)  - Task dashboard and filtering
│   └── tracker-view/      (13 files)  - Process tracking dashboard
│
├── integrations/          (149 files) - Third-party connections
│   ├── analytics/         (35 files)  - Analytics and reporting tools
│   ├── zapier/            (23 files)  - Zapier automation platform
│   ├── open-api/          (27 files)  - REST API documentation
│   ├── middleware/        (25 files)  - Integration middleware
│   └── webhooks/          (9 files)   - Webhook integrations
│
├── settings/              (25 files)  - Configuration and preferences
│   ├── personal-settings/ (12 files)  - Individual user settings
│   └── org-settings/      (8 files)   - Organization-wide settings
│
├── launching/             (11 files)  - Process initiation
├── miscellaneous/         (46 files)  - Support, troubleshooting, general topics
├── compliance/            (9 files)   - Security and compliance
├── pricing/               (6 files)   - Plans and billing
└── changelog/             (136 files) - Release notes (date-organized)
```

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
1. **Templates & Workflows**: `pro/documenting/templates/` (84 files)
2. **Task Management**: `pro/tracking-and-tasks/tasks/` (25 files)  
3. **Process Management**: `pro/tracking-and-tasks/processes/` (15 files)
4. **Integrations**: `pro/integrations/[vendor]/` (149 total files)
5. **User Management**: `pro/documenting/members/` + `pro/documenting/guests/` (36 files)

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