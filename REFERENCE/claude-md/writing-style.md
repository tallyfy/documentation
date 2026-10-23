> Source of truth for the writing style guidelines. Moved word for word from `../../CLAUDE.md` on 2026-10-21
> (owner decision 2026-10-20). Edit here; that CLAUDE.md keeps only a pointer. A section
> the text below names by title is found through that CLAUDE.md, which keeps its heading
> or names it in a pointer.

# The writing style guidelines

## WRITING STYLE GUIDELINES

### Core Humanization Framework

All AI-generated technical documentation must appear natural, human-written, and undetectable as AI-generated content. These guidelines are MANDATORY for all content operations.

#### Natural Voice & Conversational Tone

**Direct & Clear Communication**:
- **Write as if explaining to a colleague**: Use first and second person naturally
- **Conversational approach**: Include "you", "you're", "can't", "won't", "it's" throughout
- **Global accessibility**: Simple language at roughly an 8th-grade reading level (the target in CLAUDE.md, "Write for business readers, not engineers")
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
- **No rhythm quotas**: Let a sentence be short when what it says is short. Never add a one-word punch line to meet a count; a manufactured closer reads as machine-written (changed 2026-10-22, #391)
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
- **Strategic fragments**: Use sparingly (1-2 per article) for emphasis, and never as a question you answer in the next breath, which `DOCS-VOICE.md` bans as a self-answered question (examples removed 2026-10-22, #391)
- **Conversational asides in parentheses**: Add brief, helpful context
  - "(yes, it's that straightforward)"
  - "(not just specific people)"
  - "(this takes about 5 minutes)"
- **Questions**: A question in a heading, or a checklist of questions put to the reader, is fine. A question you answer yourself, and a connector that promises something interesting is coming, are both banned in `DOCS-VOICE.md` (changed 2026-10-22, #391)

**Emotional Variation in Technical Content**: Removed 2026-10-22 (#391). Its examples were the moves `DOCS-VOICE.md` bans: promising a good part is coming, saying a thing is hard instead of saying what it is, answering your own question, and performing a conversation with the reader. Warmth in docs comes from plain help: say what the reader gets, then what to click.

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
  - Good: "Want to automate task assignments? Simple. Just configure the automations in your template."
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
