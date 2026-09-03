#!/usr/bin/env python3
"""Block AI rhetorical tells in Tallyfy documentation prose.

WHY THIS EXISTS (tallyfy/documentation#191)

The only voice rule this repo had was a 26 word blacklist in CLAUDE.md. Measured across all
505 eligible articles on 2026-09-03, ALL 26 measure ZERO in the prose a reader sees. (One raw
file carries "stakeholders", inside a fenced example block that no reader-facing check reads.)
The rule was fully satisfied and could catch nothing at all. Control on the same sweep: 258
files contain "template", so the probe was not blind.

Meanwhile the owner named three phrasings he never wants to read: "This is the part worth
knowing before you build", "the hard part", "what nobody knew". None of them contains a banned
word, so no word list could ever have caught them. What he objects to is a MOVE, not a
vocabulary item: a sentence that promises significance and defers the fact.

So this checks SHAPES. The classes are listed in DOCS-VOICE.md and the rules themselves live in
.github/ai-tells.txt, as data, so they can be reviewed in a diff.

TWO STRUCTURAL DECISIONS, BOTH DELIBERATE

1. IT BLOCKS, IT NEVER REWRITES. This is a deliberate break from
   scripts/generate-related-articles.py, which silently maps "comprehensive" to "complete" via
   BLACKLIST_REPLACEMENTS. A sanitizer is right for the machine-generated card text that script
   owns, and wrong for article bodies: the author never learns, so the next article repeats it.
   A blocked build teaches. A silent rewrite does not.

2. THE `## Related articles` BLOCK AND EVERY <CardGrid> ARE SKIPPED. Those regenerate from the
   Tallyfy Answers recommendation API on every pipeline run, so a finding there is one a human
   cannot fix and CI would overwrite anyway. The exclusion is PRINTED on every run rather than
   applied silently, because an exclusion nobody can see is indistinguishable from a rule that
   does not work.

MODES

  --self-test     Prove the checker goes RED and GREEN, per rule. Runs on every CI invocation,
                  so the ability to fail is asserted rather than assumed. A positive-only self
                  test is passed by a gate that refuses everything (syncing-scripts#583, where a
                  bare `\\w+ing` participle rule flagged "billing", "pricing" and "onboarding"
                  in 288 files while catching 0 of the 7 phrases it was written for).
  --check-wiring  Prove the gate still blocks the publishing job. A red gate that does not stop
                  the publish is decoration.
  (default)       Scan the corpus, or --files.

EXIT CODES
  0  clean (no ERROR findings; WARN findings do not block unless --strict)
  1  findings
  2  the checker could not run - a broken checker is NEVER read as a pass

"I found no problems" and "I could not look" must never share an exit code.
"""

import argparse
import os
import re
import sys

# ---------------------------------------------------------------------------------------
# corpus definition - mirrors scripts/simplicity-check.py exactly, so the two scan the same
# 505 files and a count from one can be compared against the other.

SKIP_FILES = ["404.mdx"]
SKIP_DIRS = ["src/content/docs/pro/changelog", "src/content/docs/changelog"]
EXCLUDE_FROM_SCAN = ["open-api/code-samples", "open-api/api-clients"]

DEFAULT_RULES = ".github/ai-tells.txt"
DEFAULT_BASELINE = ".github/ai-tells-baseline.txt"
DEFAULT_DIR = "src/content/docs"
DEFAULT_WORKFLOW = ".github/workflows/documentation-pipeline.yml"

# A masked character. Deliberately NOT a space: a space is matched by `\s`, so a regex like
# `\bnot\s+just\b` could match ACROSS a blanked code block and report a phrase nobody wrote.
# NUL matches neither `\s` nor `\w`, so every regex rule is confined to real prose. Newlines
# are preserved through masking so reported line numbers stay identical to the raw file.
FILLER = "\x00"

SEVERITIES = ("ERROR", "WARN")
SCOPES = ("prose", "description", "both")

# The taxonomy. A rule naming a class not in this set is fatal, so a typo cannot quietly
# create a category nobody reviews. Documented in DOCS-VOICE.md.
CLASSES = (
    "manufactured-revelation",
    "difficulty-framing",
    "manufactured-exclusivity",
    "self-answered-question",
    "false-contrast",
    "false-intimacy",
    "conclusion-signposting",
    "inflation-verb",
    "vague-attribution",
    "participial-tail",
    "glyph-tell",
)

RULE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MIN_NAME_CHARS = 12

# The rule inventory lock. Every id here MUST be present in the rules file or the checker
# exits 2. Without it, DELETING a rule shrinks the expected set and the self-test passes
# happily for a rule that no longer exists - a gate quietly getting weaker with every run
# still green. Adding a rule is fine and only needs a fixture; removing one is a code change
# with an author and a diff.
REQUIRED_RULE_IDS = frozenset({
    "revelation-heres-the",
    "revelation-part-worth",
    "revelation-what-nobody",
    "revelation-turns-out",
    "difficulty-hard-part",
    "difficulty-where-it-gets",
    "exclusivity-most-people-dont",
    "exclusivity-what-they-dont-tell",
    "exclusivity-few-realize",
    "question-self-answered",
    "contrast-not-just-but",
    "contrast-isnt-about",
    "intimacy-lets-verb",
    "intimacy-sound-familiar",
    "intimacy-you-might-think",
    "conclusion-signpost",
    "conclusion-key-takeaway",
    "inflation-verb-hard",
    "inflation-verb-soft",
    "vague-attribution",
    "participial-tail",
    "glyph-dash",
    "glyph-quote",
    "glyph-invisible",
})


class CheckerError(Exception):
    """The checker could not answer. Never treated as a pass."""


def log(msg=""):
    print(msg, flush=True)


