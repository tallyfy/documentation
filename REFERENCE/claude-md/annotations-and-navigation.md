> Source of truth for hover annotations, role-based navigation and D2 resources. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.

# Hover annotations, role-based navigation and D2 resources

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
- **deadline automations** → Automatic due date calculations
- **public forms** → External data collection without login
- **runs** → Individual process instances from same template
- **automations** → If-this-then-that logic that adapts a running process

**Remember**: Only add footnotes when the term appears in a context where ~30% of users might need clarification. Never footnote basic UI terms or actions.

### Automated Intelligence System

A production-ready system exists at `/documentation/scripts/footnote-annotator.py` for batch processing. For individual articles during creation/editing, manually apply the protocol above.

**Key Stats from Testing**:
- ~85% of articles need NO footnotes
- ~12% benefit from 1-2 footnotes
- ~3% (technical/API docs) benefit from 3-5 footnotes
- Average character count: 95 characters per footnote
- Most valuable categories: Technical terms (30%), API parameters (25%), Performance metrics (20%), Tallyfy-specific terms (15%)

## 🧭 Role-based navigation: "By role" section, RoleChooser widget, and Audience bylines

Three connected pieces help readers find what applies to *them*. Both components are defined in **/support-docs** (the framework repo); the content and placement live here in /documentation.

### "By role" landing pages (`pro/by-role/`)

An additive, skippable navigation layer that points each role to EXISTING articles (no new article content, no content forking - it sits on top of the normal sidebar tree).

- `pro/by-role/index.mdx` - the hub (the role widget at full size).
- `pro/by-role/editor.mdx` - full-seat editors (build, launch, track, administer).
- `pro/by-role/user.mdx` - light-seat members (complete your own work).
- `pro/by-role/guest.mdx` - external guests (finish an emailed task).

Each page is a curated, answer-first set of grouped question -> article links. Keep them breathable, not exhaustive. These curated pages are the source of truth - we deliberately do NOT tag every article with role frontmatter.

### RoleChooser widget (reusable)

`import { RoleChooser } from "~/components";` then drop it on any page:

- `<RoleChooser variant="hero" />` - large, for the hub and the manual homepage.
- `<RoleChooser variant="inline" />` - compact, for embedding near the top of a section index.
- `<RoleChooser variant="inline" exclude="editor" heading="..." />` - drops the current role's card (used on the role pages themselves; `exclude` is `editor`, `member`, or `guest`).

The widget is always skippable (the full tree stays in the sidebar). Defined at `support-docs/src/components/RoleChooser.astro`. Currently embedded on `pro/index.mdx` and the tutorials, documenting, tracking-and-tasks, and launching index pages - add it to more pages freely (it's just one import + one tag).

### Audience byline (per-article "who is this for")

When an article applies ONLY to a specific role, mark it with the byline as the FIRST body element (it renders just under the title):

```mdx
import { Audience } from "~/components";

<Audience to="administrator" />
```

Values and when to use them (grounded in api-v2 permissions - do NOT over-label):

- `administrator` - truly admin-gated features only (api-v2 `admin` middleware): billing, org settings, branding/SMTP, system log, member role-change/remove/permissions, SSO setup, permanent delete.
- `editor` - full-seat authoring that `light_role_restrict` blocks for Light members: creating and editing templates, documents, automations, variables.
- `guest` - genuinely guest-facing articles (what a guest reads), NOT the member-facing "managing guests" articles.
- **No byline** = anyone can use it (Light members and guests included). Most articles get NO byline; absence is the signal.

**De-dup rule:** if an article already had an inline "Admin only" callout that the byline now states, remove the callout. Never keep both.

Defined at `support-docs/src/components/Audience.astro`. Bulk annotation uses `scripts/audience_byline.py` (idempotent - skips files already carrying an `<Audience>`, and preserves frontmatter + line endings byte-for-byte). It reads a simple `ROLE<TAB>path` manifest; re-derive the per-role file list by grepping existing bylines or from the classification rules above.

### Author / entity attribution (publisher entity, NOT a personal byline)

Docs are attributed to the **Tallyfy organization** (publisher), set globally in `support-docs/src/utils/structured-data.ts` (`ORGANIZATION_SCHEMA` + per-page `TechArticle`, with `founder` = Amit Kothari by `@id` to `https://tallyfy.com/authors/amit-kothari/`). This is deliberate: for non-YMYL help docs a personal author byline is not a Google ranking factor and implies an editorial process the auto-pipeline doesn't run (a Trust risk). So:

- Do NOT add a visible personal author byline or per-article `Person` schema to docs.
- Named-author E-E-A-T stays on the blog (website-astro), where readers expect it.

## D2 Diagrams Resources

**Production-Ready Diagram Assets**: D2 diagrams are rendered to external SVG files for reuse across all platforms. See the **D2 Diagrams Inventory** section in `/README.md` for complete details.

### Quick Access Information:
- **Base URL**: `https://tallyfy.com/products/d2-diagrams/docs/`
- **URL Pattern**: `https://tallyfy.com/products/d2-diagrams/docs/[path]/[filename]-[index].svg`
- **Important**: Note the `/docs/` prefix after `/d2-diagrams/` - this is required
- **Full Metadata**: Available in `/temporary/d2_inventory.json`

### Available Categories

- **API Integration Flows**: Zapier, Power Automate, n8n, Make.com workflows
- **Computer AI Agents**: Claude, ChatGPT, Skyvern, local agents
- **Authentication & SSO**: Azure AD, Okta, OneLogin, Auth0
- **Process Workflows**: Multi-level approvals, process launching
- **Webhook Integrations**: Event triggers, external integrations
- **System Architecture**: Distributed tracing, WebSocket connections

> **The per-category counts and percentages were removed rather than re-derived.** They were
> already wrong: the seven categories summed to 64 against a stated total of 63, and nobody
> noticed because a percentage looks authoritative. Re-derive the live figure instead of
> trusting any number written here:
> ```bash
> grep -rc '```d2' --include='*.mdx' src/content/docs | awk -F: '{s+=$2} END{print s}'
> ```
> Measured 2026-08-12: **57 diagrams across 50 files**, after the 4 Manufactory ones went with
> their pages in tallyfy/documentation#127.

### Example Working URLs:
- Zapier Integration: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/middleware/zapier/how-to-automate-tasks-in-tallyfy-using-zaps-0.svg`
- OAuth Flow: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/open-api/oauth-authorization-flow-0.svg`
- Multi-level Approvals: `https://tallyfy.com/products/d2-diagrams/docs/pro/documenting/templates/automations/examples/multi-level-approval-loops-0.svg`
- Azure AD SSO: `https://tallyfy.com/products/d2-diagrams/docs/pro/integrations/authentication/how-to-integrate-azure-ad-samlsso-with-tallyfy-0.svg`
