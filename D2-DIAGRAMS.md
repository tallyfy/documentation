# D2 Diagram Guidelines for Tallyfy Documentation

This file contains comprehensive D2 diagram guidelines for Tallyfy documentation. It was extracted from CLAUDE.md to optimize token usage while maintaining all critical information.

## 🚨 MANDATORY NOTATION RULES

**CRITICAL**: D2 provides cleaner, more maintainable diagram notation. These rules are MANDATORY for consistent rendering.

### ❌ FORBIDDEN NOTATION (Never Use These)

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

### ✅ CORRECT NOTATION PATTERNS

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

### 🔍 PREVENTING TEXT BLEEDING

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

## 🔧 D2 Syntax Troubleshooting

**CRITICAL SYNTAX ERRORS TO AVOID** (from Cloudflare Pages build failures):

1. **Dollar signs trigger variable substitution**:
   - ❌ WRONG: `Check: "Amount > $5000?"`
   - ✅ RIGHT: `Check: "Amount > 5000?"`
   - D2 interprets `$` as start of variable substitution

2. **Invalid node syntax with square brackets**:
   - ❌ WRONG: `TallyfyInputs[Tallyfy Process]: { ... }`
   - ✅ RIGHT: `TallyfyInputs: "Tallyfy Process" { ... }`
   - Square brackets in node names aren't valid D2 syntax

3. **No mixed node definitions and edges on same line**:
   - ❌ WRONG: `Request: "Task Request" -> Planner: "Sets goals"`
   - ✅ RIGHT: Separate into two lines:
     ```
     Request: "Task Request"
     Request -> Planner: "Sets goals"
     ```
   - Node definitions and edge definitions must be on separate lines

4. **Self-loops on containers not supported**:
   - ❌ WRONG: Container with note/children having `Container -> Container`
   - ✅ RIGHT: Move self-loop action into the note text
   - D2's dagre layout engine doesn't support self-loops on containers

