# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: Humanizing Rules Integration

**ALL AI content operations MUST incorporate the comprehensive humanizing guidelines from `humanizing-rules.md`**. These rules ensure content appears natural, human-written, and undetectable as AI-generated.

**Before any AI content work**: Review and apply the humanizing rules found in `/Users/amit/Documents/GitHub/documentation/humanizing-rules.md`

**Required in every AI prompt**: Include humanizing guidelines for conversational tone, varied sentence rhythm, specific examples, answer-first structure, and elimination of AI-typical phrases.

## ROLE & PRIMARY OBJECTIVE

You are working with Tallyfy's comprehensive product documentation. Your role is to act as a workflow expert and exceptionally skilled technical writer creating documentation for Tallyfy - a workflow and business process management SaaS platform.

**Primary Mission**: Write clear, concise articles that help non-technical users understand how to use specific Tallyfy features. Every piece of content must serve the singular goal of making users successful with the product while following all humanizing rules to ensure natural, human-like writing.

## PROJECT OVERVIEW

This is a **documentation website** for Tallyfy's suite of products built with **Astro and Starlight**.

**📁 COMPLETE DOCUMENTATION STRUCTURE**: See `DOCUMENTATION_STRUCTURE.md` for comprehensive organization guide including 578 .mdx files across 99 directories, search strategies, and file patterns.

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

### Tallyfy Pro Terminology & Concepts
- **Templates**: Where you define your process (API calls these "blueprints")
  - Two types: Document templates and Procedure templates
- **Processes**: Running instances of launched templates that you can track
- **Steps vs Tasks**: 
  - In a procedure template: single items are called "steps"
  - In a launched process: single items are called "tasks"
- **Automations**: "If this then that" rules
- **Views**:
  - Tasks view: Individual tasks assigned across all processes
  - Tracker view: Birds-eye view at per-process level
- **User Roles**: Administrator, Standard, and Light (Light users cannot edit/create templates)
- **Guests**: Email addresses outside your company (unlimited free)
- **Features**: API-first architecture, Free SSO for all customers

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

### Documentation Discovery Strategies
When identifying where to update documentation, use this search hierarchy:

1. **Check existing file coverage first**:
   ```bash
   # Find by feature area
   find /src/content/docs/pro/documenting/templates -name "*.mdx"
   find /src/content/docs/pro/tracking-and-tasks/tasks -name "*.mdx"
   
   # Search by keywords
   grep -r "assignment\|assign" /src/content/docs/pro --include="*.mdx"
   grep -r "automation\|rule" /src/content/docs/pro --include="*.mdx"
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
# Most common documentation areas (use these to narrow search)
ls /src/content/docs/pro/documenting/templates/     # 84 files - Template creation
ls /src/content/docs/pro/tracking-and-tasks/tasks/ # 25 files - Task management  
ls /src/content/docs/pro/integrations/             # 149 files - All integrations
ls /src/content/docs/pro/documenting/members/      # 19 files - User management

# Find specific topics
grep -l "how to assign" /src/content/docs/pro/**/*.mdx
grep -l "template\|blueprint" /src/content/docs/pro/**/*.mdx
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
   ---
   ```
   - New articles must use ID: `0000000000000000000000000000000000`
   - **description** field is generated server-side
   - **sidebar.order**: Use sequential numbers (1, 2, 3...) for articles within a section to control display order

2. **Component Imports**:
   - When using special components (Steps, CardGrid, LinkTitleCard), add import statements immediately after the frontmatter header
   - Example: `import { Steps } from '@astrojs/starlight/components';`
   - Import must appear before any article content

3. **Content Hierarchy**:
   - Start with H2 (`##`), never H1
   - Don't skip heading levels (H2 → H3 → H4)
   - All headings use sentence case (lowercase except proper nouns)

4. **Footers** (DO NOT EDIT except for new articles):
   - Must appear at article end
   - Contains related articles using CardGrid components

### Content Creation Rules
- Only create new articles when absolutely necessary
- When handling GitHub tickets, evaluate if documentation changes are needed
- Include prerequisites section for procedural articles
- Follow consistent structure based on content type (concept/task/reference/troubleshooting)
- **Directory structure requirement**: When creating new folders, always include an `index.mdx` file as the landing page for that directory to prevent build errors and provide proper navigation