def annotate(level, msg):
    """GitHub Actions annotation, so a failure shows in the run summary and not only in logs."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


# ---------------------------------------------------------------------------------------
# rule data


class Rule:
    __slots__ = ("id", "cls", "severity", "scope", "pattern", "name", "line_no", "regex", "builtin")

    def __init__(self, rid, cls, severity, scope, pattern, name, line_no):
        self.id = rid
        self.cls = cls
        self.severity = severity
        self.scope = scope
        self.pattern = pattern
        self.name = name
        self.line_no = line_no
        self.builtin = pattern[len("builtin:"):] if pattern.startswith("builtin:") else None
        self.regex = None
        if self.builtin is None:
            try:
                self.regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise CheckerError(f"rule {rid!r}: pattern does not compile: {exc}")
            # A pattern that can match the empty string produces one finding per character.
            # Cheap to check here, and impossible to diagnose from the output.
            if self.regex.search(""):
                raise CheckerError(
                    f"rule {rid!r}: pattern matches the empty string, so it would fire at every "
                    f"offset in every file"
                )


def parse_rules(path):
    """Parse the rule list. Any malformed line is FATAL, never a skipped line.

    A rule that silently fails to parse is exactly the gate-that-cannot-fire this whole
    mechanism exists to prevent, so there is no lenient path here. A missing file is fatal
    too, so the mechanism cannot be removed quietly.
    """
    if not os.path.isfile(path):
        raise CheckerError(
            f"rule list not found at {path}. The list is required even when it holds nothing - "
            f"a missing list must be loud, not silently permissive."
        )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise CheckerError(f"cannot read rule list at {path}: {exc}")

    rules, seen = [], {}
    for line_no, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Six pipe-separated fields, but the PATTERN field is a regex and `|` is regex
        # alternation - which is the single most natural thing to write in one. So the first
        # four fields are taken from the LEFT and the name from the RIGHT, and whatever is
        # between them is the pattern, pipes and all. A plain `split("|")` would reject every
        # alternation, and the fix people reach for then is to weaken the rule rather than to
        # escape it. The one cost is that `name` may not contain a pipe, which is checked.
        if stripped.count("|") < 5:
            raise CheckerError(
                f"{path}:{line_no}: expected six pipe-separated fields "
                f"'id | class | severity | scope | pattern | name', found "
                f"{stripped.count('|')} separator(s): {stripped!r}"
            )
        head, name = stripped.rsplit("|", 1)
        name = name.strip()
        fields = head.split("|", 4)
        rid, cls, severity, scope, pattern = (f.strip() for f in fields)
        if not RULE_ID_RE.match(rid):
            raise CheckerError(
                f"{path}:{line_no}: id {rid!r} must be lowercase letters, digits and hyphens"
            )
        if rid in seen:
            raise CheckerError(
                f"{path}:{line_no}: duplicate id {rid!r}, already defined on line {seen[rid]}. "
                f"Ids name a rule in the lock and in every report, so they must be unique."
            )
        if cls not in CLASSES:
            raise CheckerError(
                f"{path}:{line_no}: rule {rid!r} has class {cls!r}, which is not one of "
                f"{', '.join(CLASSES)}. A typo here would create a category nobody reviews."
            )
        if severity not in SEVERITIES:
            raise CheckerError(
                f"{path}:{line_no}: rule {rid!r} has severity {severity!r}, expected one of "
                f"{', '.join(SEVERITIES)}"
            )
        if scope not in SCOPES:
            raise CheckerError(
                f"{path}:{line_no}: rule {rid!r} has scope {scope!r}, expected one of "
                f"{', '.join(SCOPES)}"
            )
        if not pattern:
            raise CheckerError(f"{path}:{line_no}: rule {rid!r} has an empty pattern")
        if len(name) < MIN_NAME_CHARS:
            raise CheckerError(
                f"{path}:{line_no}: rule {rid!r} needs a real name beside it saying what the "
                f"move is (at least {MIN_NAME_CHARS} characters), got {name!r}"
            )
        seen[rid] = line_no
        rules.append(Rule(rid, cls, severity, scope, pattern, name, line_no))

    if not rules:
        raise CheckerError(
            f"{path} defines zero rules. A scan with no rules passes every assertion made about "
            f"it and proves nothing."
        )

    ids = {r.id for r in rules}
    missing = sorted(REQUIRED_RULE_IDS - ids)
    if missing:
        raise CheckerError(
            f"{path} is missing rule id(s) that are locked in REQUIRED_RULE_IDS: "
            f"{', '.join(missing)}. Deleting a rule from the data file must be a deliberate "
            f"code change, not a quiet edit - otherwise the self-test keeps passing for a rule "
            f"that no longer exists."
        )
    for rule in rules:
        if rule.builtin is not None and rule.builtin not in BUILTINS:
            raise CheckerError(
                f"{path}:{rule.line_no}: rule {rule.id!r} names builtin {rule.builtin!r}, which "
                f"has no implementation. Known builtins: {', '.join(sorted(BUILTINS))}"
            )
        if rule.id not in FIXTURES:
            raise CheckerError(
                f"{path}:{rule.line_no}: rule {rule.id!r} has no fixture in FIXTURES, so nothing "
                f"proves it can fire. Add one line of text that must trip it."
            )
    unlocked = sorted(ids - REQUIRED_RULE_IDS)
    if unlocked:
        log(
            f"NOTE: {len(unlocked)} rule(s) not yet in REQUIRED_RULE_IDS: "
            f"{', '.join(unlocked)}. Add them there so deleting one is loud."
        )
    return rules


# ---------------------------------------------------------------------------------------
# the baseline: what was already here when the gate was built
#
# This is a REGRESSION GUARD on an editing job about to touch hundreds of articles, not a
# cleanup of a backlog (tallyfy/documentation#191). The corpus is nearly clean - 4.2% of files
# carried an ERROR finding when this was written - but "nearly" is not "entirely", and a gate
# that is red on day one blocks `sync`, which means nothing publishes at all. So the findings
# that already existed are recorded here, by hand, and everything NEW is blocked.
#
# Three properties stop this becoming a dumping ground:
#
#   1. It is COUNT-AWARE. An entry suppresses exactly one occurrence. A file that gains a
#      second instance of the same sentence still fails.
#   2. A STALE ENTRY IS FATAL. When someone fixes a baselined sentence, the entry stops
#      matching and the checker exits 2 until the line is deleted. So the file can only shrink,
#      and it shrinks with an author and a date on the diff.
#   3. It is keyed on the MATCHED TEXT, not a line number. Line numbers churn on every edit, so
#      a line-keyed baseline goes stale for reasons that have nothing to do with the prose.
#
# A MISSING baseline file is NOT fatal, unlike the rule list. The asymmetry is deliberate and it
# is the safe direction: with no baseline, nothing is suppressed and the gate is STRICTER. A
# missing rule list would make it weaker, which is why that one is fatal.

BASELINE_HEADER = """# AI rhetorical tells - the baseline
#
# Findings that already existed when the gate was built (tallyfy/documentation#191), so a
# regression guard could be switched on without first rewriting other people's articles.
# EVERY LINE HERE IS A REAL FINDING THAT SHOULD BE FIXED. Nothing here is a false positive;
# the false positives were tuned out of the rules instead.
#
# Format - three pipe-separated fields, the text taken last so it may contain pipes:
#
#   <path> | <rule id> | <the exact matched text>
#
# One line suppresses ONE occurrence. Two identical lines suppress two.
#
# TO REMOVE A LINE: fix the sentence, then delete the line. You do not get a choice about the
# second half - a baseline entry that no longer matches anything is a HARD FAILURE (exit 2),
# so this file can only ever shrink.
"""


def parse_baseline(path):
    """Return {(path, rule_id, text): count}. A missing file means an empty baseline."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise CheckerError(f"cannot read baseline at {path}: {exc}")
    out = {}
    for line_no, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.count("|") < 2:
            raise CheckerError(
                f"{path}:{line_no}: expected three pipe-separated fields "
                f"'<path> | <rule id> | <matched text>', got {stripped!r}"
            )
        first, second, text = stripped.split("|", 2)
        key = (first.strip(), second.strip(), text.strip())
        if not key[0] or not key[1] or not key[2]:
            raise CheckerError(f"{path}:{line_no}: a field is empty: {stripped!r}")
        out[key] = out.get(key, 0) + 1
    return out


def apply_baseline(findings, baseline, baseline_path, enforce_stale=True):
    """Suppress baselined findings. A stale entry is fatal, so the file can only shrink.

    `enforce_stale` is False for a partial scan (`--files`). The staleness check compares the
    whole baseline against everything found, so over a two-file scan every entry for the other
    503 files looks stale and the checker would exit 2 on a run that is working perfectly. That
    is the "a probe over a subset answering about the whole" defect, and it would have made the
    local authoring command unusable.
    """
    if not baseline:
        return findings, 0
    seen = {}
    kept = []
    for f in findings:
        key = (f.path.replace(os.sep, "/"), f.rule.id, f.text.replace(FILLER, "").strip())
        allowed = baseline.get(key, 0)
        used = seen.get(key, 0)
        if used < allowed:
            seen[key] = used + 1
            continue
        kept.append(f)
    stale = [(k, n - seen.get(k, 0)) for k, n in baseline.items() if seen.get(k, 0) < n]
    if stale and enforce_stale:
        lines = "\n".join(
            f"  {n} unmatched: {k[0]} | {k[1]} | {k[2]}" for k, n in sorted(stale)
        )
        raise CheckerError(
            f"{baseline_path} has {len(stale)} stale entr(y/ies) matching nothing in the "
            f"corpus:\n{lines}\n"
            f"If you fixed the sentence, delete the line. This is fatal on purpose: it is what "
            f"stops the baseline from becoming a permanent allowlist."
        )
    return kept, sum(baseline.values())


