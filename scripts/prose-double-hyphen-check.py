#!/usr/bin/env python3
"""Find a double hyphen used as a dash in documentation prose.

WHY THIS EXISTS (tallyfy/documentation#287)

Some articles wrote ` -- ` where a dash belongs. The site's renderer turns that into an em
dash, which the house writing rules ban (CLAUDE.md, DOCS-VOICE.md). The renderer setting is
being changed separately (tallyfy/support-docs#272), and after that a ` -- ` is shown raw. So
the prose has to carry none before the renderer changes, and this script is how anyone can
check that, now and later.

WHAT IT COUNTS

A run of exactly two hyphens with whitespace, or the start or end of a line, on BOTH sides:
`permanent -- the API`. That is the shape the issue counted. It deliberately does not match:

  - `--data`, `--files` and other command flags, because a letter follows the hyphens,
  - `---` (a horizontal rule or a front matter fence), because a third hyphen follows,
  - `<!--` and `-->`, because a `!` or a `>` sits next to the hyphens.

WHERE IT LOOKS

Only prose. Before matching, these regions are overwritten with a filler character of the same
length, keeping every newline, so a reported line number is the real line in the file:

  - the front matter block,
  - fenced code blocks (``` or ~~~, closed by a fence of the same character at least as long;
    an unclosed fence is masked to the end of the file, because masking too much can only hide
    a finding, while masking too little invents one),
  - inline code spans, of any number of backticks,
  - HTML comments and MDX comments,
  - JSX and HTML tags themselves, attributes included (the text between tags is still prose),
  - table separator rows (`|---|---|`). Table BODY cells are prose and are counted.

The `## Related articles` section and every <CardGrid> are not counted, because they are
regenerated from the Answers API on each staging pipeline run and a human cannot fix them
here. That exclusion is never silent: every run prints how many matches it skipped there.

MODES

  --self-test   Prove the counter goes red on a planted prose line and stays green on the
                same characters in a code fence, in inline code and in a command flag.
  (default)     Scan --dir (default src/content/docs), or only the --files named.

EXIT CODES (as DOCS-VOICE.md sets for the checkers in this repository)
  0  clean
  1  findings
  2  the counter could not run: no files found, a named file unreadable, or a crash.
     A 2 is never a pass.
"""

import argparse
import contextlib
import io
import os
import re
import sys
import tempfile

DEFAULT_DIR = "src/content/docs"

# Not a space and not a hyphen, so a masked region can never complete a match next to it.
FILLER = "\x00"

DASH_RE = re.compile(r"(?<!\S)--(?!\S)")

