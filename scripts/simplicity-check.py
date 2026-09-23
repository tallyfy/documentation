#!/usr/bin/env python3
"""
simplicity-check.py
Scores documentation articles for business-reader simplicity (the "lowest common
denominator" rule in CLAUDE.md). Higher score = more complex / more intimidating
for a non-technical business reader.

Read-only. Never edits content. Two modes:

  Triage (build the work-list of articles to simplify):
    python scripts/simplicity-check.py --dir src/content/docs \
        --out-json /tmp/worklist.json --out-csv /tmp/worklist.csv

  Gate (score just the article(s) a unit touched; used before committing):
    python scripts/simplicity-check.py --files src/content/docs/pro/.../index.mdx --report

  Self-test (prove the scope rules below work in both directions):
    python scripts/simplicity-check.py --self-test

Pages under open-api/code-samples are never scored, in any mode (see
ALWAYS_SKIP below). Naming one with --files prints a SKIPPED line saying why.
It is never reported as a pass.

Exit code: 0 = every scored file is below threshold and has no AI-tell words
               (also when every named file was skipped: the output says
               SKIPPED, never PASS);
           1 = at least one file is at/above threshold or contains a banned word;
           2 = the checker could not do its job: a file it could not read or
               score, an empty scan, or a crash. "I could not look" never
               shares an exit code with "I looked and it passed".

The score is computed on the article's BUSINESS REGION only - everything above
the first technical section ("For your IT team" / "For developers" / "Technical
details") and outside footnote definitions. Detail that has been correctly
*demoted* into a technical section or footnote does NOT count against the page.
That is deliberate: it rewards "demote, don't delete".
"""

import re
import os
import io
import sys
import csv
import json
import argparse
import tempfile
import statistics
import contextlib
from pathlib import Path

# Mirror markdown-lint.py exactly so triage scans the same file set.
SKIP_FILES = ["404.mdx"]
SKIP_DIRS = ["src/content/docs/pro/changelog", "src/content/docs/changelog"]

# Pure developer code-reference areas - never simplified for business readers
# (auto-style API code snippets and API-client tool setup). Excluded from triage
# like changelog; they are structural reference, not prose articles.
#
# ALWAYS_SKIP is left out of EVERY mode: triage (--dir) and gate (--files) alike.
# Owner decision on tallyfy/documentation#285. Before it, only triage left
# code-samples out, so scoring one page by name reported a page that triage
# deliberately never lists. Each entry maps to the reason printed when a page
# under it is named with --files.
ALWAYS_SKIP = {
    "open-api/code-samples": "developer code reference, left out of the readability "
                             "check by owner decision (tallyfy/documentation#285)",
}

# Left out of triage only. #285 decided code-samples, so a page here is still
# scored when it is named with --files.
TRIAGE_ONLY_SKIP = ["open-api/api-clients"]

EXCLUDE_FROM_TRIAGE = list(ALWAYS_SKIP) + TRIAGE_ONLY_SKIP


def content_relative(path):
    """The path below src/content/docs/, with forward slashes. Matching is done on
    this and never on the absolute path, so a checkout that happens to sit under a
    folder named like a skipped area does not skip every page in it."""
    norm = str(path).replace(os.sep, "/")
    return norm.split("src/content/docs/", 1)[-1]


def skip_match(path, areas):
    """The first area in `areas` that `path` sits under, or None. The one place the
    scope rule is applied, for triage and for --files."""
    rel = content_relative(path)
    for area in areas:
        if area in rel:
            return area
    return None

DEFAULT_THRESHOLD = 45