5. **Position constants are limited**:
   - ❌ WRONG: `{near: middle-center}` (doesn't exist)
   - ✅ RIGHT: Valid positions: top-left, top-center, top-right, center-left, center-right, bottom-left, bottom-center, bottom-right

6. **Local validation before pushing**:
   ```bash
   # Validate all D2 diagrams locally
   ./scripts/validate-d2.sh
   ```

## Critical Implementation Notes

**RENDERING CONFIGURATION**: All D2 diagrams are rendered with global theme and configuration settings defined in `/support-docs`. Individual diagrams should focus on content structure, not styling. The global config handles:
- Brand colors (light green #f2faf4, #e1f7e6 with dark green borders #225930)
- Dark mode colors (#0D0D0D background, rgba(11, 40, 19, 0.4) nodes)
- Font settings (Inter Variable)
- Node spacing and padding
- Automatic text wrapping

## 🎨 D2 Diagram Color Palette

**MANDATORY**: Use ONLY these colors in D2 diagrams. Random colors are forbidden. Style attributes should be minimal and only when absolutely necessary for clarity.

### Light Theme Colors (Manual and Website)
- **Primary Fill**: `#f2faf4` (rgb(242 250 244) - use without opacity in D2)
- **Secondary Fill**: `#e1f7e6` (rgb(225 247 230) - use without opacity in D2)
- **Border Color**: `#225930` (rgb(34 89 48) - dark green for borders and strokes)
- **Warning/Reminder**: `#fff3cd` (light yellow for special states)
- **Text**: Black (default) - Never override
- **Background**: White (default)

### Dark Theme Colors
- **Primary Fill**: `#0D0D0D` - Near black
- **Secondary Fill**: `#0b2813` (rgb(11 40 19) - dark green tint)
- **Border Color**: `#e1f7e6` (rgb(225 247 230) - light green border)
- **Text**: White (automatic) - Never override
- **Background**: `#0D0D0D`

### D2 Usage in Code
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

### Usage Rules
1. **NO random colors**: Never use red, blue, yellow, orange, etc. unless semantically meaningful
2. **NO inline styles**: Let global config handle 99% of styling
3. **Semantic colors ONLY when necessary**:
   - Success/Approval: Use default green theme
   - Error/Rejection: May use subtle red ONLY for clear error states
   - Warning: Avoid - use text labels instead
4. **Consistency**: All diagrams must look cohesive across the documentation
5. **Simplicity**: When in doubt, use NO color styling - let defaults handle it

**ENFORCEMENT**: These notation rules are MANDATORY. Every D2 diagram must follow them to ensure consistent rendering. When creating or editing diagrams, mentally check each rule before committing changes.

## When to Use Visual Diagrams - Thorough Consideration Required

**CRITICAL RULE**: Only add D2 diagrams where they provide clear value for understanding complex flows or interactions. Based on extensive analysis, only **10-15% of documentation articles** should have diagrams. Most documentation is better with clear text.

**THOROUGH ANALYSIS APPROACH**: Before adding any diagram, you must:
1. Read the ENTIRE article to understand full context
2. Think from three perspectives: beginner, intermediate, expert
3. Ask: "Is the cognitive effort to understand a diagram LESS than understanding the text alone?"
4. Apply the "lagom" principle - not too much, not too little
5. Consider if visual learners specifically benefit
6. Evaluate long-term maintenance burden

### ✅ Good Candidates for Diagrams (High Value Patterns)
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

### ❌ Poor Candidates for Diagrams (Skip These)
- Simple linear processes (≤3 steps) - Use `<Steps>` component instead
- Single API calls without complex flow - Code blocks are clearer
- Basic CRUD operations
- UI navigation - Screenshots are better
- Content easily explained with bullet points
- Troubleshooting checklists - Bullet points work best
- Feature lists or changelogs - Text lists are appropriate
- Simple two-state toggles - Text description is sufficient

## Documentation Areas and Diagram Types

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

## Terminology Guidelines for Diagrams

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

## D2 Syntax Requirements (MANDATORY)

**CRITICAL SYNTAX RULES** to prevent parse errors:

### ✅ CORRECT Node Definition
```d2
NodeA: Simple Label
NodeB: Label with spaces
NodeC: |md
  Multi
  Line Label
|
```

### ❌ SYNTAX ERRORS TO AVOID
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

### Essential Syntax Rules:
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

## Content-Specific Diagram Templates

### For OAuth Documentation
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

### For Process Triggers
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

### For Webhook Events
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

### For Automation Logic (Reflecting Actual System)
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

## Webhook and API Visualization Best Practices

### API Call Representation

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

### Webhook Flow Patterns

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

### SSO and Authentication Flows

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

## Auto-Generation Rules

### When You See These Patterns → Generate Diagrams

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

## Diagram Placement & Article Structure

### Recommended Article Structure with Diagrams
When including a D2 diagram, follow this proven structure:
1. **H2 heading** for the concept
2. **One-sentence "What this shows" line** - Brief context
3. **D2 code fence** - The diagram itself
4. **3 bullets titled "What to notice"** - Call out key insights
5. **Optional links** to deeper concepts embedded in the diagram

### Placement Golden Rules
1. **For feature overviews**: Place diagram IMMEDIATELY after overview paragraph
2. **For troubleshooting**: Put at TOP before wall-of-text steps
3. **For concepts**: After the intro, before deep details
4. **For quick starts**: At the very beginning for 5-second path understanding
5. **For complex flows**: Chapter with anchors and link between sections

### Visual Best Practices
- **One idea per diagram** - Split if >30 nodes
- **Labels**: ≤5 words per node; edges are verbs ("sends", "approves")
- **Flow direction**:
  - LR (left-right) for features and processes
  - TD (top-down) for troubleshooting and decision trees
- **Decisions**: Always use diamonds with at least two labeled exits
- **Swimlanes**: Use `subgraph` with recognizable titles ("Your Workspace", "Tallyfy Cloud")
- **Consistency**: Reuse node names across pages ("Task", "Approval")

### Quality Checklist
- **Clarity**: Is the diagram easier to understand than text?
- **Completeness**: Are all paths and error states shown?
- **Accuracy**: Does it reflect the actual system behavior?
- **Simplicity**: One concept per diagram, <30 nodes ideal, 50 max
- **Mobile-friendly**: Readable on small screens
- **Value-add**: Would removing the diagram hurt understanding?
- **Maintenance**: Will this need frequent updates?

## Hyperlinks in D2 Diagrams

### Making Diagrams Interactive Navigation Hubs
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

### Hyperlink Support in D2
- ✅ **Full support**: All node types support hyperlinks
- ✅ **Tooltips**: Rich tooltips on hover
- ✅ **External links**: Full URL support
- **Note**: D2 provides consistent link support across all diagram types

### Link Patterns
1. **Internal docs**: `link: /products/pro/path/`
2. **Same-page anchors**: `link: #section-id`
3. **External sites**: `link: https://api.tallyfy.com`
4. **With tooltip**: `tooltip: Descriptive text`

**Best Practice**: Add at least 2 links per diagram to make it a navigation hub.

## Practical D2 Implementation

### Creating Effective Prompts for AI
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

### Animated Arrows in D2 Diagrams

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

### Golden Nuggets for Specific Diagram Types

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

### Common Tallyfy Entities
**Core**: Template, Process, Step, Task, Form
**Users**: Admin, Member (Standard/Light), Guest, Owner
**Integration**: Webhook, API, WebSocket, Email trigger

### Technical Constraints
- Maximum 30 nodes ideal, 50 absolute max (performance)
- Avoid nesting beyond 3 levels
- Split complex flows into multiple focused diagrams
- Ensure text remains readable on mobile devices
- One idea per diagram - chapter large flows with anchors

## Global Configuration & CSS (DO NOT OVERRIDE)

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

## Mobile-Friendly D2 Design Guidelines

### Layout Orientation for Device Compatibility

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

### Dark Mode Compatibility

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

### Responsive Design Patterns

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

### Text Spacing and Readability

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

## D2 Diagram Maintenance Rules

**CRITICAL**: When updating ANY article that contains D2 diagrams, you MUST:

1. **Review Existing Diagrams**: Check if the content changes affect the diagram's accuracy
2. **Update Diagram Content**: If the article changes modify any process, flow, or relationship shown in the diagram, update the D2 notation accordingly
3. **Maintain Consistency**: Ensure terminology in the diagram matches the updated article text
4. **Verify Links**: If the diagram contains `click` statements, verify all linked paths remain valid
5. **Apply thorough analysis**: Re-evaluate if the diagram still adds value after the content update
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

## D2 Configuration in Astro Starlight

### Supported Diagram Types with D2
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

### Platform Configuration
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

## ⚠️ CRITICAL D2 DIAGRAM ISSUES TO AVOID

### 1. Text Visibility Problem (MUST FIX)
**PROBLEM**: Text appears white/invisible on light backgrounds in light mode.
**SOLUTION**: Text color is now forced to black in light mode via global CSS. Never override this.

### 2. Broken Hyperlinks (ALWAYS VERIFY)
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

## D2 Diagram Troubleshooting Guide

### Common Build Errors and Solutions

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

### Debug Commands
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