FENCE_OPEN_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
MDX_COMMENT_RE = re.compile(r"\{/\*.*?\*/\}", re.S)
# A code span: a run of N backticks, then anything that does not cross a blank line, then a
# run of exactly N backticks. Neither run may touch another backtick.
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)\1(?!`)", re.S)
# A separator row holds only pipes, hyphens, colons and spaces, with at least one pipe.
TABLE_SEPARATOR_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$|"
                                r"^[ \t]*\|[ \t]*:?-+:?[ \t]*\|[ \t]*$", re.M)
# A JSX or HTML tag with quoted attribute values understood, the same shape
# scripts/ai-tell-check.py uses: a `>` inside `header="<b>A > B</b>"` does not end the tag.
_JSX_ATTR = (
    r"""(?:\s+[A-Za-z_:][-\w:.]*(?:\s*=\s*"""
    r"""(?:"[^"]*"|'[^']*'|\{(?:[^{}]|\{[^{}]*\})*\}|[^\s"'>`]+))?)*"""
)
JSX_TAG_RE = re.compile(r"</?[A-Za-z][-\w.:]*" + _JSX_ATTR + r"\s*/?>")
CARDGRID_RE = re.compile(r"<CardGrid\b[^>]*>.*?</CardGrid>", re.S | re.I)
RELATED_HEADING_RE = re.compile(r"^[ \t]{0,3}##[ \t]+Related articles[ \t]*$", re.M | re.I)
NEXT_H2_RE = re.compile(r"^[ \t]{0,3}##[ \t]+", re.M)


class CouldNotRun(Exception):
    """Raised for anything that means the count is not trustworthy. Maps to exit 2."""


def _blank(chars, start, end):
    for i in range(max(0, start), min(end, len(chars))):
        if chars[i] != "\n":
            chars[i] = FILLER


def _line_spans(raw):
    """(start, end_without_newline, end_with_newline) for every line."""
    spans, pos = [], 0
    for line in raw.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        spans.append((pos, pos + len(body), pos + len(line)))
        pos += len(line)
    return spans


def mask(raw):
    """Return (prose, generated): two strings the same length as raw.

    prose has every non-prose region filled. generated keeps only the machine-generated
    Related articles regions, masked the same way, so matches there can be reported apart.
    """
    chars = list(raw)

    # Front matter: the file opens with a `---` line and a later `---` line closes it.
    lines = _line_spans(raw)
    if lines and raw[lines[0][0]:lines[0][1]].strip() == "---":
        for start, end, _ in lines[1:]:
            if raw[start:end].strip() == "---":
                _blank(chars, 0, end)
                break

    # Fenced code, line by line, so the closing rule is the real one: same character, at
    # least as many of it, and nothing but spaces around it on the line.
    i = 0
    while i < len(lines):
        start, end, _ = lines[i]
        if chars[start:end] and all(c == FILLER for c in chars[start:end]):
            i += 1
            continue
        m = FENCE_OPEN_RE.match(raw[start:end])
        if not m or (m.group(1)[0] == "`" and "`" in m.group(2)):
            i += 1
            continue
        fence = m.group(1)
        close_re = re.compile(r"^[ \t]*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$")
        j = i + 1
        while j < len(lines) and not close_re.match(raw[lines[j][0]:lines[j][1]]):
            j += 1
        last = lines[min(j, len(lines) - 1)][1]
        _blank(chars, start, last)
        i = j + 1

    def blank_matches(regex):
        text = "".join(chars)
        for m in regex.finditer(text):
            _blank(chars, m.start(), m.end())

    blank_matches(HTML_COMMENT_RE)
    blank_matches(MDX_COMMENT_RE)
    blank_matches(INLINE_CODE_RE)
    blank_matches(TABLE_SEPARATOR_RE)

    # Split off the generated regions before tags are blanked, because finding them needs
    # the tags. Their text goes to `generated`, never to `prose`.
    text = "".join(chars)
    gen_keep = [False] * len(chars)
    regions = [(m.start(), m.end()) for m in CARDGRID_RE.finditer(text)]
    m = RELATED_HEADING_RE.search(text)
    if m:
        nxt = NEXT_H2_RE.search(text, m.end())
        regions.append((m.start(), nxt.start() if nxt else len(text)))
    for s, e in regions:
        for k in range(s, e):
            gen_keep[k] = True

    blank_matches(JSX_TAG_RE)

    prose = ["\n" if c == "\n" else (FILLER if gen_keep[k] else c) for k, c in enumerate(chars)]
    generated = ["\n" if c == "\n" else (c if gen_keep[k] else FILLER) for k, c in enumerate(chars)]
    return "".join(prose), "".join(generated)


def find(raw):
    """Return (findings, generated_count). A finding is (line_number, line_text)."""
    prose, generated = mask(raw)
    starts = [0] + [m.end() for m in re.finditer(r"\n", raw)]
    raw_lines = raw.split("\n")

    def line_of(offset):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    findings = []
    for m in DASH_RE.finditer(prose):
        n = line_of(m.start())
        findings.append((n, raw_lines[n - 1]))
    return findings, len(DASH_RE.findall(generated))


def discover(root):
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".mdx"):
                paths.append(os.path.join(dirpath, name))
    return paths


def run(paths, quiet=False):
    """Count over paths. Returns (exit_code, total, files_with_findings)."""
    if not paths:
        raise CouldNotRun("0 files to scan, so nothing was checked")
    total, hit_files, generated_total = 0, 0, 0
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise CouldNotRun(f"could not read {path}: {exc}")
        findings, generated = find(raw)
        generated_total += generated
        if findings:
            hit_files += 1
            total += len(findings)
            if not quiet:
                for line_no, text in findings:
                    print(f"{path}:{line_no}: {text.strip()[:160]}")
    if not quiet:
        print(f"\nSUMMARY: {len(paths)} file(s) scanned, {total} prose double hyphen(s) in "
              f"{hit_files} file(s).")
        print(f"Not counted: {generated_total} in generated `## Related articles` / <CardGrid> "
              f"regions, which the staging pipeline rewrites.")
    return (1 if total else 0), total, hit_files


# ---------------------------------------------------------------------------------------
# self-test: the counter must go red on a planted prose line, and stay green on the same
# characters where they are code. A self-test that only ever passes proves nothing.

def self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append((name, ok))
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))

    def lines_found(text):
        return [n for n, _ in find(text)[0]]

    print("prose-double-hyphen-check self-test")

    planted = "---\ntitle: x\n---\n\nDeleting a tag is permanent -- the API uses a hard delete.\n"
    case("a planted prose line is found, on its real line", lines_found(planted) == [5],
         str(lines_found(planted)))

    # A blank line inside each fence below stops the inline-code pattern from spanning the
    # fence, so these cases fail if fence masking alone breaks.
    fenced = "Intro.\n\n```bash\ncurl --data '{}' https://x\n\necho a -- b\n```\n\nOutro.\n"
    case("`--data` and `a -- b` inside a code fence are not found", lines_found(fenced) == [])

    inline = "Run `a -- b` and then ``x -- ` y`` to see it.\n"
    case("`a -- b` inside inline code, single and double backticks, is not found",
         lines_found(inline) == [])

    flag = "Pass --data to curl, or use --files with the script.\n"
    case("a command flag written in prose is not a dash", lines_found(flag) == [])

    fm = "---\ndescription: Tallyfy does this -- and that.\n---\n\nBody.\n"
    case("front matter is not counted", lines_found(fm) == [])

    table = "| a | b |\n| -- | -- |\n| x | text -- more |\n"
    case("a table separator row is not counted, a table body cell is",
         lines_found(table) == [3], str(lines_found(table)))

    tilde = "~~~\na -- b\n~~~\nafter -- this\n"
    case("a tilde fence is masked and the line after it is counted",
         lines_found(tilde) == [4], str(lines_found(tilde)))

    unclosed = "Before.\n\n```js\n// token expired -- retry\n"
    case("an unclosed fence is masked to the end of the file", lines_found(unclosed) == [])

    short_close = "````md\n```\na -- b\n````\nreal -- dash\n"
    case("a fence closes only on a fence at least as long",
         lines_found(short_close) == [5], str(lines_found(short_close)))

    indented = "<Steps>\n1. Do it.\n   ```bash\n\n   tool --x -- y\n   ```\n2. Then -- this.\n</Steps>\n"
    case("an indented fence inside a list is masked, the prose step is counted",
         lines_found(indented) == [7], str(lines_found(indented)))

    comments = "<!-- a -- b -->\n{/* c -- d */}\n---\n\nText.\n"
    case("HTML and MDX comments and a horizontal rule are not counted", lines_found(comments) == [])

    jsx = '<Aside title="One -- two">\nInside -- prose.\n</Aside>\n'
    case("a JSX attribute is not counted, the text inside the component is",
         lines_found(jsx) == [2], str(lines_found(jsx)))

    related = ("Body.\n\n## Related articles\n<CardGrid>\n"
               '<LinkTitleCard header="<b>A > B</b>" href="/x/" > Card -- text. </LinkTitleCard>\n'
               "</CardGrid>\n")
    found, generated = find(related)
    case("the Related articles block is not counted, but it is reported",
         found == [] and generated == 1, f"found={found} generated={generated}")

    two = "One -- two -- three.\n"
    case("two on one line count as two", len(find(two)[0]) == 2)

    case("a clean file reads 0", lines_found("Plain prose, with a comma.\n") == [])

    # The real command-line path, on real files, including the exit codes.
    with tempfile.TemporaryDirectory() as tmp:
        dirty = os.path.join(tmp, "dirty.mdx")
        clean = os.path.join(tmp, "clean.mdx")
        with open(dirty, "w", encoding="utf-8") as fh:
            fh.write(planted + fenced)
        with open(clean, "w", encoding="utf-8") as fh:
            fh.write(fenced + inline)
        case("exit 1 when a named file has a finding", main(["--files", dirty, "--quiet"]) == 1)
        case("exit 0 when the named files are clean", main(["--files", clean, "--quiet"]) == 0)
        case("a comma-joined --files list is split into its paths",
             run_count([f"{clean},{dirty}"]) == (1, 1))
        # The two "could not run" cases print to stderr. That text is captured and checked
        # here, so a CI log never shows a COULD NOT RUN line from a self-test that passed.
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["--files", os.path.join(tmp, "missing.mdx"), "--quiet"])
        case("exit 2 when a named file cannot be read, and it says so",
             rc == 2 and "COULD NOT RUN: could not read" in err.getvalue(), f"rc={rc}")
        empty = os.path.join(tmp, "empty")
        os.mkdir(empty)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = main(["--dir", empty, "--quiet"])
        case("exit 2 when the directory holds no .mdx files, and it says so",
             rc == 2 and "COULD NOT RUN: 0 files" in err.getvalue(), f"rc={rc}")
        case("--dir finds the planted line under it", main(["--dir", tmp, "--quiet"]) == 1)

    failed = [name for name, ok in cases if not ok]
    if failed:
        print(f"SELF-TEST FAILED: {len(failed)} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} case(s).")
    return 0


def _split_files(values):
    out = []
    for value in values:
        out.extend(p for p in re.split(r"[,\s]+", value) if p)
    return out


def run_count(files):
    """Helper for the self-test: (total, files_with_findings) for a --files list."""
    _, total, hit_files = run(_split_files(files), quiet=True)
    return total, hit_files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", default=None, help=f"directory to scan (default {DEFAULT_DIR})")
    parser.add_argument("--files", nargs="+", help="only these files (space or comma separated)")
    parser.add_argument("--quiet", action="store_true", help="print nothing, set the exit code")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            return self_test()
        if args.files is not None:
            paths = _split_files(args.files)
        else:
            root = args.dir or DEFAULT_DIR
            if not os.path.isdir(root):
                raise CouldNotRun(f"{root} is not a directory")
            paths = discover(root)
        code, _, _ = run(paths, quiet=args.quiet)
        return code
    except CouldNotRun as exc:
        print(f"COULD NOT RUN: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # a crash is "could not look", never a finding and never a pass
        print(f"COULD NOT RUN: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