# ---------------------------------------------------------------------------
# Jargon tiers. Counted as DISTINCT terms present in the business region.
# BAN  = no business reason to sit in prose; belongs in a technical section or
#        footnote (or be cut). EXPLAIN = legitimate for the topic, but must be
#        glossed/footnoted on first use - only counted when never explained.
# ---------------------------------------------------------------------------
BAN_PATTERNS = {
    "PKCE": r"\bPKCE\b",
    "RS256": r"\bRS256\b",
    "JWT": r"\bJWTs?\b",
    "jwks": r"\bjwks\b",
    "VRAM": r"\bVRAM\b",
    "TFLOPs": r"\bTFLOPs?\b",
    "MoE": r"\bMoE\b",
    "mixture-of-experts": r"mixture of experts",
    "stdio": r"\bstdio\b",
    "SSE": r"\bSSE\b",
    "DLP": r"\bDLP\b",
    "WAF": r"\bWAF\b",
    "VNet": r"\bVNet\b",
    "DCR": r"\bDCR\b",
    "OBO": r"\bOBO\b",
    "on-behalf-of": r"\bon-behalf-of\b",
    "FP8": r"\bFP8\b",
    "quantization": r"\bquantiz(?:ation|ed|e)\b",
    "mcp_resource": r"\bmcp_resource\b",
    "RFC-number": r"\bRFC\s*\d+\b",
    "tokens-per-second": r"\btokens?\s*/\s*s(?:econd)?\b",
    "load-balancer": r"\bload balancer",
    "well-known-endpoint": r"/\.well-known/",
}

EXPLAIN_PATTERNS = {
    "OAuth": r"\bOAuth\b",
    "OIDC": r"\bOIDC\b",
    "SAML": r"\bSAML\b",
    "SCIM": r"\bSCIM\b",
    "webhook": r"\bwebhooks?\b",
    "SSO": r"\bSSO\b",
    "MFA": r"\bMFA\b",
    "IAM": r"\bIAM\b",
    "BPMN": r"\bBPMN\b",
    "RPA": r"\bRPA\b",
    "SLM": r"\bSLM\b",
    "LLM": r"\bLLMs?\b",
    "inference": r"\binference\b",
    "embeddings": r"\bembeddings?\b",
    "PKCE-spelled": r"proof key for code exchange",
}

# Concrete spec mentions that belong in a footnote or technical section.
SPEC_PATTERNS = [
    r"\bRFC\s*\d+\b",
    r"\b\d+[-\s]?bit\b",
    r"\bTFLOPs?\b",
    r"\b\d+\s?GB\s+VRAM\b",
    r"\bVRAM\b",
    r"\bOSWorld\b",
    r"\bWebArena\b",
    r"\b\d+(?:\.\d+)?B\s+parameters?\b",
    r"\b\d+(?:\.\d+)?[MB]\b(?=[^\n]{0,30}param)",
]

# Zero-tolerance AI-tell words from CLAUDE.md. Any hit = hard FAIL.
BLACKLIST = [
    "delve", "landscape", "tapestry", "multifaceted", "pivotal",
    "comprehensive", "seamless", "robust", "leverage", "facilitate",
    "paramount", "meticulous", "underscore", "moreover", "furthermore",
    "indeed", "subsequently", "additionally", "endeavor", "embark",
    "in essence", "notably", "arguably", "methodology", "stakeholder",
    "innovative", "scalable",
]

# Developer-reference areas: jargon is partly the audience, so dampen the
# jargon/code/spec signals there (not the length/readability ones).
REFERENCE_PREFIXES = (
    "pro/integrations/open-api",
    "pro/integrations/webhooks",
)

TECH_SECTION_RE = re.compile(
    r"(?im)^#{2,4}\s+(for your it team|for developers|technical details|"
    r"technical reference|technical setup|for your it admin|for it admins?)\b"
)
RELATED_RE = re.compile(r"(?im)^##\s+Related articles\b")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^[^\]]+\]:.*$")