def check_baseline_rule_ids(baseline, rules, baseline_path):
    known = {r.id for r in rules}
    unknown = sorted({k[1] for k in baseline} - known)
    if unknown:
        raise CheckerError(
            f"{baseline_path} names rule id(s) that do not exist: {', '.join(unknown)}. A "
            f"baseline entry against a deleted rule suppresses nothing and hides that the rule "
            f"is gone."
        )


# ---------------------------------------------------------------------------------------
# masking: turn a raw .mdx file into prose, WITHOUT moving a single byte
#
# Every stripped region is overwritten with FILLER of EQUAL LENGTH and newlines are preserved,
# so an offset in the masked text is the same offset in the file on disk and a reported line
# number is real. Deleting the regions instead would shift every line below them, and a gate
# that points at the wrong line is one people stop reading.

FENCE_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[^\n]*\n.*?^\1?\2[^\n]*$", re.S | re.M)
FENCE_OPEN_RE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})", re.M)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
MDX_COMMENT_RE = re.compile(r"\{/\*.*?\*/\}", re.S)
IMPORT_EXPORT_RE = re.compile(r"^[ \t]*(?:import|export)\b[^\n]*(?:\n[ \t]+[^\n]*)*", re.M)
HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+[^\n]*$", re.M)
TABLE_ROW_RE = re.compile(r"^[ \t]*\|[^\n]*$", re.M)
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)*?\1", re.S)
IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
LINK_RE = re.compile(r"(\[[^\]\n]*\])(\([^)\n]*\))")
BARE_URL_RE = re.compile(r"<?https?://[^\s<>)\"']+>?")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]\n]+\](?!:)")

# A JSX/MDX tag, with QUOTED ATTRIBUTE VALUES understood. The naive `<\/?[A-Za-z][^>]*>`
# stops at the first `>` it meets, and inside
#   <LinkTitleCard header="<b>Tasks > Step types</b>" href="/x/" >
# that `>` is the one inside the attribute, so the rest of the card text leaks into prose and
# gets scanned as if a human wrote it. 2,044 LinkTitleCard tags in this corpus carry exactly
# that shape.
_JSX_ATTR = (
    r"""(?:\s+[A-Za-z_:][-\w:.]*(?:\s*=\s*"""
    r"""(?:"[^"]*"|'[^']*'|\{(?:[^{}]|\{[^{}]*\})*\}|[^\s"'>`]+))?)*"""
)
JSX_TAG_RE = re.compile(r"</?[A-Za-z][-\w.:]*" + _JSX_ATTR + r"\s*/?>")

# Machine-generated recommendation blocks. Regenerated from the Answers API on every pipeline
# run, so a finding inside one is a finding a human cannot fix.
CARDGRID_RE = re.compile(r"<CardGrid\b[^>]*>.*?</CardGrid>", re.S | re.I)
LINKCARD_RE = re.compile(r"<LinkTitleCard\b" + _JSX_ATTR + r"\s*>.*?</LinkTitleCard>", re.S | re.I)
RELATED_HEADING_RE = re.compile(r"^[ \t]{0,3}##[ \t]+Related articles[ \t]*$", re.M | re.I)
NEXT_H2_RE = re.compile(r"^[ \t]{0,3}##[ \t]+", re.M)


class Stream:
    """One masked view of a file: same length as the raw bytes, non-prose blanked out."""

    def __init__(self, raw, start_masked):
        self.raw = raw
        self.chars = [FILLER if (start_masked and c != "\n") else c for c in raw]
        self.masked = [start_masked] * len(raw)

    def blank(self, start, end):
        for i in range(max(0, start), min(end, len(self.raw))):
            self.masked[i] = True
            if self.raw[i] != "\n":
                self.chars[i] = FILLER

    def keep(self, start, end):
        for i in range(max(0, start), min(end, len(self.raw))):
            self.masked[i] = False
            self.chars[i] = self.raw[i]

    def text(self):
        return "".join(self.chars)

    def span_is_clean(self, start, end):
        return not any(self.masked[i] for i in range(max(0, start), min(end, len(self.raw))))


def frontmatter_span(raw):
    """(start, end) of the frontmatter block including both `---` fences, or None."""
    if not raw.startswith("---"):
        return None
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", raw, re.S)
    if not m:
        return None
    return (0, m.end())


def description_span(raw):
    """(start, end) of the frontmatter `description:` VALUE, or None.

    The description ships to search results and to Tallyfy Answers, so it is prose a reader
    sees and it is checked. Everything else in the frontmatter is metadata and is not.
    Folded values that continue onto indented lines are included whole.
    """
    fm = frontmatter_span(raw)
    if not fm:
        return None
    body = raw[:fm[1]]
    m = re.search(r"^description:[ \t]*", body, re.M)
    if not m:
        return None
    start = m.end()
    # Skip a YAML block-scalar indicator so `>-` / `|2` never reads as prose. Only when the
    # value actually OPENS with one: a description may legitimately begin with a digit
    # ("500 users can share one template"), and skipping digits unconditionally would eat it.
    if start < len(body) and body[start] in ">|":
        start += 1
        while start < len(body) and body[start] in "-+0123456789":
            start += 1
    line_end = body.find("\n", start)
    if line_end == -1:
        return (start, len(body))
    end = line_end
    for line_m in re.finditer(r"^[^\n]*$", body[line_end + 1:], re.M):
        line = line_m.group(0)
        abs_start = line_end + 1 + line_m.start()
        if abs_start >= len(body):
            break
        if line.strip() == "---":
            break
        if line and not line[0].isspace():
            break
        end = abs_start + len(line)
        if not line.strip():
            break
    return (start, end)


def build_streams(raw):
    """Return (prose, description, heading_spans).

    prose and description are Streams over the same raw text, disjoint, each the same length
    as the file.
    """
    prose = Stream(raw, start_masked=False)

    fm = frontmatter_span(raw)
    if fm:
        prose.blank(*fm)

    for regex in (HTML_COMMENT_RE, MDX_COMMENT_RE):
        for m in regex.finditer(raw):
            prose.blank(m.start(), m.end())

    for m in FENCE_RE.finditer(raw):
        prose.blank(m.start(), m.end())
    # An UNTERMINATED fence would otherwise leak a whole code block into prose. Checked against
    # what is still unmasked, not `if no closed fence exists`: a file can carry a closed fence
    # and then an unclosed one, and the simpler test misses exactly that case. Blank to EOF -
    # over-blanking loses a finding, under-blanking INVENTS one, and inventing is the expensive
    # direction for a gate people have to be willing to keep.
    for m in FENCE_OPEN_RE.finditer(raw):
        if not prose.masked[m.start()]:
            prose.blank(m.start(), len(raw))
            break

    for m in IMPORT_EXPORT_RE.finditer(raw):
        prose.blank(m.start(), m.end())

    # Machine-generated regions, before tag stripping (the region detection needs the tags).
    for regex in (CARDGRID_RE, LINKCARD_RE):
        for m in regex.finditer(raw):
            prose.blank(m.start(), m.end())
    m = RELATED_HEADING_RE.search(raw)
    if m:
        nxt = NEXT_H2_RE.search(raw, m.end())
        prose.blank(m.start(), nxt.start() if nxt else len(raw))

    for m in JSX_TAG_RE.finditer(raw):
        prose.blank(m.start(), m.end())

    for m in INLINE_CODE_RE.finditer(raw):
        prose.blank(m.start(), m.end())

    for m in IMAGE_RE.finditer(raw):
        prose.blank(m.start(), m.end())
    for m in LINK_RE.finditer(raw):
        prose.blank(m.start(1), m.start(1) + 1)          # the opening [
        prose.blank(m.end(1) - 1, m.end(1))              # the closing ]
        prose.blank(m.start(2), m.end(2))                # the (url)
    for m in BARE_URL_RE.finditer(raw):
        prose.blank(m.start(), m.end())
    for m in FOOTNOTE_REF_RE.finditer(raw):
        prose.blank(m.start(), m.end())

    for m in TABLE_ROW_RE.finditer(raw):
        prose.blank(m.start(), m.end())

    desc = Stream(raw, start_masked=True)
    span = description_span(raw)
    if span and span[1] > span[0]:
        desc.keep(*span)

    heading_spans = [(m.start(), m.end()) for m in HEADING_RE.finditer(raw)]
    return prose, desc, heading_spans


