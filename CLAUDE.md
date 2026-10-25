# CLAUDE.md

> **NEVER use auto memory** (`~/.claude/projects/*/memory/`) — store all knowledge in this repo's CLAUDE.md file.

> **Codex and other agents read this file too.** `AGENTS.md` is a link to it, and each folder in `.claude/skills/` has a matching relative link in `.agents/skills/`, which is where Codex looks for skills. When you add a skill, add its link as well: `ln -s ../../.claude/skills/<name> .agents/skills/<name>`.

> **AI task reliability cross-links (2026-05):** three doc pages carry a one-line curious-reader callout to the public marketing tool `https://tallyfy.com/tools/ai-task-reliability/` (and the post `/ai-tasks-not-jobs/`): `pro/tracking-and-tasks/tasks/index.mdx`, `pro/documenting/templates/automations/index.mdx`, `pro/integrations/computer-ai-agents/index.mdx`. They are plain root-relative links, no embed. Leave them unless the tool URL changes.


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

### Adapted humanization rules for documentation

These rules apply to ALL documentation content (adapted from blog humanization rules -- docs-specific, lighter touch):

**Zero-tolerance blacklisted words** (always replace):
delve, landscape, tapestry, multifaceted, pivotal, comprehensive, seamless, robust, leverage, facilitate, paramount, meticulous, underscore, moreover, furthermore, indeed, subsequently, additionally, endeavor, embark, "in essence", notably, arguably, methodology, stakeholder, innovative, scalable

**Context-dependent words** (keep when technical, replace when AI filler):
- "framework" -- KEEP for actual software frameworks, REPLACE "a framework for understanding"
- "navigate" -- KEEP for UI instructions ("navigate to Settings"), REPLACE "navigate challenges"
- "utilize" -- KEEP only in URLs that can't be changed, otherwise replace with "use"