def count_syllables(word):
    """Approximate English syllable count - good enough for a readability proxy."""
    word = word.lower()
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def flesch_kincaid_grade(prose):
    """Flesch-Kincaid grade level of plain prose. Lower = simpler."""
    sentences = [s for s in re.split(r"[.!?]+", prose) if s.strip()]
    words = re.findall(r"[A-Za-z]+", prose)
    if not sentences or not words:
        return 0.0
    syllables = sum(count_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59


def strip_code_blocks(text):
    """Return (text_without_fenced_blocks, fenced_line_count, non_d2_fenced_line_count)."""
    lines = text.split("\n")
    out, fenced, non_d2 = [], 0, 0
    in_block, lang = False, ""
    for line in lines:
        m = re.match(r"^```(\w[\w-]*)?", line.strip())
        if m and not in_block:
            in_block, lang = True, (m.group(1) or "").lower()
            fenced += 1
            continue
        if in_block:
            fenced += 1
            if line.strip().startswith("```"):
                in_block, lang = False, ""
            elif lang not in ("d2", "mermaid"):
                non_d2 += 1
            continue
        out.append(line)
    return "\n".join(out), fenced, non_d2


def to_prose(text):
    """Crude markdown -> prose for readability/sentence stats."""
    text, _, _ = strip_code_blocks(text)
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", "", text)        # headings
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)             # bullet markers
    text = re.sub(r"`[^`]*`", " ", text)                    # inline code
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)       # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)    # links -> text
    text = re.sub(r"[*_>#|]", " ", text)
    text = re.sub(r"\[\^[^\]]+\]", " ", text)               # footnote refs
    return re.sub(r"\s+", " ", text).strip()


def distinct_matches(patterns, text):
    """Names of patterns that match at least once in text."""
    hits = []
    for name, pat in (patterns.items() if isinstance(patterns, dict) else []):
        if re.search(pat, text):
            hits.append(name)
    return hits


def is_explained(text, pat):
    """True if at least one occurrence of pat sits near a footnote ref or a
    parenthetical gloss (so the term is defined on use somewhere)."""
    for m in re.finditer(pat, text):
        window = text[m.start(): m.end() + 120]
        before = text[max(0, m.start() - 120): m.start()]
        if "[^" in window or "[^" in before:
            return True
        # parenthetical gloss right after the term, e.g. "OAuth (a sign-in standard)"
        if re.match(r"[A-Za-z0-9 ]{0,8}\([^)]{8,}\)", text[m.end(): m.end() + 120]):
            return True
    return False