class Doc:
    def __init__(self, path, raw):
        self.path = path
        self.raw = raw
        self.prose, self.desc, self.heading_spans = build_streams(raw)
        self._line_starts = [0] + [m.end() for m in re.finditer(r"\n", raw)]
        self._both = None

    def line_of(self, offset):
        lo, hi = 0, len(self._line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def stream(self, scope):
        if scope == "prose":
            return self.prose
        if scope == "description":
            return self.desc
        if self._both is None:
            merged = Stream(self.raw, start_masked=True)
            for i, ch in enumerate(self.raw):
                if not self.prose.masked[i] or not self.desc.masked[i]:
                    merged.masked[i] = False
                    merged.chars[i] = ch
            self._both = merged
        return self._both

    def in_heading(self, start, end):
        return any(hs <= start and end <= he for hs, he in self.heading_spans)


# ---------------------------------------------------------------------------------------
# builtin rules: the shapes a single regex cannot express


def _clean_text(stream):
    """The masked stream with FILLER as spaces, so sentence splitting reads normally.

    Offsets are preserved, and every builtin still asserts its MATCH span is unmasked before
    reporting, so nothing that came out of a code block or a card can be attributed to a human.
    """
    return stream.text().replace(FILLER, " ")


SENTENCE_END_RE = re.compile(r"[.!?]+[\"')\]]*(?=\s|$)")

# The rhetorical-question openers. A question in an H2 or H3 is legitimate documentation
# structure - this repo's articles are built out of them ("What are tasks in Tallyfy?") - so
# headings are exempt and only BODY prose is looked at. Even in body prose, a plain question
# followed by an answer is normal teaching. What is banned is the manufactured one: a question
# the writer asks himself purely to answer it in the next breath.
RHETORICAL_Q_RE = re.compile(
    r"(?:^|(?<=[.!?\"')\s]))("
    r"(?:so\s+)?(?:why|what|how)\s+(?:does|do|is|are|would|should|might)\s+(?:this|that|it|any\s+of\s+this)\b[^?\n]{0,60}\?"
    r"|the\s+(?:result|upshot|catch|answer|difference|problem|reason|point|fix|effect|payoff|kicker)\s*\?"
    r"|(?:so\s+)?(?:why|what)\s+(?:not|then|now|next)\s*\?"
    r"|(?:but\s+)?(?:why|what|how)\s*\?"
    r"|sounds?\s+familiar\s*\?"
    r"|(?:so\s+)?what\s+(?:gives|now|then)\s*\?"
    r"|the\s+(?:short|honest|real)\s+answer\s*\?"
    r")",
    re.IGNORECASE,
)

MIN_ANSWER_CHARS = 12
QUOTE_OPEN = "\"'*“‘"
QUOTE_CLOSE = "\"'*”’"
LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")
# Three or more questions in one paragraph is a CHECKLIST of questions put to the reader
# ("What to collect? Why? How? When? Who's responsible?"), not one question the writer asks
# himself. Two is deliberately still in scope: the Zapier article's "A deal closes in your CRM -
# then what? Zapier fires a trigger ... without 'what's the status?' emails" is a real tell in a
# paragraph carrying two question marks, and a threshold of 2 would let it through.
QUESTION_RUN_MIN = 3


def _paragraph_bounds(text, offset):
    """The blank-line-delimited block containing `offset`."""
    start = 0
    for m in re.finditer(r"\n[ \t]*\n", text[:offset]):
        start = m.end()
    m = re.search(r"\n[ \t]*\n", text[offset:])
    return start, offset + m.start() if m else len(text)


def builtin_self_answered_question(doc, rule):
    """A rhetorical question in BODY prose that the writer immediately answers himself.

    Naive "any `?` in prose" hits 327 of 505 files here, because this repo teaches through
    question headings and puts genuine questions to the reader. A gate firing on two thirds of
    the corpus gets switched off in a week. Five narrowings, each measured on the real corpus:

      1. HEADINGS ARE EXEMPT. "### Why do tasks matter?" is documentation structure.
      2. The question must match a RHETORICAL opener - one the writer is asking on the reader's
         behalf, not one asking the reader to do or decide anything.
      3. Something must FOLLOW it. A question that ends a section is an invitation; a question
         answered in the next clause is the tell.
      4. A QUOTED OR EMPHASISED question is an example, not the writer's own move. The 5 Whys
         article says `keep asking "Why?"` and writes `*Why?*` five times; that is the name of
         the technique, and it was four of this rule's twelve false positives.
      5. A QUESTION RUN (three or more in one paragraph) is a checklist, and a question inside
         a LIST ITEM is a prompt to the reader. Both were false positives here, and neither
         produced a single true positive on the whole corpus.

    Tuned from 21 findings in 13 files, of which 12 were false positives, down to 9 findings in
    9 files with none. That the exemptions cost no true positive is itself measured, not assumed.
    """
    stream = doc.stream(rule.scope)
    text = _clean_text(stream)
    out = []
    for m in RHETORICAL_Q_RE.finditer(text):
        start, end = m.start(1), m.end(1)
        if not stream.span_is_clean(start, end):
            continue
        if doc.in_heading(start, end):
            continue
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        if before in QUOTE_OPEN and after in QUOTE_CLOSE:
            continue
        para_start, para_end = _paragraph_bounds(text, start)
        if text.count("?", para_start, para_end) >= QUESTION_RUN_MIN:
            continue
        first_line = text[para_start:text.find("\n", para_start) if "\n" in text[para_start:para_end] else para_end]
        if LIST_ITEM_RE.match(first_line):
            continue
        line_start = text.rfind("\n", 0, start) + 1
        if LIST_ITEM_RE.match(text[line_start:start]):
            continue
        tail = text[end:end + 400]
        # The answer: real words after the question mark, before the section ends. A blank line
        # is fine (the answer often starts a new paragraph); a heading is not.
        answer = re.split(r"\n[ \t]{0,3}#{1,6}[ \t]", tail)[0]
        if len(answer.strip()) < MIN_ANSWER_CHARS:
            continue
        out.append((start, end, text[start:end].strip()))
    return out


# Present participles that carry the tell. An ALLOWLIST, never a bare `\w+ing` suffix match.
#
# Measured on this corpus 2026-09-03: `,\s+\w+ing` matches 432 times across 221 of 505 files
# (43.8%), and the top of that list is `including` (30), `pricing` (10), `billing` (5),
# `onboarding` (5), `nothing` (6), `during` (4) and `everything` (3) - four of which are not
# even verbs. That is the syncing-scripts#583 defect exactly: the same spelling flagged
# billing, pricing and onboarding across 288 files there while catching 0 of the 7 phrases it
# was written for.
#
# Missing a novel tell is the cheap failure. Blocking correct writing is the expensive one,
# because that is what teaches people to switch the gate off.
#
# `helping` and `driving` are deliberately absent, following the same call in
# syncing-scripts' voice_check.py: they carry almost no tell value and appear in ordinary
# documentation English.
PARTICIPLE_TELLS = frozenset({
    "emphasizing", "emphasising", "showcasing", "highlighting", "underscoring",
    "demonstrating", "illustrating", "reinforcing", "leveraging", "facilitating",
    "empowering", "streamlining", "unlocking", "fostering", "maximizing", "maximising",
    "optimizing", "optimising", "revolutionizing", "revolutionising", "transforming",
    "ushering", "spearheading", "harnessing", "elevating", "cementing", "solidifying",
    "ensuring", "enabling", "delivering", "providing", "eliminating", "boosting",
})

PARTICIPIAL_TAIL_RE = re.compile(r",\s+([a-z]+ing)\b", re.IGNORECASE)
# A finite verb immediately after means the participle is a gerund subject
# ("Ensuring accuracy takes time"), not a tail bolted onto a finished sentence.
FINITE_AFTER_RE = re.compile(
    r"^\s+(?:is|are|was|were|takes?|means?|requires?|helps?|matters?|works?|remains?)\b", re.I
)
# A sentence that OPENS with a fronted adjunct - "For employees who aren't Hebrew-proficient,
# providing Arabic versions is best practice" - has its first comma separating that adjunct
# from the MAIN clause, so what follows is the subject, not a decorative tail. Without this,
# that real sentence in azure-translation/global-workplace-language-requirements.mdx is the
# rule's only false positive on the whole corpus.
FRONTED_OPENER_RE = re.compile(
    r"^\s*(?:for|when|if|after|before|while|once|since|although|though|because|in|on|at|with|"
    r"without|to|by|as|unless|instead|rather|given|depending|during|from|under|over|despite|"
    r"whether|until|by)\b",
    re.I,
)
SENTENCE_START_RE = re.compile(r"(?:^|[.!?]\s+|\n\s*\n|\n\s*[-*+]\s+|\n\s*\d+[.)]\s+)")


def builtin_participial_tail(doc, rule):
    """A sentence finished, then a decorative `, ...ing ...` clause bolted on the end."""
    stream = doc.stream(rule.scope)
    text = _clean_text(stream)
    out = []
    for m in PARTICIPIAL_TAIL_RE.finditer(text):
        word = m.group(1).lower()
        if word not in PARTICIPLE_TELLS:
            continue
        if not stream.span_is_clean(m.start(), m.end()):
            continue
        if FINITE_AFTER_RE.match(text[m.end():m.end() + 40]):
            continue
        starts = [s.end() for s in SENTENCE_START_RE.finditer(text, 0, m.start())]
        head = text[starts[-1]:m.start()] if starts else text[:m.start()]
        if "," not in head and FRONTED_OPENER_RE.match(head):
            continue
        tail_end = min(len(text), m.end() + 60)
        snippet = text[m.start():tail_end].split("\n")[0].strip()
        out.append((m.start(), m.end(), snippet))
    return out


# Glyph tells. A NAMED LIST, never a blanket non-ASCII ban: an accented name or a real
# non-English term belongs in the docs, and banning all non-ASCII would refuse it. Four of the
# invisible family are written as \u escapes on purpose - a literal here is a character an
# editor can silently eat and nobody can see go missing.
GLYPHS = {
    "—": "EM DASH", "–": "EN DASH", "‑": "NON-BREAKING HYPHEN",
    "‒": "FIGURE DASH", "―": "HORIZONTAL BAR",
    "‘": "LEFT SINGLE QUOTE", "’": "RIGHT SINGLE QUOTE",
    "“": "LEFT DOUBLE QUOTE", "”": "RIGHT DOUBLE QUOTE",
    "…": "ELLIPSIS CHARACTER",
    " ": "NON-BREAKING SPACE", " ": "NARROW NO-BREAK SPACE",
    " ": "THIN SPACE", "​": "ZERO-WIDTH SPACE", "﻿": "ZERO-WIDTH NO-BREAK SPACE",
}
GLYPH_GROUPS = {
    "dash": "—–‑‒―",
    "quote": "‘’“”…",
    "invisible": "   ​﻿",
}


def _glyph_builtin(group):
    chars = GLYPH_GROUPS[group]

    def run(doc, rule):
        stream = doc.stream(rule.scope)
        text = stream.text()
        out = []
        for i, ch in enumerate(text):
            if ch in chars and not stream.masked[i]:
                out.append((i, i + 1, f"{GLYPHS[ch]} (U+{ord(ch):04X})"))
        return out

    return run


BUILTINS = {
    "self-answered-question": builtin_self_answered_question,
    "participial-tail": builtin_participial_tail,
    "glyph-dash": _glyph_builtin("dash"),
    "glyph-quote": _glyph_builtin("quote"),
    "glyph-invisible": _glyph_builtin("invisible"),
}


# ---------------------------------------------------------------------------------------
# the check


class Finding:
    __slots__ = ("path", "line", "rule", "text")

    def __init__(self, path, line, rule, text):
        self.path = path
        self.line = line
        self.rule = rule
        self.text = text

    def render(self):
        snippet = self.text.replace(FILLER, "").replace("\n", " ").strip()
        snippet = re.sub(r"\s+", " ", snippet)
        if len(snippet) > 90:
            snippet = snippet[:87] + "..."
        return (
            f"{self.path}:{self.line}: {self.rule.severity} "
            f"[{self.rule.id} {self.rule.cls}] {self.rule.name} -> {snippet!r}"
        )


def check_doc(doc, rules):
    findings = []
    for rule in rules:
        if rule.builtin is not None:
            hits = BUILTINS[rule.builtin](doc, rule)
        else:
            stream = doc.stream(rule.scope)
            hits = []
            for m in rule.regex.finditer(stream.text()):
                # CONVENTION: if a pattern has a capture group, group 1 is the tell and the rest
                # is only context needed to anchor it. Reporting group 0 would point the line
                # number at the anchor - a `(?:^|[.!?]\s+)` prefix consumes the newline before
                # the sentence, so the finding would be reported one line early and name the
                # wrong sentence. Measured on the conclusion-signpost rule: line 10 instead of 12.
                start, end = (m.span(1) if m.re.groups else m.span(0))
                if stream.span_is_clean(start, end):
                    hits.append((start, end, m.group(1) if m.re.groups else m.group(0)))
        for start, _end, snippet in hits:
            findings.append(Finding(doc.path, doc.line_of(start), rule, snippet))
    findings.sort(key=lambda f: (f.line, f.rule.id))
    return findings


def discover(root):
    """Every eligible article. Mirrors simplicity-check.py's file set exactly."""
    if not os.path.isdir(root):
        raise CheckerError(f"content directory not found: {root}")
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if not name.endswith(".mdx"):
                continue
            if name in SKIP_FILES:
                continue
            path = os.path.join(dirpath, name)
            norm = path.replace(os.sep, "/")
            if any(skip in norm for skip in SKIP_DIRS):
                continue
            if any(skip in norm for skip in EXCLUDE_FROM_SCAN):
                continue
            out.append(path)
    return sorted(out)


def run(paths, rules, strict=False, quiet=False, baseline_path=None, enforce_stale=True):
    # An input set of zero passes every assertion made about it. A scan over no files is
    # indistinguishable, in its output, from a scan over a clean corpus - so it is exit 2.
    if not paths:
        raise CheckerError(
            "zero files to scan. A scan over an empty input set reports exactly what a clean "
            "corpus reports, so it can never be read as a pass."
        )

    baseline = {}
    if baseline_path:
        baseline = parse_baseline(baseline_path)
        check_baseline_rule_ids(baseline, rules, baseline_path)

    log(f"Rules: {len(rules)} across {len(set(r.cls for r in rules))} class(es).")
    log(f"Files: {len(paths)}.")
    log(
        "Excluded from every file, and said out loud rather than applied silently: the "
        "`## Related articles` section and every <CardGrid> / <LinkTitleCard> block. Those "
        "regenerate from the Answers API on each pipeline run, so a finding inside one is a "
        "finding a human cannot fix and CI would overwrite."
    )
    log("Also excluded: code fences, inline code, JSX tags, imports, comments, image alt, "
        "table rows, link URLs, and all frontmatter except `description:`.")
    log()

    all_findings = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            raise CheckerError(f"cannot read {path}: {exc}")
        except UnicodeDecodeError as exc:
            raise CheckerError(f"{path} is not valid UTF-8, so it cannot be checked: {exc}")
        all_findings.extend(check_doc(Doc(path, raw), rules))

    raw_total = len(all_findings)
    all_findings, baselined = apply_baseline(
        all_findings, baseline, baseline_path, enforce_stale=enforce_stale
    )
    if baseline_path:
        suppressed = raw_total - len(all_findings)
        log(
            f"Baseline {baseline_path}: {baselined} pre-existing finding(s) recorded, "
            f"{suppressed} suppressed here of {raw_total} found"
            + ("" if enforce_stale else " (partial scan: stale entries are not checked)")
            + ". Every line in it is real and should be fixed; deleting the line is how you "
            f"record that you did."
        )
    log()

    errors = [f for f in all_findings if f.rule.severity == "ERROR"]
    warns = [f for f in all_findings if f.rule.severity == "WARN"]

    if not quiet:
        for f in all_findings:
            log(f.render())
            if f.rule.severity == "ERROR":
                annotate("error", f.render())
            else:
                annotate("warning", f.render())
        if all_findings:
            log()

    by_rule = {}
    for f in all_findings:
        by_rule.setdefault(f.rule.id, []).append(f)
    if by_rule:
        log("Per rule:")
        for rid in sorted(by_rule):
            hits = by_rule[rid]
            files = len({h.path for h in hits})
            log(f"  {hits[0].rule.severity:5} {rid:32} {len(hits):4} finding(s) in {files} file(s)")
        log()

    err_files = len({f.path for f in errors})
    warn_only_files = len({f.path for f in warns}) - len(
        {f.path for f in warns} & {f.path for f in errors}
    )
    log(
        f"SUMMARY: {len(paths)} file(s) scanned, {len(errors)} ERROR finding(s) in "
        f"{err_files} file(s), {len(warns)} WARN finding(s), "
        f"{warn_only_files} file(s) WARN-only."
    )

    if errors or (strict and warns):
        log("FAIL: rewrite the sentence. This gate blocks; it never edits your prose for you.")
        log("The standard, with what to write instead, is in DOCS-VOICE.md.")
        return 1
    if warns:
        log("PASS with warnings. WARN findings do not block; run with --strict to make them.")
    else:
        log("PASS: no AI rhetorical tells found.")
    return 0


# ---------------------------------------------------------------------------------------
# self-test: the red/green control, per rule, on every invocation
#
# FIXTURES is the red half. Every rule id in the data file must have one, and each fixture must
# trip THE RULE THAT NAMES IT - not merely "something fired". A battery whose arms all assert
# the same outcome cannot tell a working rule from a broken one next to it.

FIXTURES = {
    "revelation-heres-the":
        "Here's the catch nobody mentions when you set this up.",
    "revelation-part-worth":
        "This is the part worth knowing before you build your first template.",
    "revelation-what-nobody":
        "What nobody knew is that the setting had been there all along.",
    "revelation-turns-out":
        "It turns out that the two settings were fighting each other.",
    "difficulty-hard-part":
        "Tallyfy handles the hard part of keeping procedures alive.",
    "difficulty-where-it-gets":
        "That works fine until you add approvals, and this is where it gets tricky.",
    "exclusivity-most-people-dont":
        "Most teams never realize that a template can be paused.",
    "exclusivity-what-they-dont-tell":
        "What vendors don't tell you is that migration takes a quarter.",
    "exclusivity-few-realize":
        "Few people realize how much time this saves over a year.",
    "question-self-answered":
        "You set the deadline and forget it. So why does this matter? Because overdue "
        "tasks are the only signal a manager reads.",
    "contrast-not-just-but":
        "This is not just a checklist but a live record of who did what.",
    "contrast-isnt-about":
        "It's not about saving clicks. It is about knowing where the work stands.",
    "intimacy-lets-verb":
        "Let's dive into how approvals actually resolve.",
    "intimacy-sound-familiar":
        "Three people own the same step and none of them start it. Sound familiar?",
    "intimacy-you-might-think":
        "You might think a template is just a document.",
    "conclusion-signpost":
        "In conclusion, the deadline field is the one to set first.",
    "conclusion-key-takeaway":
        "The key takeaway is that steps become tasks only at launch.",
    "inflation-verb-hard":
        "Tallyfy will supercharge your onboarding and revolutionize handovers.",
    "inflation-verb-soft":
        "Templates empower your team to transform how work gets tracked.",
    "vague-attribution":
        "Studies show that written procedures cut errors by half.",
    "participial-tail":
        "Tallyfy records every completion, ensuring nothing is lost between teams.",
    "glyph-dash":
        "The deadline is the hard stop — miss it and the task shows as overdue.",
    "glyph-quote":
        "The step is “done” only when someone marks it complete…",
    "glyph-invisible":
        "The queue\u00a0grows whenever a step has no owner.",
}

# The GREEN half, and it is not symmetry for its own sake. A gate that refuses everything passes
# a positive-only self test while blocking every correct article, which is precisely how a voice
# checker gets switched off. Everything below is ordinary Tallyfy documentation English and must
# trip NOTHING:
#   - "Here's how" and "Here's where" are good documentation sentences. The tell is the abstract
#     significance noun after the definite article, never the word "here's".
#   - The H3 is a question, which is this repo's normal structure.
#   - "billing", "pricing" and "onboarding" end in "ing" and are not participial tails.
#   - "9 - 5" is a numeric range, not a dash.
#   - "not just" appears in its ordinary sense, with no "but Y" completing the contrast.
CLEAN_CONTROL = """---
description: 'Set up a template once, then launch it whenever the work comes in. Steps become
  tasks at launch, and deadlines keep everyone on the same page.'
title: Working with templates
---

## How do I create a template?

Here's how to create your first template. Open the Templates page and click New Template.

### What happens when I launch it?

Here's where to click: the Launch button sits at the top right. Each step in the template
becomes a task, and the person named on the step gets it.

You can change billing and pricing later from Settings. Onboarding a new teammate takes about
ten minutes.

Support is open 9 - 5 if you get stuck. Tasks are not just for one team, so invite anyone who
needs to see the work.

| Field | What it does |
| --- | --- |
| Deadline | The hard stop for the task. |
"""


def self_test():
    rules_path = os.environ.get("AI_TELLS_RULES", DEFAULT_RULES)
    rules = parse_rules(rules_path)
    by_id = {r.id: r for r in rules}
    cases = []

    def case(name, ok, detail=""):
        cases.append((name, ok, detail))
        log(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    # RED, per rule. Each fixture must trip the rule that names it, so a rule that has quietly
    # stopped matching is attributable rather than hidden behind a neighbour that still fires.
    for rid in sorted(by_id):
        rule = by_id[rid]
        fixture = FIXTURES[rid]
        if rule.scope == "description":
            raw = f"---\ndescription: '{fixture}'\ntitle: Fixture\n---\n\nBody text.\n"
        else:
            raw = f"---\ntitle: Fixture\n---\n\n{fixture}\n"
        hits = check_doc(Doc("<fixture>", raw), rules)
        got = {h.rule.id for h in hits}
        case(f"RED   {rid} fires on its own fixture", rid in got,
             "" if rid in got else f"tripped {sorted(got) or 'nothing'} instead")

    # GREEN. Ordinary documentation English must trip nothing at all.
    clean_hits = check_doc(Doc("<clean-control>", CLEAN_CONTROL), rules)
    case("GREEN clean control trips no rule", not clean_hits,
         "" if not clean_hits else "; ".join(h.render() for h in clean_hits))

    # The exclusions, proven rather than assumed. A tell planted inside a machine-generated card
    # must NOT be reported: it is a finding a human cannot fix.
    carded = (
        "---\ntitle: Fixture\n---\n\nOrdinary text.\n\n"
        '<CardGrid>\n<LinkTitleCard header="<b>A > B</b>" href="/x/" > Here\'s the catch you '
        "cannot fix. </LinkTitleCard>\n</CardGrid>\n"
    )
    case("EXCLUDE a tell inside a <CardGrid> is not reported",
         not check_doc(Doc("<cards>", carded), rules))

    related = (
        "---\ntitle: Fixture\n---\n\nOrdinary text.\n\n## Related articles\n"
        "Here's the catch in the generated block.\n"
    )
    case("EXCLUDE a tell under `## Related articles` is not reported",
         not check_doc(Doc("<related>", related), rules))

    fenced = (
        "---\ntitle: Fixture\n---\n\n```text\nHere's the catch inside a code block.\n```\n"
    )
    case("EXCLUDE a tell inside a code fence is not reported",
         not check_doc(Doc("<fence>", fenced), rules))

    # The quoted-attribute trap, stated as its own case because the naive tag regex passes every
    # other assertion here. `<\/?[A-Za-z][^>]*>` stops at the `>` inside header="<b>...</b>",
    # so the card's text leaks into prose and gets scanned as if a human wrote it.
    leaky = (
        "---\ntitle: Fixture\n---\n\nOrdinary text.\n\n"
        '<LinkTitleCard header="<b>Tasks > Steps</b>" href="/x/" > In conclusion, this is '
        "generated. </LinkTitleCard>\n"
    )
    case("EXCLUDE a quoted `>` inside a tag attribute does not leak card text",
         not check_doc(Doc("<leaky>", leaky), rules))

    # An UNCLOSED fence that follows a CLOSED one. The obvious implementation - "look for an
    # unterminated fence only if no closed fence exists" - misses exactly this shape and leaks
    # a whole code block into prose.
    two_fences = (
        "---\ntitle: Fixture\n---\n\n```text\nclosed\n```\n\n```text\nIn conclusion, "
        "this is inside an unterminated fence.\n"
    )
    case("EXCLUDE an unclosed fence AFTER a closed one still masks to EOF",
         not check_doc(Doc("<fences>", two_fences), rules))

    # A description may legitimately begin with a digit, so the YAML block-scalar skip must not
    # eat one. Asserted on the SPAN rather than through a rule: no rule matches a bare number,
    # so a rule-level fixture could not tell a truncated description from an intact one - it
    # would pass either way, which is a control that cannot fail.
    digit_desc = "---\ndescription: 500 users share one template.\ntitle: X\n---\n\nBody.\n"
    dspan = description_span(digit_desc)
    got = digit_desc[dspan[0]:dspan[1]] if dspan else None
    case("SCOPE a description beginning with a digit is not truncated",
         got == "500 users share one template.", f"got {got!r}")
    folded = "---\ndescription: >-\n  In conclusion: set it once.\ntitle: X\n---\n\nBody.\n"
    fspan = description_span(folded)
    fgot = folded[fspan[0]:fspan[1]] if fspan else None
    case("SCOPE a YAML block-scalar indicator is skipped, its value is not",
         fgot is not None and fgot.strip().startswith("In conclusion"), f"got {fgot!r}")

    # Line numbers are REAL, not the line number of some post-stripping copy. Stripped regions
    # are blanked in place rather than deleted precisely so this holds; a gate pointing at the
    # wrong line is one people stop reading.
    lined = (
        "---\ntitle: Fixture\n---\n\n"          # lines 1-4
        "```text\nnoise\nnoise\n```\n\n"        # lines 5-9
        "Ordinary sentence.\n\n"                # lines 10-11
        "In conclusion, the deadline comes first.\n"   # line 12
    )
    lh = check_doc(Doc("<lines>", lined), rules)
    case("LINE  the reported line number is the real one",
         len(lh) == 1 and lh[0].line == 12,
         "" if (len(lh) == 1 and lh[0].line == 12)
         else f"got {[(h.line, h.rule.id) for h in lh]}, expected [(12, 'conclusion-signpost')]")

    # The description ships to search results, so it is prose and is checked.
    desc_doc = "---\ndescription: 'In conclusion, use a template.'\ntitle: X\n---\n\nBody.\n"
    case("SCOPE the frontmatter description is checked",
         any(h.rule.id == "conclusion-signpost" for h in check_doc(Doc("<d>", desc_doc), rules)))

    meta_doc = "---\nid: 89d271c1294e72c1\ntitle: In conclusion\n---\n\nBody.\n"
    case("SCOPE frontmatter metadata other than description is not checked",
         not check_doc(Doc("<m>", meta_doc), rules))

    def _error_kind(fn, *args):
        try:
            fn(*args)
        except CheckerError:
            return True
        return False

    # The baseline. Four cases, because the ways it can go wrong are all silent: it can
    # suppress too much, suppress the wrong thing, rot into a permanent allowlist, or break the
    # local `--files` command that people actually use.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_bl:
        doc_raw = "---\ntitle: Fixture\n---\n\nIn conclusion, set the deadline first.\n"
        doc_path = os.path.join(tmp_bl, "a.mdx")
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(doc_raw)
        hits = check_doc(Doc(doc_path.replace(os.sep, "/"), doc_raw), rules)

        def _bl(lines):
            bl = os.path.join(tmp_bl, "bl.txt")
            with open(bl, "w", encoding="utf-8") as fh:
                fh.write("# fixture baseline\n" + "\n".join(lines) + "\n")
            return bl

        entry = f"{doc_path.replace(os.sep, '/')} | conclusion-signpost | {hits[0].text}"
        kept, _ = apply_baseline(list(hits), parse_baseline(_bl([entry])), "bl")
        case("BASELINE a recorded finding is suppressed", not kept)

        # Two occurrences against one baseline line: the second must still be reported. Without
        # this, one entry would grandfather every future repeat of the same sentence in that file.
        kept2, _ = apply_baseline(list(hits) + list(hits), parse_baseline(_bl([entry])), "bl")
        case("BASELINE a SECOND occurrence beyond the recorded count is still reported",
             len(kept2) == 1, f"kept {len(kept2)}, expected 1")

        stale_bl = parse_baseline(_bl([entry, f"{doc_path.replace(os.sep, '/')} | "
                                              f"conclusion-signpost | to sum up:"]))
        case("BASELINE a stale entry is FATAL, so the file can only shrink",
             _error_kind(apply_baseline, list(hits), stale_bl, "bl"))

        # The same staleness check over a PARTIAL scan would call every other file's entry stale
        # and exit 2 on a run that is working perfectly, which would make the local authoring
        # command unusable.
        try:
            apply_baseline(list(hits), stale_bl, "bl", False)
            partial_ok = True
        except CheckerError:
            partial_ok = False
        case("BASELINE a partial (--files) scan does not trip the staleness check", partial_ok)

        ghost = parse_baseline(_bl([f"{doc_path.replace(os.sep, '/')} | no-such-rule | x"]))
        case("BASELINE an entry naming an unknown rule id is FATAL",
             _error_kind(check_baseline_rule_ids, ghost, rules, "bl"))


    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "bad.txt")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("only-three | manufactured-revelation | ERROR\n")
        case("FAIL CLOSED a malformed rule line is fatal, never skipped",
             _error_kind(parse_rules, bad))

        missing = os.path.join(tmp, "nope.txt")
        case("FAIL CLOSED a missing rule list is fatal", _error_kind(parse_rules, missing))

        shrunk = os.path.join(tmp, "shrunk.txt")
        with open(shrunk, encoding="utf-8", mode="w") as fh:
            with open(rules_path, encoding="utf-8") as src:
                for line in src:
                    if not line.strip().startswith("difficulty-hard-part"):
                        fh.write(line)
        case("FAIL CLOSED deleting a locked rule id is fatal", _error_kind(parse_rules, shrunk))

        empty_pat = os.path.join(tmp, "emptypat.txt")
        with open(empty_pat, "w", encoding="utf-8") as fh:
            fh.write("zero-width | glyph-tell | ERROR | prose | x* | matches nothing at all\n")
        case("FAIL CLOSED a pattern that matches the empty string is fatal",
             _error_kind(parse_rules, empty_pat))

        notutf8 = os.path.join(tmp, "bad.mdx")
        with open(notutf8, "wb") as fh:
            fh.write(b"---\ntitle: X\n---\n\n\xff\xfe not utf-8\n")
        case("FAIL CLOSED a file that is not valid UTF-8 is fatal, not a pass",
             _error_kind(run, [notutf8], rules))

        empty = os.path.join(tmp, "empty.txt")
        with open(empty, "w", encoding="utf-8") as fh:
            fh.write("# nothing but comments\n")
        case("FAIL CLOSED a rule list with zero rules is fatal", _error_kind(parse_rules, empty))

        case("FAIL CLOSED an empty input set is fatal, never a pass",
             _error_kind(run, [], rules))

    failed = [c for c in cases if not c[1]]
    log()
    if failed:
        annotate("error", f"ai-tell-check self-test FAILED ({len(failed)} case(s))")
        log(f"SELF-TEST FAILED: {len(failed)} of {len(cases)} case(s).")
        return 1
    log(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s). Every rule proven able to "
        f"fire on its own fixture, and proven silent on ordinary documentation English.")
    return 0