**Mandatory rules:**
- Zero em-dashes (—) in all content. Use periods, commas, colons, or spaced hyphens instead
- Use contractions naturally throughout, including footnotes (don't, won't, can't, it's, you'll, etc.). Exception: keep uncontracted for emphasis ("Do NOT delete")
- All headings in sentence case (capitalize first word + proper nouns only)
- All frontmatter descriptions must end with a period. For their LENGTH see the single
  rule under "Article Structure Rules" below, and do not restate a number here: a length
  quoted in two places is how this file came to state two different ones
- Fix empty alt text on images: `![]()` -> `![Descriptive text]()`
- Replace wordy phrases: "in order to" -> "to", "prior to" -> "before", etc.

**Do NOT apply to docs** (blog-only rules):
- E-E-A-T markers, experience markers, catchphrase pools
- Self-doubt expressions, creative immersion
- Named entity density, register mixing
- Paragraph rhythm SD targets, British English markers

### Governance: preventing regression

All new documentation articles must pass these checks before merge:
- Zero em-dashes
- Zero blacklisted words (zero-tolerance list)
- At least 1 contraction per article (3+ for articles over 400 words)
- Description ends with period
- Headings in sentence case
- No empty alt text on images
- Passes `scripts/simplicity-check.py` below the complexity threshold (business-reader simplicity)
- Passes `scripts/ai-tell-check.py` (AI rhetorical tells - see below)

⚠️ **The blacklist above is fully satisfied and catches nothing.** Measured across all 505
eligible articles on 2026-09-03: **all 26** zero-tolerance entries appear **zero** times in the
prose a reader sees. (One raw file carries "stakeholders", inside a fenced example block.)
Control on the same sweep: 258 files contain "template", so the probe was not blind. A green
result against that list therefore says nothing about whether an article reads as
machine-written.

What the owner actually objects to is a **move, not a vocabulary item**: a sentence that promises
significance and defers the fact. He named three, and none of them contains a banned word, so no
word list could ever have found them: *"This is the part worth knowing before you build"*,
*"the hard part"*, *"what nobody knew"*.

**The standard is [`DOCS-VOICE.md`](DOCS-VOICE.md)**, enforced by `scripts/ai-tell-check.py` from
the rules in `.github/ai-tells.txt`, as the `ai-tell-gate` job that blocks `sync` in the
pipeline. It checks twelve shapes rather than words, and it **blocks rather than rewrites** -
deliberately unlike `scripts/generate-related-articles.py`, which silently maps `comprehensive`
to `complete`. A silent rewrite is right for the card text that script generates and wrong for an
article body, because the author never finds out and the next article repeats it.

```bash
python3 scripts/ai-tell-check.py --files src/content/docs/path/to/article.mdx --strict
```

Exit 0 clean, 1 findings, **2 the checker itself could not run** - never read a 2 as clean.
`## Related articles` and every `<CardGrid>` are excluded, because they regenerate from the
Answers API on each pipeline run and a finding inside one is a finding a human cannot fix.

## ✍️ Write for business readers, not engineers (lowest common denominator)

Tallyfy's docs are read by busy, non-technical business people: buyers, admins, and everyday users, many reading in a second language. NOT engineers. Write for the lowest common denominator. The most common failure in our docs is sounding like a spec sheet: leading with OAuth flows, RFC numbers, VRAM math, and benchmark scores that a business reader neither understands nor needs.

**This rule sits alongside the humanization rules above. It doesn't replace them.** Keep the contractions, varied rhythm, sentence-case headings, and the em-dash ban. This adds one thing: simple enough for anyone.

### The reading-level target

- Aim for roughly an 8th-grade reading level (Flesch-Kincaid grade ≤ ~9, Reading Ease ≥ ~60).
- Short sentences. One idea each. Plain everyday words over fancy ones ("use" not "utilize", "set up" not "provision").
- A reader should understand the opening without Googling a single term.
- End bullet items with a period when they're complete thoughts. It reads cleaner, and it stops readability tools from treating a run of period-less bullets as one giant run-on sentence.

### Lead with the business answer

The first 2-3 sentences after the H2 say what this does *for you*, in plain words, with zero jargon and zero spec. State the outcome, then the "how", then any detail. Our `byo-ai/use-cases/*` articles are the model: imitate them.

- Good: "Sign in once with your normal company login, and every approved AI tool just works. No separate password per tool."
- Bad: "Tallyfy's MCP server implements OAuth 2.1 with PKCE S256 and Dynamic Client Registration (RFC 7591)."

### Demote technical detail. Never delete it. Never lose meaning.

Real technical facts (OAuth/PKCE/RFC/JWT/VRAM/benchmarks/limits/setup specifics) are valuable to whoever actually does the integration. Don't strip them. Move them down, and keep every one:

- **A single inline term** that has to stay in the flow goes to a footnote (`[^1]`, 50-150 chars, placed before the Related articles section).
- **A block of specs** (the whole OAuth flow, VRAM tables, benchmark numbers, config snippets) goes to a clearly-labeled section near the bottom. **Pick the heading that fits who needs it:**
  - `## For your IT team` for SSO, security, org/admin setup
  - `## For developers` for API, code, MCP/webhook wiring
  - `## Technical details` as the neutral default when it's neither

  Start that section with: *"(Skip this unless you're setting up the technical side.)"*

**Never lose essential meaning.** Before you simplify, list every essential point in the article (facts, steps, limits, supported options, gotchas). After, confirm each one still appears somewhere: body, footnote, or the technical section. Simplifying the language is required. Dropping a fact is a bug. Only true fluff (empty benefit statements) gets deleted.

### Jargon discipline

- **Never in business prose** (demote to a footnote or technical section, or cut): PKCE, RS256, JWT, jwks, RFC numbers, `mcp_resource`, stdio, SSE, VRAM, TFLOPs, quantization, MoE, FP8, tokens/second, DLP, WAF, VNet, load balancer.
- **Explain on first use** (a one-line gloss or footnote the first time, then use it freely): OAuth, OIDC, SAML, SCIM, webhook, SSO, MFA, IAM, API, BPMN, RPA, MCP, inference, embeddings, SLM, LLM.
- **Fine as-is** (our product vocabulary): templates, processes, tasks, steps, runs, blueprints, snippets, automations, kick-off form, job titles, guests, light users, tracker view.

### Diagrams: simple or none

A flowchart with load balancers, WAF, DLP, or VNet boxes is for architects, not business readers. Keep each diagram to a single clear idea (an approval flow, a simple sequence). If a diagram needs a legend to follow, it's too complex. Cut it or move it to the technical section.

### Reference docs are the exception

Developer and API reference under `pro/integrations/open-api` and `pro/integrations/webhooks` may keep more jargon. Their audience genuinely is developers. Everything else (customer and buyer-facing) follows the lowest-common-denominator rule.

Pages under `pro/integrations/open-api/code-samples` are not scored at all. `scripts/simplicity-check.py` skips them in every mode, and says SKIPPED when you name one with `--files` (owner decision, #285). `python3 scripts/simplicity-check.py --self-test` proves that rule works in both directions. The skip is `ALWAYS_SKIP` in the script, landed in #290. Pages under `open-api/api-clients` are different: triage (`--dir`) leaves them out through `TRIAGE_ONLY_SKIP`, but they are still scored when named with `--files` (owner, 2026-09-23).

### Enforce it

Before committing any article, run:

```bash
python3 scripts/simplicity-check.py --files src/content/docs/path/to/article.mdx --report
```

It must score **below the threshold** (default 45) with no AI-tell words. `--files` takes paths separated by spaces, commas, or both, as `ai-tell-check.py` does, and a run that scores no file exits 2 (#259). The script is read-only and scores only the business-facing part of the page, so detail you've correctly demoted into a footnote or technical section doesn't count against you.

Every pull request into `staging` or `main` also gets a readability report in its job summary, from `.github/workflows/readability-report.yml` (#291). It shows the score of each page the pull request changes. It is report only: a score never fails it, and it is not a required check. It goes red only when the checker itself breaks, and then the summary says "checker error". The workflow landed in #292.

## 📝 Hover Annotations (Footnotes) Guidelines

**Moved:** the hover annotation guidelines. Source of truth: `REFERENCE/claude-md/annotations-and-navigation.md`, section
"📝 Hover Annotations (Footnotes) Guidelines". Read it before adding a footnote or hover annotation;
edit it there, not here.

- Before touching role navigation or audience bylines: section "🧭 Role-based navigation: "By role" section, RoleChooser widget, and Audience bylines".
- Before making a D2 diagram: section "D2 Diagrams Resources".

## ROLE & PRIMARY OBJECTIVE

You are working with Tallyfy's comprehensive product documentation. Your role is to act as a workflow expert and exceptionally skilled technical writer creating documentation for Tallyfy - a workflow and business process management SaaS platform.

**Primary Mission**: Write clear, concise articles that help non-technical users understand how to use specific Tallyfy features. Every piece of content must serve the singular goal of making users successful with the product while following all humanizing rules to ensure natural, human-like writing.

## PROJECT OVERVIEW

**Moved:** the project overview. Source of truth: `REFERENCE/claude-md/project.md`, section
"PROJECT OVERVIEW". Read it before a first change in this repo;
edit it there, not here.

- Before looking for or updating an article: section "FINDING & UPDATING DOCUMENTATION".

## DEVELOPMENT COMMANDS

```bash
# Development
npm install                    # Install dependencies
npm run dev                   # Start development server

# Content Automation (Python scripts)
python scripts/generate-ids.py --dir [repo root] [--dry-run]       # Give every page lacking one an id (whole tree, #296)
python scripts/generate-snippets.py --dir [repo root] --token [api-key] --prompt [base64-prompt] [--dry-run]   # Description for every page lacking one
python scripts/generate-related-articles.py --dir [directory] --answers_api_key [key]
python scripts/markdown-lint.py --dir [directory]
python scripts/check-deleted-files.py --dir [repo root] --collection_name tyfy --answers_api_key [key] --base_url [answers url] [--dry-run]   # Remove index entries whose page is gone
python3 scripts/update-documentation-structure.py         # Rewrite the file counts in DOCUMENTATION_STRUCTURE.md and this file (--check to report only)
# Dated 2026-10-21 (#384): the count lines moved to REFERENCE/claude-md/project.md, so the script now rewrites that file, not this one.
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

**Moved:** the platform and technical requirements. Source of truth: `REFERENCE/claude-md/platform-and-technical.md`, section
"PLATFORM & TECHNICAL REQUIREMENTS". Read it before writing or structuring any article;
edit it there, not here.

- Before setting an article's length or structure: section "Article Structure Rules".
- Before editing anything a pipeline generates: section "Pipeline behavior: what's safe to edit vs auto-generated".

## WRITING STYLE GUIDELINES

**Moved:** the writing style guidelines. Source of truth: `REFERENCE/claude-md/writing-style.md`, section
"WRITING STYLE GUIDELINES". Read it before writing or editing any article;
edit it there, not here.

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

**Moved:** the linking rules and the deployment pipeline. Source of truth: `REFERENCE/claude-md/linking-and-deployment.md`, section
"LINKING & REFERENCES". Read it before adding a link, before any push or merge into `staging` or
`main`, and before any promotion to production; edit it there, not here.

- Before any push or merge into `staging` or `main`, to know what deploys: section "Deployment Pipeline Architecture".
- Before promoting `staging` to `main`, in full or in part: section "Deploying staging to production".
- Before adding, releasing or relying on a promotion hold: section "Holding a path back from production (`.github/promotion-holds.txt`)".
- After a promotion, before saying it is live or purging the cache: section "Verifying deployment".
- Before adding an external link: section "External Link Requirements".

Always in force: merging into `main` publishes to tallyfy.com/products. The `sync` job deletes or
reverts anything published that `main` lacks. So before any promotion, check that `main` is not
behind what is published, and read the promotion diff by hand, because a hold cannot block a
deletion.

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

**Moved:** SEO and AI optimization. Source of truth: `REFERENCE/claude-md/seo-dates-and-automation.md`, section
"SEO & AI OPTIMIZATION". Read it before changing titles, descriptions or structured data;
edit it there, not here.

## TROUBLESHOOTING CONTENT

### Format
- Clear problem/cause/solution structure
- Use tables or lists for multiple issues
- Include exact error messages in `code` format
- Specific solutions (not "check your settings")
- Preventative measures when applicable
- Link to support resources for complex issues

## LAST UPDATED DATES SYSTEM

**Moved:** the last updated dates system. Source of truth: `REFERENCE/claude-md/seo-dates-and-automation.md`, section
"LAST UPDATED DATES SYSTEM". Read it before changing how dates are shown;
edit it there, not here.

- Before automating documentation work: section "CLAUDE CODE AUTOMATION PHILOSOPHY".

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
- Deep analysis approach for diagram decisions

## DOCUMENTATION ASSET MANAGEMENT

**Moved:** the documentation asset management system. Source of truth: `REFERENCE/claude-md/asset-management.md`, section
"DOCUMENTATION ASSET MANAGEMENT". Read it before adding, captioning or moving a screenshot or image;
edit it there, not here.

## QUICK REFERENCE CHECKLIST

Before submitting documentation:

### Content Structure & Writing
- [ ] Uses H2 for main headings, maintains hierarchy
- [ ] Answer-first structure: Complete answer in first 2-3 sentences
- [ ] Written in simple, clear language (roughly an 8th-grade reading level, as set above)
- [ ] UI elements are **bold**
- [ ] One main topic per article
- [ ] High information density - every sentence adds value
- [ ] Active voice and present tense throughout
- [ ] Procedures start with action verbs
- [ ] Varied sentence lengths for natural rhythm

### D2 Diagrams (If Applicable)
- [ ] Deep analysis applied - diagram truly adds value (10-15% of articles)
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

## CI runners and pull requests (dated 2026-10-06)

This repo is public. All its CI runs on GitHub-hosted runners and it sets no `CI_*` variable.

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