def analyze(path, content):
    """Compute all signals + the 0-100 complexity score for one article."""
    rel = str(path).split("src/content/docs/", 1)[-1]
    cat_mult = 0.4 if rel.startswith(REFERENCE_PREFIXES) else 1.0

    fm = FRONTMATTER_RE.match(content)
    body = content[fm.end():] if fm else content

    # Cut the auto-generated Related articles block (never scored).
    rm = RELATED_RE.search(body)
    if rm:
        body = body[:rm.start()]

    # Split business region (scored) from the demoted technical region (exempt).
    tm = TECH_SECTION_RE.search(body)
    has_it_section = bool(tm)
    business = body[:tm.start()] if tm else body
    business = FOOTNOTE_DEF_RE.sub("", business)   # footnote glosses are exempt

    # --- signals on the business region ---
    hard = distinct_matches(BAN_PATTERNS, business)
    explain_unexplained = [
        name for name, pat in EXPLAIN_PATTERNS.items()
        if re.search(pat, business) and not is_explained(business, pat)
    ]
    spec_without_fn = 0
    for pat in SPEC_PATTERNS:
        for m in re.finditer(pat, business):
            window = business[max(0, m.start() - 120): m.end() + 120]
            if "[^" not in window:
                spec_without_fn += 1

    _, fenced_lines, non_d2_lines = strip_code_blocks(business)
    business_lines = [l for l in business.split("\n") if l.strip()]
    code_ratio = (non_d2_lines / len(business_lines)) if business_lines else 0.0

    prose = to_prose(business)
    fk_grade = flesch_kincaid_grade(prose)
    sentences = [s for s in re.split(r"[.!?]+", prose) if s.strip()]
    sent_lens = [len(re.findall(r"[A-Za-z]+", s)) for s in sentences] or [0]
    long_sent_pct = 100.0 * sum(1 for n in sent_lens if n > 30) / len(sent_lens)
    avg_sent_len = statistics.mean(sent_lens) if sent_lens else 0

    # --- signals on the whole body ---
    business_words = len(re.findall(r"[A-Za-z]+", to_prose(business)))
    total_words = len(re.findall(r"[A-Za-z]+", to_prose(body)))
    headings = len(re.findall(r"(?m)^#{2,4}\s+", body))
    headings_per_1000w = headings / (total_words / 1000) if total_words else 0
    deep_bullets = len(re.findall(r"(?m)^\s{8,}[-*]\s+", body))

    # plain opening: first ~60 words after the first H2
    plain_opening = True
    h2 = re.search(r"(?m)^##\s+.*$", business)
    if h2:
        after = business[h2.end():]
        nxt = re.search(r"(?m)^#{2,4}\s+", after)
        opening = after[:nxt.start()] if nxt else after
        opening = " ".join(opening.split()[:60])
        jcount = len(distinct_matches(BAN_PATTERNS, opening)) + len(distinct_matches(EXPLAIN_PATTERNS, opening))
        if jcount >= 2 or "`" in opening or re.search(r"\bRFC\b", opening):
            plain_opening = False

    blacklist_hits = sorted({w for w in BLACKLIST if re.search(r"\b" + re.escape(w) + r"\b", business, re.I)})

    # --- score (caps sum to 100) ---
    opening_jargon = (25 if not plain_opening else 0) + len(hard) * 3 * cat_mult
    score = 0.0
    score += min(35, opening_jargon)
    score += min(15, code_ratio * 100 * 0.5 * cat_mult)
    score += min(12, spec_without_fn * 3 * cat_mult)
    score += min(8, len(explain_unexplained) * 1 * cat_mult)
    score += min(15, max(0.0, (fk_grade - 9) * 2))
    score += min(5, long_sent_pct * 0.2)
    score += min(5, max(0.0, (business_words - 1500) / 600))
    score += min(3, max(0.0, headings_per_1000w - 8))
    score += min(2, deep_bullets * 0.5)
    score = round(min(100.0, score), 1)

    failed = score >= 0  # placeholder; threshold applied by caller
    return {
        "path": rel,
        "score": score,
        "category": "reference" if cat_mult < 1.0 else "business",
        "words": total_words,
        "business_words": business_words,
        "fk_grade": round(fk_grade, 1),
        "avg_sentence_len": round(avg_sent_len, 1),
        "long_sentence_pct": round(long_sent_pct, 1),
        "code_ratio": round(code_ratio, 3),
        "headings": headings,
        "plain_opening": plain_opening,
        "has_it_section": has_it_section,
        "hard_jargon": hard,
        "unexplained_jargon": explain_unexplained,
        "spec_without_footnote": spec_without_fn,
        "blacklist_hits": blacklist_hits,
    }


def gather_files(base_dir):
    files = []
    for path, _subdirs, names in os.walk(base_dir):
        if any(sd in path for sd in SKIP_DIRS):
            continue
        for name in names:
            if not name.endswith(".mdx") or name in SKIP_FILES:
                continue
            full = os.path.join(path, name)
            if skip_match(full, EXCLUDE_FROM_TRIAGE):
                continue
            files.append(full)
    return files


def print_report(r, threshold):
    status = "FAIL" if (r["score"] >= threshold or r["blacklist_hits"]) else "PASS"
    glyph = "❌" if status == "FAIL" else "✓"
    print(f"{glyph} {r['path']}  score={r['score']}  ({status}, threshold {threshold})")
    print(f"  └─ words={r['words']} (business {r['business_words']})  FK-grade={r['fk_grade']}  "
          f"long-sentences={r['long_sentence_pct']}%  code={int(r['code_ratio']*100)}%  category={r['category']}")
    print(f"  └─ plain-opening={r['plain_opening']}  has-technical-section={r['has_it_section']}  "
          f"headings={r['headings']}")
    if r["hard_jargon"]:
        print(f"  └─ hard jargon in prose: {', '.join(r['hard_jargon'])}")
    if r["unexplained_jargon"]:
        print(f"  └─ unexplained terms: {', '.join(r['unexplained_jargon'])}")
    if r["spec_without_footnote"]:
        print(f"  └─ spec mentions without a footnote: {r['spec_without_footnote']}")
    if r["blacklist_hits"]:
        print(f"  └─ ⛔ AI-tell words (hard fail): {', '.join(r['blacklist_hits'])}")