# ---------------------------------------------------------------------------------------
# wiring guard: a red gate that blocks nothing is decoration

GATE_JOB = "ai-tell-gate"
# The jobs that put content in front of a reader. Each must name the gate DIRECTLY.
PUBLISH_JOBS = ("sync",)
# Everything else, with the reason it cannot publish an unchecked article. Anything NOT listed
# and NOT in PUBLISH_JOBS is reported, so ADDING a job forces a decision rather than silently
# escaping the gate.
WIRING_KNOWN = {
    GATE_JOB: "the gate itself",
    "promotion-hold-gate": "the other root gate; publishes nothing itself",
    "validate-markdown": "read-only lint, publishes nothing",
    "generate-snippets": "early-exits on main; writes MDX back to staging only",
    "update-last-modified": "early-exits on main; writes MDX back to staging only",
    "generate-related-articles": "early-exits on main; writes MDX back to staging only",
    "check-deleted-files": "only removes Answers entries for files deleted in this commit",
    "upload-to-tallyfy-answers":
        "indexes article text for search. DELIBERATELY not gated: #191 scopes this gate to "
        "blocking `sync`, which is what puts an article in front of a reader. Widening it to "
        "the search index is a decision with its own blast radius (a red voice gate would "
        "freeze search updates), not a tidy-up. Decide it, do not drift into it.",
}


