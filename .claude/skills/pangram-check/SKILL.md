---
name: pangram-check
description: Scans a finished blog post, article or docs page with Pangram, the AI-text detector, and rewrites only the passages it flags. Use after drafting or editing and before it ships, when asked for a Pangram or AI-detection check, or when text still sounds machine-written after this repo's own voice checks pass. Needs a browser already signed in to pangram.com.
---

# Pangram check

Pangram reads a piece of text and says how much of it looks AI-written. This skill runs that check on a piece before it ships and fixes what it flags. It comes after this repo's own voice checks, which are free. Pangram costs credits.

## Before you start

- You need a browser signed in to pangram.com. Codex reaches Chrome through its Chrome extension or its `chrome` MCP server; Claude Code uses Claude in Chrome. If the dashboard asks you to log in, stop and say so. Do not try to sign in. It never logs in.
- This repo's free checks pass first (see "Where content lives here" at the end). Pangram is for what those checks cannot see.
- Only send text meant for publication. Never paste customer or client names that are not already public, internal notes, private material quoted in a draft, or anything that looks like a credential.

## Limits

From Pangram's knowledge hub, last reviewed 2026-07-24. If a number looks wrong, the dashboard is the authority.

- At least 50 words per scan. Below that there is not enough signal for a result.
- At most 18,725 words per scan through the dashboard.
- Credits: 1 per 100 words, rounded up for each scan, so a 101-word scan costs 2. The free plan gives 20 credits a day.

Scan a whole piece once. Five 120-word scans cost 10 credits, while one 600-word scan costs 6.

## Steps

1. Prepare the text a reader sees. Remove frontmatter, import lines, components and their props, code blocks, tables, image markup and link URLs (keep the link text). Keep headings as plain lines and list items as sentences. Count the words.
2. Open https://www.pangram.com/dashboard, choose New Check, paste the text and click Check for AI.
3. Confirm the result belongs to this text: the result view shows the start of what you pasted, and a new entry appears in the scan history. If either is missing, report "could not measure" and stop. Reading a stale result from an earlier scan is the mistake to guard against here.
4. Write down what Pangram shows, word for word: the overall label, the AI percentage, and every highlighted segment with its color (red for AI-generated, yellow for AI-assisted, green for human). Copy the label as Pangram words it. Its labels change between versions, so never map them onto your own pass or fail.
5. If the label says human and nothing is highlighted red or yellow, go to step 8.
6. Rewrite only the highlighted passages until it reads as human-written, following this repo's voice rules. Make the changes a person would make:
   - change the sentence structure and the order of ideas, not single words (swapping synonyms makes the prose worse);
   - add a real specific from the source material, such as a named step, a number you can cite, or a concrete example from the product;
   - cut a sentence that only restates the one before it.

   Never invent a fact, quote, number, customer or story to make text sound human. The repo's no-fabrication rule outranks this skill.

7. Scan the whole piece again (steps 1 to 4). Stop after two rewrite rounds. If passages are still flagged, hand them to a person with the result.
8. Record the result where the change is recorded, in the commit message or PR body, in this form:

   `Pangram: <label>, <AI %>, <word count> words, <UTC time>, round <n>`

   Never claim a result you did not see on screen.

## When something goes wrong

- Signed out, out of credits, or the page will not load: stop and say which. Never put another detector's verdict in its place and call it a Pangram result.
- Under 50 words: say so and skip the scan. Do not pad the text.
- Pangram flags a passage that quotes a real source word for word: leave the quote as it is and say so in the report.

## Later

Pangram also has an API that handles long documents by splitting them. This version of the skill does not use the Pangram API.

## Where content lives here

- Pages are in `src/content/docs/` (.mdx). Leave out the `## Related articles` section and every `<CardGrid>` when you prepare the text, because the pipeline regenerates them. Keep footnotes and the "For your IT team", "For developers" and "Technical details" sections, since readers see them.
- The voice rules are `DOCS-VOICE.md` and "Write for business readers, not engineers" in `CLAUDE.md`.
- Free checks, in this order:
  - `python3 scripts/ai-tell-check.py --files <path> --strict` (exit 0 clean, 1 findings, 2 could not run, which is never clean);
  - `python3 scripts/simplicity-check.py --files <path> --report`, which must score below 45.
- Developer reference pages under `pro/integrations/open-api/` and `pro/integrations/webhooks/` are written for developers. Scan them only when asked.