def main(argv=None):
    try:
        return _main(argv)
    except Exception as exc:  # noqa: BLE001 - deliberate
        # A crash must be 2, never 1. Python's own exit code for an uncaught
        # exception is 1, which here means "a page scored too high", so a broken
        # checker would otherwise look exactly like a page that needs work.
        import traceback
        traceback.print_exc()
        print(f"CHECKER ERROR: simplicity-check crashed: {exc!r}")
        return 2


def _main(argv=None):
    parser = argparse.ArgumentParser(description="Score docs for business-reader simplicity")
    parser.add_argument("--dir", type=str, help="Base directory of MDX files (triage mode)")
    parser.add_argument("--files", type=str, nargs="+", help="Specific .mdx files to score (gate mode)")
    parser.add_argument("--out-json", type=str, help="Write the ranked work-list as JSON")
    parser.add_argument("--out-csv", type=str, help="Write the ranked work-list as CSV")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help=f"Complexity threshold (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--report", action="store_true", help="Print per-file signal breakdown")
    parser.add_argument("--self-test", action="store_true",
                        help="Prove the scope rules skip what they should and score everything else")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if not args.dir and not args.files:
        print("Error: pass --dir (triage) or --files (gate)")
        return 2

    targets = []
    skipped = []
    if args.files:
        # The same scope rule triage applies, so a page that triage never lists
        # is not scored just because someone named it. Said out loud, never
        # reported as a pass.
        for f in args.files:
            area = skip_match(f, ALWAYS_SKIP)
            if area:
                skipped.append((content_relative(f), ALWAYS_SKIP[area]))
            else:
                targets.append(Path(f))
    else:
        base_dir = Path(args.dir)
        if not base_dir.is_dir():
            print(f"Error: Invalid directory: {args.dir}")
            return 2
        targets = [Path(f) for f in gather_files(args.dir)]
        if not targets:
            # A scan over nothing reports exactly what a clean corpus reports.
            print(f"CHECKER ERROR: no .mdx files found to scan under {args.dir}")
            return 2

    results = []
    errors = []
    for p in targets:
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠ could not read {p}: {e}")
            errors.append(p)
            continue
        try:
            results.append(analyze(p, content))
        except Exception as e:
            print(f"⚠ could not score {p}: {e}")
            errors.append(p)

    results.sort(key=lambda r: r["score"], reverse=True)

    over = [r for r in results if r["score"] >= args.threshold or r["blacklist_hits"]]

    # Gate mode (or --report): print breakdowns.
    if args.files or args.report:
        for r in results:
            print_report(r, args.threshold)
    for rel, why in skipped:
        print(f"SKIPPED {rel}  (not scored: {why})")

    # Triage artifacts.
    if args.out_json or args.out_csv:
        for i, r in enumerate(over, 1):
            r["id"] = f"U{i:03d}"
        if args.out_json:
            Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
            with open(args.out_json, "w", encoding="utf-8") as f:
                json.dump({
                    "threshold": args.threshold,
                    "total_scanned": len(results),
                    "on_worklist": len(over),
                    "items": over,
                }, f, indent=2)
            print(f"✓ wrote {len(over)} work-list items to {args.out_json}")
        if args.out_csv:
            Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
            with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "score", "category", "words", "fk_grade", "plain_opening",
                            "has_it_section", "hard_jargon", "unexplained_jargon",
                            "spec_without_footnote", "blacklist_hits", "path"])
                for r in over:
                    w.writerow([r.get("id"), r["score"], r["category"], r["words"], r["fk_grade"],
                                r["plain_opening"], r["has_it_section"], "|".join(r["hard_jargon"]),
                                "|".join(r["unexplained_jargon"]), r["spec_without_footnote"],
                                "|".join(r["blacklist_hits"]), r["path"]])
            print(f"✓ wrote CSV to {args.out_csv}")

    # Summary line.
    if args.dir and not args.files:
        print(f"\nScanned {len(results)} files - {len(over)} at/above threshold {args.threshold}.")
    if skipped:
        print(f"\n{len(skipped)} file(s) skipped and not scored. {len(results)} file(s) scored.")

    if errors:
        # Dropping a file it could not read, then exiting 0, would report a page
        # nobody looked at as if it had passed.
        print(f"\nCHECKER ERROR: {len(errors)} file(s) could not be read or scored.")
        return 2

    return 1 if over else 0