### Content Automation System
This repository uses a sophisticated Python-based content automation system:

1. **Content IDs**: Generated server-side with MD5 hashes for unique page identification
2. **AI-Generated Descriptions**: `generate-snippets.py` uses Claude AI to create page descriptions
3. **Related Articles**: `generate-related-articles.py` fetches cross-references via Answers API
4. **Content Validation**: `markdown-lint.py` validates frontmatter structure and MDX syntax

### Content Validation
Run `python scripts/markdown-lint.py --dir src/content/docs` to validate:
- Frontmatter YAML structure
- Required fields presence
- UUID format validation
- Sidebar order requirements

## WRITING STYLE GUIDELINES

**CRITICAL**: All writing must follow the comprehensive humanizing guidelines in `humanizing-rules.md`. The rules below supplement but do not replace the humanizing requirements.

### Answer-First Content Structure (From Humanizing Rules)

Apply the answer-first pattern from `humanizing-rules.md`:
- Provide complete, actionable answer in first 2-3 sentences
- Use conversational tone with natural speech patterns
- Include specific examples and concrete details
- Vary sentence rhythm throughout

**See humanizing-rules.md for complete guidelines on natural content structure.**

### Voice & Tone (Enhanced by Humanizing Rules)
- **Apply all humanizing-rules.md guidelines first**
- Direct & Clear with conversational elements
- Simple language with varied sentence rhythm
- Natural contractions and personal pronouns
- Professional but conversational tone
- Eliminate all AI-typical phrases and patterns


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
- **Public URLs**: Base URL is `https://tallyfy.com/products/`
- **Core Concepts Linking Pattern**: 
  - Link sparingly to core concepts from the reference list when first mentioned in article body
  - Format: `[templates](mdc:products/pro/documenting/templates)`, `[tasks](mdc:products/pro/tracking-and-tasks/tasks)`
  - Only link when it adds value for understanding the current topic
- Link only first occurrence in a section
- Use descriptive anchor text (not "click here")
- Add "See also" sections when helpful

### Linking Best Practices
- Sparingly link to core concepts when helpful
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

## CONTENT MAINTENANCE


### Best Practices
- Test all instructions before publishing
- Maintain consistent terminology throughout documentation
- Write with accessibility in mind
- Consider both human readers and AI systems
- Keep examples realistic and relevant
- Update content when features change


## DEVELOPMENT WORKFLOW

When working with content:

1. Create/edit `.mdx` files in appropriate product directories
2. Content IDs are assigned automatically server-side
3. Run `python scripts/generate-snippets.py` to generate descriptions (requires API key)
4. Run `python scripts/markdown-lint.py` to validate structure
5. Use `npm run dev` to preview changes locally

## AI INTEGRATION

This repository extensively uses Claude AI for content automation:

1. **Content Generation**: `generate-snippets.py` uses Claude API to create descriptions
2. **Related Articles**: Integration with Tallyfy's Answers API for cross-references
3. **Configuration**: AI settings in `.claude/settings.local.json`

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

### Best Practices for Documentation Automation

1. **Atomic Tasks**: Each prompt should create/update one article or section
2. **Clear Context**: Reference specific files and follow CLAUDE.md guidelines
3. **Validation Steps**: Include prompts to validate generated content
4. **Incremental Updates**: Work on small batches to maintain quality

Example atomic prompts:
```
# Good: Specific and bounded
"Update the API authentication article at /products/pro/integrations/open-api/oauth-authorization-flow.mdx to include the new OAuth 2.0 flow changes from changelog 2025-03-31"

# Bad: Too broad
"Update all API documentation"
```

### Common Documentation Automation Patterns

1. **Changelog-Driven Updates**: Automatically update docs based on changelog entries
2. **Screenshot Updates**: Generate prompts to update screenshots when UI changes
3. **Cross-Reference Validation**: Verify all internal links remain valid
4. **Style Compliance**: Check and fix articles not following guidelines
5. **Missing Content Detection**: Identify and create stub articles for new features

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

### Content Optimization
- [ ] "Tallyfy" mentioned 1-3 times naturally (not "the platform")
- [ ] Answer provided in first 2-3 sentences
- [ ] Title under 60 characters when possible
- [ ] Includes specific numbers where available
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