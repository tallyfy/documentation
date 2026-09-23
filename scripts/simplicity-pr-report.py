#!/usr/bin/env python3
"""
simplicity-pr-report.py

Runs scripts/simplicity-check.py on each documentation page a pull request
changes, and writes the scores as a markdown report. It is REPORT ONLY: a
score, however high, never changes the exit code. Owner decision on
tallyfy/documentation#291. Used by .github/workflows/readability-report.yml.

  In CI (the checkout is GitHub's test merge of the pull request):
    python3 scripts/simplicity-pr-report.py --pr-merge-commit --run-self-tests \
        --summary "$GITHUB_STEP_SUMMARY"

  --run-self-tests runs this script's self-test and, when the checker in the
  branch has one, the checker's --self-test too, before any page is scored.
  Either failing is a checker error, because scores from a broken tool mean
  nothing.

  By hand, on named pages:
    python3 scripts/simplicity-pr-report.py src/content/docs/pro/some-page.mdx

  Prove it can tell every outcome apart, including a broken checker:
    python3 scripts/simplicity-pr-report.py --self-test

Each page is checked in its own run of the checker, so one page that breaks it
is named on its own and cannot hide the others' scores.

Exit codes:
  0  the report was written. Every page was either scored or skipped.
  2  checker error. The checker could not score at least one page, or this
     script could not work out which pages changed. The report says "checker
     error" in plain words, so it is never mistaken for a score problem.
"""

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKER = "scripts/simplicity-check.py"
CONTENT_ROOT = "src/content/docs/"
TIMEOUT_SECONDS = 120

# The checker's per-page lines. A scored page prints
#   "<mark> <path>  score=<n>  (PASS|FAIL, threshold <t>)"
# and a page it leaves out on purpose prints
#   "SKIPPED <path>  (not scored: <reason>)"
SCORED_RE = r"^\S+ {path}  score=(?P<score>\d+(?:\.\d+)?)  \((?P<status>PASS|FAIL), threshold (?P<thr>\d+)\)$"
SKIPPED_RE = r"^SKIPPED {path}  \(not scored: (?P<why>.*)\)$"
BANNED_RE = re.compile(r"AI-tell words \(hard fail\): (?P<words>.+)$", re.M)


_INSIDE_SELF_TEST = False   # stops --run-self-tests re-running the self-test inside itself


class ReportError(Exception):
    """This script could not work out what to score."""


def changed_pages_from_merge_commit():
    """The .mdx pages that merging this pull request adds or changes.

    actions/checkout on a pull_request event checks out GitHub's test merge.
    Its first parent is the base branch, so HEAD^1..HEAD is exactly what the
    merge adds. Anything else checked out here would answer a different
    question, so it is an error rather than a guess."""
    parents = subprocess.run(["git", "rev-list", "--parents", "-n1", "HEAD"],
                             capture_output=True, text=True)
    if parents.returncode != 0:
        raise ReportError(f"git rev-list failed: {parents.stderr.strip()}")
    n = len(parents.stdout.split()) - 1
    if n != 2:
        raise ReportError(f"expected the pull request's merge commit, with 2 parents; HEAD has {n}")
    diff = subprocess.run(["git", "diff", "-z", "--name-only", "--diff-filter=d", "HEAD^1", "HEAD"],
                          capture_output=True)
    if diff.returncode != 0:
        raise ReportError(f"git diff failed: {diff.stderr.decode(errors='replace').strip()}")
    names = [p.decode("utf-8", errors="surrogateescape") for p in diff.stdout.split(b"\0") if p]
    return pages_only(names)


def pages_only(paths):
    return [p for p in paths if p.startswith(CONTENT_ROOT) and p.endswith(".mdx")]