# ---------------------------------------------------------------------------
# Self-test. Drives the real entry point, main(), on a throwaway docs tree.
#
# The same complex fixture sits both inside and outside the skipped area. It
# must FAIL where it is scored, so its SKIPPED result inside code-samples is
# proven to be the scope rule at work and not a page that happened to pass. A
# plain fixture must PASS, so the checker is not simply failing everything.
# ---------------------------------------------------------------------------

_COMPLEX = """---
title: Fixture
---

## Overview

The `POST /organizations/{org_id}/widgets` endpoint instantiates heterogeneous configuration entities, necessitating authorization semantics that intermittently propagate organizational identifiers across asynchronous integration boundaries without deterministic acknowledgement guarantees for downstream consumers.

```json
{"id": 1, "name": "widget", "type": "configuration", "enabled": true}
{"id": 2, "name": "widget", "type": "configuration", "enabled": true}
{"id": 3, "name": "widget", "type": "configuration", "enabled": true}
{"id": 4, "name": "widget", "type": "configuration", "enabled": true}
{"id": 5, "name": "widget", "type": "configuration", "enabled": true}
{"id": 6, "name": "widget", "type": "configuration", "enabled": true}
```

Administrators occasionally misinterpret the synchronization characteristics, particularly regarding idempotency considerations, reconciliation procedures, and authentication propagation throughout interconnected organizational infrastructure environments everywhere.
"""

_PLAIN = """---
title: Fixture
---

## Overview

A template is a list of steps. You run it when work comes in. Each step goes to a person. They tick it off when it's done.

You can see every run in one place. It's easy to tell what's late.
"""


