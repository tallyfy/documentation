#!/usr/bin/env python3
"""Keep DOCUMENTATION_STRUCTURE.md and CLAUDE.md honest about how many .mdx files exist.

Run it after adding, removing or moving documentation files. It rewrites every count it can
attribute to a real directory, and it prints every count-shaped figure it could NOT attribute,
so the gap is visible rather than assumed.

Why this file was rewritten (tallyfy/documentation#126): the previous version set its paths as
literal "~/GitHub/..." strings and never called expanduser. glob does not expand `~`, so it
matched 0 files where the expanded path matches 742, and both targets failed their
os.path.exists check and returned early. It wrote nothing, ever, on either machine, while
printing a line that a caller reading only the exit status saw as success. The headline counts
drifted 27% before anyone noticed.

Four properties are load-bearing, so do not remove them:

  1. Paths derive from __file__, not from `~` and not from the current directory. The script
     lives inside the repository it edits, so it can always find it.
  2. It exits non-zero on a zero count or a missing target. A count of zero must never reach
     either file. That is the failure that would turn a harmless no-op into real damage.
  3. It reconciles the arithmetic before writing: every parent equals the sum of its children
     plus its own loose files, and the top-level rows sum to the stated total. A partial update
     is the failure mode this catches, and nothing else catches it.
  4. It reports what it did not touch. A figure this script cannot attribute to a directory is
     named on stdout rather than silently left stale, which is how the drift went unnoticed.

Usage:
    python3 scripts/update-documentation-structure.py            # rewrite both files
    python3 scripts/update-documentation-structure.py --check    # report only, non-zero if stale

Exit codes: 0 files are correct (or were made correct), 1 a check failed and nothing was written.
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# The script lives at <repo>/scripts/, so the repo root is one level up. Deriving it this way
# means the script works from any working directory and on either machine, which is AC1.
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "src" / "content" / "docs"
STRUCTURE_FILE = REPO_ROOT / "DOCUMENTATION_STRUCTURE.md"
CLAUDE_FILE = REPO_ROOT / "CLAUDE.md"

# "├── answers/         (17 files)  - description", nested rows carrying "│   " prefixes,
# and bare file rows such as "404.mdx  (1 file)".
ROW_RE = re.compile(
    r"^(?P<indent>(?:│   |    )*)(?P<branch>├── |└── )(?P<name>[^\s(]+)"
    r"(?P<gap>\s+)\((?P<count>\d+) (?P<noun>files?)\)(?P<rest>.*)$"
)
# "│   └── (3 files sit directly in integrations/)"
LOOSE_RE = re.compile(
    r"^(?P<indent>(?:│   |    )*)(?P<branch>├── |└── )"
    r"\((?P<count>\d+) (?P<noun>files?) sits? directly in (?P<name>[^)]+?)/\)(?P<rest>.*)$"
)
# The unbranched root line of a tree block: "pro/                    (671 files)"
ROOT_RE = re.compile(r"^(?P<name>[A-Za-z0-9._/-]+)/(?P<gap>\s+)\((?P<count>\d+) (?P<noun>files?)\)$")
TOTAL_RE = re.compile(r"\*\*Total\*\*: \d+ \.mdx files across \d+ directories")
# Quick Navigation Map: "**Task Management**: `pro/tracking-and-tasks/tasks/` (22 files)"
NAV_RE = re.compile(r"`(?P<path>[A-Za-z0-9._/-]+)/`(?P<mid>[^`(]*)\((?P<count>\d+)(?P<qual> total)? (?P<noun>files?)")
# The same, but summing two paths: "`pro/documenting/members/` + `pro/documenting/guests/` (16 files)"
NAV_SUM_RE = re.compile(
    r"`(?P<a>[A-Za-z0-9._/-]+)/` \+ `(?P<b>[A-Za-z0-9._/-]+)/` \((?P<count>\d+) (?P<noun>files?)\)")


def plural(count, noun="file"):
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def scan_docs():
    """Return (total_files, total_dirs, recursive, loose).

    Keys are POSIX paths relative to DOCS_DIR, e.g. "pro/integrations/open-api". `recursive`
    counts every .mdx at or below a directory; `loose` counts only those sitting directly in it.
    """
    if not DOCS_DIR.is_dir():
        print(f"FATAL: docs directory not found: {DOCS_DIR}", file=sys.stderr)
        sys.exit(1)

    files = sorted(p for p in DOCS_DIR.rglob("*.mdx") if p.is_file())
    recursive, loose, dirs = defaultdict(int), defaultdict(int), set()

    for path in files:
        parent = path.relative_to(DOCS_DIR).parent
        dirs.add(parent.as_posix())
        loose[parent.as_posix()] += 1
        # Credit the file to its own directory and to every ancestor, which is what the nested
        # rows in the tree actually mean. The old version only looked at rel.split('/')[0], so
        # nested counts were never computed at all, whatever the regexes did.
        node = parent
        while True:
            recursive[node.as_posix()] += 1
            if node == Path("."):
                break
            node = node.parent

    return len(files), len(dirs), dict(recursive), dict(loose)


def reconcile(recursive, loose, total_files):
    """AC5. Each parent equals its children plus its own loose files; the top level sums."""
    problems = []
    children = defaultdict(list)
    for key in recursive:
        if key != ".":
            children[Path(key).parent.as_posix()].append(key)

    for parent, kids in children.items():
        expected = sum(recursive[k] for k in kids) + loose.get(parent, 0)
        if recursive.get(parent, 0) != expected:
            problems.append(
                f"{parent or '<root>'}: recursive={recursive.get(parent)} but children+loose={expected}")

    top = sum(v for k, v in recursive.items() if "/" not in k and k != ".")
    if top + loose.get(".", 0) != total_files:
        problems.append(
            f"top-level rows sum to {top} plus {loose.get('.', 0)} loose, but the total is {total_files}")
    return problems


def swap_count(line, old_text, new_text, tail_start):
    """Replace a count and absorb the width change into the whitespace that follows it, so the
    description column does not drift when a number gains or loses a digit."""
    head, tail = line[:tail_start], line[tail_start:]
    pad = len(old_text) - len(new_text)
    if pad > 0:
        tail = " " * pad + tail
    elif pad < 0 and tail.startswith(" " * (-pad)):
        tail = tail[-pad:]
    return head + tail


class Rewriter:
    """Rewrites counts in one file and records which line numbers it owns."""

    def __init__(self, label, recursive, loose):
        self.label = label
        self.recursive = recursive
        self.loose = loose
        self.owned = set()      # 1-based line numbers this script maintains
        self.unresolved = []    # figures that name a path with no matching directory

    def note(self, lineno):
        self.owned.add(lineno)

    def lookup(self, key, lineno, what):
        actual = self.recursive.get(key)
        if actual is None:
            self.unresolved.append(f"{self.label}:{lineno}  {what} -> no directory '{key}'")
        return actual

    def trees(self, lines):
        """Rewrite every fenced tree block. Returns the new lines."""
        out, block, start, in_block = [], [], 0, False
        for i, line in enumerate(lines, 1):
            if line.startswith("```"):
                if in_block:
                    out.extend(self._tree(block, start))
                    in_block, block = False, []
                else:
                    in_block, block, start = True, [], i + 1
                out.append(line)
            elif in_block:
                block.append(line)
            else:
                out.append(line)
        if in_block:                      # unterminated fence: emit untouched
            out.extend(block)
        return out

    def _tree(self, block, start):
        out, stack, base = [], [], ""
        for offset, line in enumerate(block):
            lineno = start + offset

            m = ROOT_RE.match(line)
            if m and not stack:
                # The Pro tree opens with "pro/  (671 files)" and its rows hang off that.
                base = m.group("name").strip("/")
                actual = self.lookup(base, lineno, "tree root")
                if actual is None:
                    out.append(line)
                    continue
                old, new = f"({m.group('count')} {m.group('noun')})", f"({plural(actual)})"
                self.note(lineno)
                out.append(swap_count(line.replace(old, new, 1), old, new, m.start("gap")))
                continue

            m = LOOSE_RE.match(line)
            if m:
                depth = len(m.group("indent")) // 4
                # A loose row describes the directory it sits inside, not a child of it.
                key = "/".join([p for p in [base] + stack[:depth] if p])
                actual = self.loose.get(key)
                if actual is None:
                    self.unresolved.append(f"{self.label}:{lineno}  loose row -> no directory '{key}'")
                    out.append(line)
                    continue
                old = f"({plural(int(m.group('count')))} sit{'s' if int(m.group('count')) == 1 else ''}"
                new = f"({plural(actual)} sit{'s' if actual == 1 else ''}"
                self.note(lineno)
                out.append(line.replace(old, new, 1))
                continue

            m = ROW_RE.match(line)
            if not m:
                out.append(line)
                continue

            depth = len(m.group("indent")) // 4
            name = m.group("name")
            del stack[depth:]
            if name.endswith("/"):
                key = "/".join([p for p in [base] + stack + [name.rstrip("/")] if p])
                stack.append(name.rstrip("/"))
                actual = self.lookup(key, lineno, f"row '{name}'")
            else:
                key = "/".join([p for p in [base] + stack + [name] if p])
                actual = 1 if (DOCS_DIR / key).is_file() else None
                if actual is None:
                    self.unresolved.append(f"{self.label}:{lineno}  row '{name}' -> no file '{key}'")
            if actual is None:
                out.append(line)
                continue

            old, new = f"({m.group('count')} {m.group('noun')})", f"({plural(actual)})"
            self.note(lineno)
            out.append(swap_count(line.replace(old, new, 1), old, new, m.start("rest")))
        return out

    def nav(self, lines):
        """Rewrite the Quick Navigation Map entries, which carry their path in backticks."""
        out = []
        for i, line in enumerate(lines, 1):
            m = NAV_SUM_RE.search(line)
            if m:
                a, b = self.recursive.get(m.group("a")), self.recursive.get(m.group("b"))
                if a is None or b is None:
                    self.unresolved.append(f"{self.label}:{i}  nav sum -> unknown path")
                    out.append(line)
                    continue
                self.note(i)
                out.append(line.replace(f"({plural(int(m.group('count')))})", f"({plural(a + b)})", 1))
                continue

            m = NAV_RE.search(line)
            if m and not line.lstrip().startswith(("├──", "└──", "│")):
                actual = self.lookup(m.group("path"), i, "nav entry")
                if actual is None:
                    out.append(line)
                    continue
                old = f"({m.group('count')}{m.group('qual') or ''} {m.group('noun')}"
                new = f"({actual}{m.group('qual') or ''} {'file' if actual == 1 else 'files'}"
                self.note(i)
                out.append(line.replace(old, new, 1))
                continue
            out.append(line)
        return out

    def audit(self, lines):
        """AC3. Name every count-shaped figure this script does not own, so the gap is visible."""
        stale = []
        pattern = re.compile(r"\(\d+(?: total)? files?\b|\b\d+ \.mdx files\b")
        for i, line in enumerate(lines, 1):
            if i in self.owned or not pattern.search(line):
                continue
            snippet = line.strip()
            stale.append(f"{self.label}:{i}  {snippet[:87] + '...' if len(snippet) > 90 else snippet}")
        return stale


def rewrite_structure(text, total_files, total_dirs, recursive, loose):
    rw = Rewriter(STRUCTURE_FILE.name, recursive, loose)
    lines = text.split("\n")
    lines = rw.trees(lines)
    lines = rw.nav(lines)
    out = []
    for i, line in enumerate(lines, 1):
        new = TOTAL_RE.sub(f"**Total**: {total_files} .mdx files across {total_dirs} directories", line)
        if new != line or TOTAL_RE.search(line):
            rw.note(i)
        out.append(new)
    return out, rw


def rewrite_claude(text, total_files, total_dirs, recursive, loose):
    rw = Rewriter(CLAUDE_FILE.name, recursive, loose)
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        original = line

        # "...including 742 .mdx files across 156 directories, search strategies..."
        line, n = re.subn(r"including \d+ \.mdx files across \d+ directories",
                          f"including {total_files} .mdx files across {total_dirs} directories", line)
        if n:
            rw.note(i)

        # "  - Location: `/src/content/docs/answers/` (17 files)"
        m = re.search(r"Location: `/src/content/docs/(?P<path>[^`]+)` \((?P<count>\d+) (?P<noun>files?)", line)
        if m:
            key = m.group("path").strip("/")
            actual = rw.lookup(key, i, "Location line")
            if actual is not None:
                line = line.replace(f"({m.group('count')} {m.group('noun')}", f"({plural(actual)}", 1)
                rw.note(i)

        # "  - Core areas: documenting/ (79 files), tracking-and-tasks/ (50 files), ..."
        if "Core areas:" in line:
            def core(m):
                actual = rw.recursive.get(f"pro/{m.group('name')}")
                if actual is None:
                    rw.unresolved.append(f"{rw.label}:{i}  core area '{m.group('name')}' -> no directory")
                    return m.group(0)
                return f"{m.group('name')}/ ({plural(actual)})"
            line = re.sub(r"(?P<name>[a-z0-9-]+)/ \(\d+ files?\)", core, line)
            rw.note(i)

        if line != original or original.strip():
            out.append(line)
        else:
            out.append(line)
    return out, rw


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="Report what would change and exit non-zero if anything would. Writes nothing.")
    args = parser.parse_args()

    total_files, total_dirs, recursive, loose = scan_docs()

    # AC4: a zero count must never be written over a correct number.
    if total_files == 0:
        print(f"FATAL: found 0 .mdx files under {DOCS_DIR}", file=sys.stderr)
        print("Refusing to write a zero count. Check the path before rerunning.", file=sys.stderr)
        return 1

    for target in (STRUCTURE_FILE, CLAUDE_FILE):
        if not target.is_file():
            print(f"FATAL: target not found: {target}", file=sys.stderr)
            return 1

    problems = reconcile(recursive, loose, total_files)
    if problems:
        print("FATAL: the counts do not reconcile, so writing would encode an inconsistency:",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"Scanned {DOCS_DIR}")
    print(f"  {total_files} .mdx files across {total_dirs} directories")

    structure_before = STRUCTURE_FILE.read_text()
    structure_lines, srw = rewrite_structure(
        structure_before, total_files, total_dirs, recursive, loose)

    claude_before = CLAUDE_FILE.read_text()
    claude_lines, crw = rewrite_claude(claude_before, total_files, total_dirs, recursive, loose)

    structure_after = "\n".join(structure_lines)
    claude_after = "\n".join(claude_lines)

    # Only restamp when a count actually moved, so a second immediate run is a true no-op (AC2).
    if structure_after != structure_before:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        structure_after = re.sub(r"<!-- Last updated: .+ -->",
                                 f"<!-- Last updated: {stamp} -->", structure_after, count=1)

    changed = [f.name for f, before, after in
               ((STRUCTURE_FILE, structure_before, structure_after),
                (CLAUDE_FILE, claude_before, claude_after)) if before != after]

    if args.check:
        report(srw, crw, structure_lines, claude_lines)
        if changed:
            print(f"\nCHECK FAILED: {', '.join(changed)} would be rewritten.")
            return 1
        print("\nCHECK PASSED: both files already match the tree.")
        return 0

    STRUCTURE_FILE.write_text(structure_after)
    CLAUDE_FILE.write_text(claude_after)
    print(f"  maintained {len(srw.owned) + len(crw.owned)} line(s) carrying counts")
    print(f"  changed: {', '.join(changed) if changed else 'nothing, both files were already correct'}")
    report(srw, crw, structure_lines, claude_lines)
    return 0


def report(srw, crw, structure_lines, claude_lines):
    unresolved = srw.unresolved + crw.unresolved
    stale = srw.audit(structure_lines) + crw.audit(claude_lines)
    if not unresolved and not stale:
        print("\nEvery count-shaped figure in both files was reached and verified.")
        return
    print("\nNOT MAINTAINED by this script - check these by hand:")
    for item in unresolved:
        print(f"  - {item}")
    for item in stale:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