def score_page(path, checker):
    """Run the checker on one page. Returns a dict with kind in
    {"scored", "skipped", "error"}."""
    rel = path.split(CONTENT_ROOT, 1)[-1]
    try:
        proc = subprocess.run([sys.executable, checker, "--files", path],
                              capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return {"kind": "error", "rel": rel, "why": f"timed out after {TIMEOUT_SECONDS}s"}
    except OSError as exc:
        return {"kind": "error", "rel": rel, "why": f"could not start the checker: {exc}"}

    out = proc.stdout
    esc = re.escape(rel)
    scored = re.search(SCORED_RE.format(path=esc), out, re.M)
    skipped = re.search(SKIPPED_RE.format(path=esc), out, re.M)
    last = " / ".join(l.strip() for l in (out + proc.stderr).strip().splitlines()[-3:]) or "no output"

    # A result only counts when the exit code agrees with it. An uncaught
    # Python exception also exits 1, so exit 1 alone is never read as a score.
    if scored and "Traceback" not in proc.stderr:
        status = scored.group("status")
        if (status == "PASS" and proc.returncode == 0) or (status == "FAIL" and proc.returncode == 1):
            banned = BANNED_RE.search(out)
            return {"kind": "scored", "rel": rel, "score": scored.group("score"),
                    "status": status, "threshold": int(scored.group("thr")),
                    "banned": banned.group("words").strip() if banned else ""}
    if skipped and proc.returncode == 0 and not scored:
        return {"kind": "skipped", "rel": rel, "why": skipped.group("why")}
    return {"kind": "error", "rel": rel, "why": f"exit {proc.returncode}, no usable result. Last output: {last}"}


def cell(text):
    """Markdown table cell text, with pipes and backticks made safe."""
    return str(text).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")


def page_cell(rel):
    """A page path as a code span. Inside a table a pipe still needs a backslash."""
    if "`" in rel:
        return cell(rel)
    return "`" + rel.replace("|", "\\|") + "`"


def render(results, selftest_note=""):
    lines = ["## Readability report (report only, never blocks a merge)", ""]
    if selftest_note:
        lines += [selftest_note, ""]
    errors = [r for r in results if r["kind"] == "error"]
    if not results:
        lines.append("This pull request changes no documentation pages, so there is nothing to score.")
        return "\n".join(lines) + "\n"

    lines += ["Each changed page, scored by `scripts/simplicity-check.py`. Lower is simpler. "
              "A page at or over the limit is worth a look, but nothing here stops a merge.", ""]
    lines += ["| Page | Score | Result |", "|---|---|---|"]
    for r in results:
        page = page_cell(r["rel"])
        if r["kind"] == "scored":
            if r["status"] == "PASS":
                result = f"under {r['threshold']}"
            elif r["banned"]:
                result = f"uses a banned word: {cell(r['banned'])}"
            else:
                result = f"{r['threshold']} or over, worth a look"
            lines.append(f"| {page} | {r['score']} | {result} |")
        elif r["kind"] == "skipped":
            lines.append(f"| {page} | not scored | skipped: {cell(r['why'])} |")
        else:
            lines.append(f"| {page} | not scored | **checker error** |")
    counts = {k: sum(1 for r in results if r["kind"] == k) for k in ("scored", "skipped", "error")}
    lines += ["", f"{len(results)} page(s) changed: {counts['scored']} scored, "
                  f"{counts['skipped']} skipped, {counts['error']} checker error(s)."]
    if errors:
        lines += ["", "### Checker error", "",
                  "The checker could not score the page(s) below. This is a problem with the "
                  "checker, not a score. The job fails for this reason only, so a broken checker "
                  "is seen and fixed rather than silently reporting nothing.", ""]
        lines += [f"- {page_cell(r['rel'])}: {cell(r['why'])}" for r in errors]
    return "\n".join(lines) + "\n"


def render_error(message):
    return ("## Readability report (report only, never blocks a merge)\n\n"
            "### Checker error\n\n"
            f"The report could not run: {cell(message)}\n\n"
            "This is a problem with the report, not a score. No page was scored.\n")


def last_line(text):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "no output"


def run_self_tests(checker):
    """Returns (ok, one line for the report)."""
    if _INSIDE_SELF_TEST:
        mine, mine_tail = 0, "SELF-TEST PASSED: not re-run inside its own self-test."
    else:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mine = self_test()
        mine_tail = last_line(buf.getvalue())
    if mine != 0 or "SELF-TEST PASSED" not in mine_tail:
        return False, f"this report's own self-test failed: {mine_tail}"
    helptext = subprocess.run([sys.executable, checker, "--help"], capture_output=True, text=True,
                              timeout=TIMEOUT_SECONDS)
    if helptext.returncode != 0:
        return False, f"the checker could not print its help (exit {helptext.returncode})"
    if "--self-test" not in helptext.stdout:
        return True, (f"Self-tests: this report, {mine_tail.rstrip('.')}. The checker in this "
                      "branch has no self-test, so none ran for it.")
    ck = subprocess.run([sys.executable, checker, "--self-test"], capture_output=True, text=True,
                        timeout=TIMEOUT_SECONDS, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    ck_tail = last_line(ck.stdout + ck.stderr)
    if ck.returncode != 0 or "SELF-TEST PASSED" not in ck.stdout:
        return False, f"the checker's self-test failed (exit {ck.returncode}): {ck_tail}"
    return True, (f"Self-tests: this report, {mine_tail.rstrip('.')}. "
                  f"The checker, {ck_tail.rstrip('.')}.")


def emit(text, summary):
    print(text)
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report readability scores for changed docs pages.")
    ap.add_argument("paths", nargs="*", help="pages to score, when not using --pr-merge-commit")
    ap.add_argument("--pr-merge-commit", action="store_true",
                    help="score the pages that HEAD, a pull request merge commit, adds or changes")
    ap.add_argument("--summary", default="", help="append the markdown report to this file")
    ap.add_argument("--run-self-tests", action="store_true",
                    help="run this script's and the checker's self-tests before scoring")
    ap.add_argument("--checker", default=CHECKER, help=argparse.SUPPRESS)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    try:
        if args.pr_merge_commit:
            if args.paths:
                raise ReportError("pass either --pr-merge-commit or page paths, not both")
            pages = changed_pages_from_merge_commit()
        else:
            pages = pages_only(args.paths)
            if args.paths and not pages:
                raise ReportError(f"none of the {len(args.paths)} path(s) given is an .mdx page under {CONTENT_ROOT}")
        if not os.path.isfile(args.checker):
            raise ReportError(f"checker not found at {args.checker}")
        note = ""
        if args.run_self_tests:
            ok, note = run_self_tests(args.checker)
            if not ok:
                raise ReportError(note)
        results = [score_page(p, args.checker) for p in pages]
    except ReportError as exc:
        emit(render_error(str(exc)), args.summary)
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash here is a checker error, never a pass
        emit(render_error(f"crashed: {exc!r}"), args.summary)
        return 2

    emit(render(results, note), args.summary)
    return 2 if any(r["kind"] == "error" for r in results) else 0


# ---------------------------------------------------------------------------
# Self-test. Each case runs main() against a stand-in checker that behaves one
# known way, and asserts the report names that outcome and nothing else.
# ---------------------------------------------------------------------------

FAKES = {
    "pass": 'print("\\u2713 pro/a b.mdx  score=12.0  (PASS, threshold 45)"); raise SystemExit(0)',
    "over": 'print("\\u274c pro/a b.mdx  score=51.8  (FAIL, threshold 45)"); raise SystemExit(1)',
    "banned": ('print("\\u274c pro/a b.mdx  score=20.0  (FAIL, threshold 45)")\n'
               'print("  \\u2514\\u2500 \\u26d4 AI-tell words (hard fail): leverage"); raise SystemExit(1)'),
    "skipped": 'print("SKIPPED pro/a b.mdx  (not scored: developer code reference)"); raise SystemExit(0)',
    "crash": 'raise RuntimeError("boom")',
    "silent": 'raise SystemExit(0)',
    "exit2": 'print("CHECKER ERROR: could not read"); raise SystemExit(2)',
    "wrongpage": 'print("\\u2713 pro/other.mdx  score=12.0  (PASS, threshold 45)"); raise SystemExit(0)',
    "lies": 'print("\\u2713 pro/a b.mdx  score=12.0  (PASS, threshold 45)"); raise SystemExit(1)',
    "failcrash": ('print("\\u274c pro/a b.mdx  score=51.8  (FAIL, threshold 45)", flush=True)\n'
                  'raise RuntimeError("boom after the score line")'),
    "skipcrash": ('print("SKIPPED pro/a b.mdx  (not scored: x)", flush=True)\n'
                  'raise RuntimeError("boom after the skip line")'),
    "ckselftestok": ('import sys\n'
                     'if "--help" in sys.argv: print("usage: x [--self-test]"); raise SystemExit(0)\n'
                     'if "--self-test" in sys.argv: print("SELF-TEST PASSED: 3 of 3 case(s)."); raise SystemExit(0)\n'
                     'print("\\u2713 pro/a b.mdx  score=12.0  (PASS, threshold 45)")'),
    "ckselftestbad": ('import sys\n'
                      'if "--help" in sys.argv: print("usage: x [--self-test]"); raise SystemExit(0)\n'
                      'if "--self-test" in sys.argv: print("SELF-TEST FAILED: 1 of 3 case(s)."); raise SystemExit(1)\n'
                      'print("\\u2713 pro/a b.mdx  score=12.0  (PASS, threshold 45)")'),
}


def self_test():
    global _INSIDE_SELF_TEST
    _INSIDE_SELF_TEST = True
    try:
        return _self_test()
    finally:
        _INSIDE_SELF_TEST = False


def _self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        print(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    print("Self-test: proving the report tells a score, a skip and a broken checker apart.")
    with tempfile.TemporaryDirectory() as tmp:
        page = f"{CONTENT_ROOT}pro/a b.mdx"   # a space in the path, on purpose

        def run(kind, paths=(page,), extra=()):
            fake = Path(tmp, f"fake-{kind}.py")
            fake.write_text(FAKES[kind] + "\n", encoding="utf-8")
            summary = Path(tmp, f"summary-{kind}.md")
            summary.write_text("", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--checker", str(fake), "--summary", str(summary), *extra, *paths])
            return rc, summary.read_text(encoding="utf-8")

        rc, s = run("pass")
        case("a passing page is reported with its score, exit 0",
             rc == 0 and "| `pro/a b.mdx` | 12.0 | under 45 |" in s, f"rc={rc}")
        rc, s = run("over")
        case("a page over the limit is reported, and the exit code is still 0",
             rc == 0 and "| `pro/a b.mdx` | 51.8 | 45 or over, worth a look |" in s
             and "### Checker error" not in s and "**checker error**" not in s, f"rc={rc}")
        rc, s = run("banned")
        case("a banned word is reported as such, exit 0",
             rc == 0 and "uses a banned word: leverage" in s, f"rc={rc}")
        rc, s = run("skipped")
        case("a skipped page says skipped and why, never a score",
             rc == 0 and "| `pro/a b.mdx` | not scored | skipped: developer code reference |" in s, f"rc={rc}")
        for kind, what in (("crash", "a crash, which exits 1 like a high score"),
                           ("silent", "a checker that prints nothing and exits 0"),
                           ("exit2", "a checker that exits 2"),
                           ("wrongpage", "a result line for a different page"),
                           ("lies", "a PASS line with exit code 1"),
                           ("failcrash", "a FAIL line followed by a crash, which also exits 1"),
                           ("skipcrash", "a SKIPPED line followed by a crash")):
            rc, s = run(kind)
            case(f"{what} is a checker error, exit 2",
                 rc == 2 and "**checker error**" in s and "### Checker error" in s
                 and "under 45" not in s, f"rc={rc}")
        rc, s = run("pass", paths=())
        case("no changed pages says so plainly, exit 0",
             rc == 0 and "changes no documentation pages" in s, f"rc={rc}")
        rc, s = run("pass", paths=("README.md", "src/content/docs/pro/image.png"))
        case("paths that are not docs pages are a report error, never a silent empty report",
             rc == 2 and "Checker error" in s, f"rc={rc}")
        rc, s = run("ckselftestok", extra=("--run-self-tests",))
        case("--run-self-tests with a checker whose self-test passes says so, then scores",
             rc == 0 and "The checker, SELF-TEST PASSED: 3 of 3" in s and "| 12.0 | under 45 |" in s,
             f"rc={rc}")
        rc, s = run("ckselftestbad", extra=("--run-self-tests",))
        case("--run-self-tests with a failing checker self-test is a checker error, and scores nothing",
             rc == 2 and "self-test failed" in s and "Checker error" in s and "12.0" not in s, f"rc={rc}")
        rc, s = run("pass", extra=("--run-self-tests",))
        case("--run-self-tests with a checker that has no self-test says so plainly, then scores",
             rc == 0 and "has no self-test" in s and "| 12.0 | under 45 |" in s, f"rc={rc}")
        rc, s = run("pass", paths=(page, "README.md"))
        case("non-page paths mixed with a page are ignored, and the page is scored",
             rc == 0 and "1 page(s) changed: 1 scored" in s, f"rc={rc}")

    if not all(cases):
        print(f"SELF-TEST FAILED: {cases.count(False)} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