def check_wiring(workflow_path):
    try:
        import yaml
    except ImportError:
        raise CheckerError("pyyaml is required for --check-wiring")
    if not os.path.isfile(workflow_path):
        raise CheckerError(f"workflow not found at {workflow_path}")
    with open(workflow_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    jobs = (doc or {}).get("jobs") or {}
    if not jobs:
        raise CheckerError(f"{workflow_path} declares no jobs")
    if GATE_JOB not in jobs:
        raise CheckerError(f"{workflow_path} has no {GATE_JOB!r} job")

    def needs_of(name):
        raw = (jobs.get(name) or {}).get("needs") or []
        return [raw] if isinstance(raw, str) else list(raw)

    problems = []

    # DIRECT dependency, deliberately not transitive. `sync` guards itself with
    # `if: !failure() && !cancelled()`, a status-function conditional that REPLACES the default
    # "skip when a needed job was skipped". Measured on this repo's run 27840821129: every other
    # job read `skipped` and `sync` read `success`. A gate inherited through a neighbour is a
    # gate that can be skipped, so a publishing job must name this one itself.
    for name in PUBLISH_JOBS:
        if name not in jobs:
            problems.append(
                f"job {name!r} is named in PUBLISH_JOBS but does not exist in {workflow_path}. "
                f"Either it was renamed - in which case update PUBLISH_JOBS - or the publishing "
                f"step moved and this gate is now guarding nothing."
            )
        elif GATE_JOB not in needs_of(name):
            problems.append(
                f"job {name!r} does not name {GATE_JOB!r} DIRECTLY in its `needs`, so a red gate "
                f"would not stop it publishing. A transitive path does not count here."
            )

    # The gate must be a root job. A gate carrying `needs:` is skipped when its upstream fails,
    # which is exactly the run on which you wanted it. A gate carrying `if:` can be skipped by
    # the same status-function behaviour that lets `sync` publish through a skipped pipeline.
    if needs_of(GATE_JOB):
        problems.append(
            f"{GATE_JOB!r} has `needs`, so another job failing would SKIP the gate. It must be a "
            f"root job."
        )
    if (jobs.get(GATE_JOB) or {}).get("if") is not None:
        problems.append(
            f"{GATE_JOB!r} has an `if:`, so it can be skipped. Measured on run 27840821129: on a "
            f"run where the triggering workflow did not succeed, every `if:`-guarded job skipped "
            f"and `sync` published anyway. A gate that can be skipped is not a gate."
        )

    log(f"Workflow {workflow_path}: {len(jobs)} job(s).")
    for name in sorted(jobs):
        if name in PUBLISH_JOBS:
            state = "gated" if GATE_JOB in needs_of(name) else "NOT GATED"
            log(f"  - {name}: publishes -> {state}")
        elif name in WIRING_KNOWN:
            log(f"  - {name}: not gated ({WIRING_KNOWN[name]})")
        else:
            problems.append(
                f"job {name!r} is new and is neither in PUBLISH_JOBS nor in WIRING_KNOWN. Decide "
                f"which it is: if it can put an article in front of a reader, add it to "
                f"PUBLISH_JOBS and to its `needs`; if it cannot, add it to WIRING_KNOWN with the "
                f"reason. Both live in {os.path.basename(__file__)}."
            )
            log(f"  - {name}: UNCLASSIFIED")

    if problems:
        for problem in problems:
            log(f"WIRING FAIL: {problem}")
            annotate("error", f"ai-tell gate wiring: {problem}")
        return 1
    log(f"WIRING OK: {', '.join(PUBLISH_JOBS)} waits for {GATE_JOB}, and the gate is a root job "
        f"with no `if:`.")
    return 0


# ---------------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="Block AI rhetorical tells in documentation.")
    parser.add_argument("--dir", default="", help=f"content root (default {DEFAULT_DIR})")
    parser.add_argument("--files", default="", help="scan these files instead of --dir")
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE,
                        help="pre-existing findings to suppress; pass '' to ignore it")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-wiring", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="make WARN findings block too (useful while writing)")
    parser.add_argument("--quiet", action="store_true", help="summary only, no per-finding lines")
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            log("Self-test: proving every rule can fire, and that none fires on clean prose.")
            os.environ.setdefault("AI_TELLS_RULES", args.rules)
            return self_test()
        if args.check_wiring:
            return check_wiring(args.workflow)

        rules = parse_rules(args.rules)
        if args.files:
            paths = [p for p in re.split(r"[,\s]+", args.files.strip()) if p]
            for p in paths:
                if not os.path.isfile(p):
                    raise CheckerError(f"--files names a path that does not exist: {p}")
        else:
            paths = discover(args.dir or DEFAULT_DIR)
        # Staleness compares the WHOLE baseline against everything found, so it is only
        # meaningful over the whole corpus. `--files`, and a `--dir` pointing at a subtree, are
        # both partial scans where every other file's entry would look stale.
        full_scan = not args.files and args.dir in ("", DEFAULT_DIR)
        return run(paths, rules, strict=args.strict, quiet=args.quiet,
                   baseline_path=args.baseline or None, enforce_stale=full_scan)
    except CheckerError as exc:
        log(f"CHECKER ERROR: {exc}")
        annotate("error", f"ai-tell-check could not run: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - deliberate
        # A crash must be 2, never 1. Exit 1 means "I looked and found findings", and an
        # uncaught exception would otherwise exit 1 through Python's own default - a broken
        # checker wearing the exit code of a working one.
        import traceback
        traceback.print_exc()
        log(f"CHECKER CRASHED: {exc!r}")
        annotate("error", f"ai-tell-check crashed: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
