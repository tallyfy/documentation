# Documentation voice: the AI rhetorical tells

The one rule: **say the thing.** Do not tell the reader that what follows is significant, hard,
secret or surprising. Write the fact and let them decide.

This file is the standard. `scripts/ai-tell-check.py` enforces it, from the rules in
`.github/ai-tells.txt`, as the `ai-tell-gate` job that blocks `sync` in the pipeline.

## Why a word list was not enough

CLAUDE.md carries a 26 word blacklist. Measured across all 505 eligible articles on 2026-09-03,
**all 26 appear zero times** in the prose a reader sees. (One raw file carries "stakeholders",
inside a fenced example block.) The rule was fully satisfied and caught nothing.

The owner then named three phrasings he never wants to read, and **none of them contains a
banned word**, so no word list could ever have found them. What he objects to is a move, not a
vocabulary item: a sentence that promises significance and defers the fact. So the checker looks
at shapes.

## It blocks. It does not rewrite.

`scripts/generate-related-articles.py` silently maps `comprehensive` to `complete`. That is right
for the card text it generates and wrong for an article body, because the author never finds out
and the next article repeats it. A blocked build teaches. A silent rewrite does not.

## What is skipped, and why you will see it printed on every run

The `## Related articles` block and every `<CardGrid>` are excluded. They regenerate from the
Tallyfy Answers API on each pipeline run, so a finding inside one is a finding a human cannot fix
and CI would overwrite. Also excluded: code fences, inline code, JSX tags, imports, comments,
image alt, table rows, link URLs, and all frontmatter **except** `description:`, which ships to
search results and to Answers and is therefore prose a reader sees.

## The eleven classes

| Class | The move |
|---|---|
| manufactured-revelation | promises a revelation, defers the fact |
| difficulty-framing | says a thing is hard instead of saying what it is |
| manufactured-exclusivity | flatters the reader for knowing what you are about to tell them |
| self-answered-question | asks a question purely to answer it in the next breath |
| false-contrast | denies a straw alternative to make the real subject look larger |
| false-intimacy | performs a conversation that is not happening |
| conclusion-signposting | announces a summary instead of writing one |
| inflation-verb | a marketing verb where a plain one would do |
| vague-attribution | borrows authority from a source that is never named |
| participial-tail | a finished sentence with a decorative clause bolted on |
| glyph-tell | em dash, en dash, smart quote, ellipsis character, invisible space |

## FORBIDDEN. Everything in this section is banned, and appears here only as the ban.

Do not copy these. They are the only place in this file where they are allowed to appear, and
running the checker over this file must report findings in this section and nowhere else.

- Here's the catch, the thing, the trick, the kicker. Also the part worth knowing.
- What nobody knew. What most people miss. What vendors don't tell you.
- The hard part. The tricky part. This is where it gets interesting.
- The result? Now what? Why? followed immediately by your own answer.
- In conclusion, or to summarize, or all in all, in place of the summary itself.
- The key insight, or the key takeaway, in place of the insight.
- Studies show, research suggests, experts agree, with nobody named.
- Let's dive in. Let's unpack this. Sound familiar?
- Supercharge, revolutionize, unleash, usher in, demystify.
- A sentence finished, then a clause bolted on the end, ensuring the reader gets one more claim.

## Write this instead

Each of these is the same information with the promise removed.

- Instead of promising a catch: state the exception. "Deadlines set from another step's
  completion shift when that step shifts."
- Instead of framing difficulty: state the constraint. "Recording a step needs Editor access."
- Instead of a question you answer yourself: join the two halves. "External BI tools give you a
  complete picture, because they mix Tallyfy data with your other systems."
- Instead of a summary signpost: write the summary. "Set the deadline first; everything else
  follows from it."
- Instead of vague authority: name the source, or drop the claim. CLAUDE.md already bans
  invented statistics, and an unnamed study is the same failure with the number hidden.
- Instead of a participial tail: make it its own sentence, or cut it. Most of them are an empty
  benefit claim.

Good sentences that people mistake for tells, and which the checker deliberately leaves alone:
"Here's how to create a template." "Here's where to click." A question in a heading. A checklist
of questions put to the reader. A run of questions in one paragraph. `9 - 5` as a range.

## Running it

```bash
python3 scripts/ai-tell-check.py --self-test                    # proves it can go red AND green
python3 scripts/ai-tell-check.py --files path/to/article.mdx    # one article, while writing
python3 scripts/ai-tell-check.py --files path/to/article.mdx --strict   # WARN blocks too
python3 scripts/ai-tell-check.py --dir src/content/docs         # the whole corpus, as CI runs it
```

Exit 0 clean, 1 findings, **2 the checker itself could not run**. "I found no problems" and "I
could not look" never share an exit code.

## The baseline, and why it can only shrink

`.github/ai-tells-baseline.txt` records the 50 findings that already existed in 19 of 505 files
when the gate was switched on, so a regression guard could start guarding without first
rewriting other people's articles. Every line in it is real and should be fixed. Fix the
sentence, then delete the line: an entry that no longer matches anything is a hard failure, so
the file cannot become a permanent allowlist.

## Adding a rule

Add a line to `.github/ai-tells.txt`, a fixture to `FIXTURES` in the checker, and the id to
`REQUIRED_RULE_IDS`. All three are enforced: a rule with no fixture is a hard failure, because
nothing would prove it can fire. Then measure it against all 505 articles before you commit. A
rule that fires on a large share of the corpus gets the whole gate switched off, so tuning it
down is part of writing it, not a follow-up.