def self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append((name, ok))
        print(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    def run(argv):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = main(argv)
        except Exception as exc:  # noqa: BLE001 - an escaped exception is a result here
            rc = f"raised {exc!r}"
        return rc, buf.getvalue()

    def scored_line(out, rel):
        """The PASS or FAIL header line for rel, or None."""
        for line in out.splitlines():
            if f" {rel}  score=" in line and ("(PASS," in line or "(FAIL," in line):
                return line
        return None

    print("Self-test: proving code-samples pages are skipped in every mode, "
          "and every other page is still scored.")
    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp, "repo", "src", "content", "docs")
        cs_rel = "pro/integrations/open-api/code-samples/groups/complex.mdx"
        ac_rel = "pro/integrations/open-api/api-clients/tool/complex.mdx"
        guide_rel = "pro/guides/complex.mdx"
        plain_rel = "pro/guides/plain.mdx"
        for rel, body in ((cs_rel, _COMPLEX), (ac_rel, _COMPLEX),
                          (guide_rel, _COMPLEX), (plain_rel, _PLAIN)):
            f = docs / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(body, encoding="utf-8")
        cs, ac, guide, plain = (str(docs / r) for r in (cs_rel, ac_rel, guide_rel, plain_rel))

        # A checkout that sits under a folder named like the skipped area. Only
        # the part below src/content/docs/ may decide, so this page is scored.
        trap_docs = Path(tmp, "open-api", "code-samples", "clone", "src", "content", "docs")
        trap = trap_docs / guide_rel
        trap.parent.mkdir(parents=True, exist_ok=True)
        trap.write_text(_COMPLEX, encoding="utf-8")

        # 1. A code-samples page named explicitly is skipped, said so, and not scored.
        rc, out = run(["--files", cs])
        case("--files on a code-samples page prints SKIPPED with the reason",
             f"SKIPPED {cs_rel}  (not scored: " in out and "#285" in out)
        case("--files on a code-samples page is never reported as PASS or FAIL",
             scored_line(out, cs_rel) is None and "score=" not in out)
        case("--files on a code-samples page alone exits 0 (nothing scored, nothing over)",
             rc == 0, f"rc={rc}")

        # 2. The same complex content on an ordinary page is scored, and fails.
        rc, out = run(["--files", guide])
        line = scored_line(out, guide_rel)
        case("--files on an ordinary page is scored", line is not None)
        case("the complex fixture FAILS where it is scored, so the skip above is discriminating",
             rc == 1 and line is not None and "(FAIL," in line, f"rc={rc}")

        # 3. A plain ordinary page passes, so the checker is not failing everything.
        rc, out = run(["--files", plain])
        line = scored_line(out, plain_rel)
        case("the plain fixture is scored and PASSES",
             rc == 0 and line is not None and "(PASS," in line, f"rc={rc}")

        # 4. Mixed: the skip does not swallow the other files, and the exit code
        #    comes from the file that was scored.
        rc, out = run(["--files", cs, guide])
        case("mixed --files: one SKIPPED line, one FAIL line, exit 1",
             rc == 1 and f"SKIPPED {cs_rel}" in out
             and (scored_line(out, guide_rel) or "").find("(FAIL,") >= 0, f"rc={rc}")

        # 5. api-clients is NOT covered by #285, so a named page there is scored.
        rc, out = run(["--files", ac])
        case("--files on an api-clients page is still scored (#285 covers code-samples only)",
             rc == 1 and scored_line(out, ac_rel) is not None and "SKIPPED" not in out,
             f"rc={rc}")

        # 6. Matching is relative to the content root, not the absolute path.
        rc, out = run(["--files", str(trap)])
        case("a page whose PARENT folders are named open-api/code-samples is still scored",
             rc == 1 and scored_line(out, guide_rel) is not None and "SKIPPED" not in out,
             f"rc={rc}")

        # 7. Triage leaves out both areas and scores the two ordinary pages.
        jpath = Path(tmp, "triage.json")
        rc, out = run(["--dir", str(docs), "--out-json", str(jpath)])
        data = json.loads(jpath.read_text(encoding="utf-8")) if jpath.exists() else {}
        listed = [i["path"] for i in data.get("items", [])]
        case("triage scans exactly the 2 ordinary pages",
             data.get("total_scanned") == 2, f"total_scanned={data.get('total_scanned')}")
        case("triage lists the ordinary complex page and neither skipped area",
             listed == [guide_rel], f"items={listed}")

        # 8. "Could not look" is exit 2, never a pass.
        rc, out = run(["--files", str(docs / "pro" / "guides" / "missing.mdx")])
        case("a named file that does not exist exits 2, not 0", rc == 2, f"rc={rc}")
        bad = docs / "pro" / "guides" / "bad.mdx"
        bad.write_bytes(b"---\ntitle: X\n---\n\n\xff\xfe not utf-8\n")
        rc, out = run(["--files", str(bad)])
        case("a file that is not valid UTF-8 exits 2, not 0", rc == 2, f"rc={rc}")
        empty = Path(tmp, "empty")
        empty.mkdir()
        rc, out = run(["--dir", str(empty)])
        case("a triage scan that finds no files exits 2, not 0", rc == 2, f"rc={rc}")
        blocker = Path(tmp, "a-file")
        blocker.write_text("x", encoding="utf-8")
        rc, out = run(["--dir", str(docs), "--out-json", str(blocker / "out.json")])
        case("a crash exits 2, never Python's default 1, which means a page scored too high",
             rc == 2 and "CHECKER ERROR" in out, f"rc={rc}")

    failed = [c for c in cases if not c[1]]
    if failed:
        print(f"SELF-TEST FAILED: {len(failed)} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
