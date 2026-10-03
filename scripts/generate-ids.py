#!/usr/bin/env python3
"""
generate-ids.py - give every documentation page that lacks one an Answers id.

    python scripts/generate-ids.py --dir=$PWD               reconcile the whole tree
    python scripts/generate-ids.py --dir=$PWD --dry-run     report only, write nothing
    python scripts/generate-ids.py --self-test [--target PATH]

WHOLE TREE, EVERY RUN (owner decision 218, 2026-10-03, tallyfy/documentation#296 criterion 2).
Until then this script got the pages one commit added (`git diff-tree --diff-filter=A`), so a
push whose run was dropped from the concurrency queue, or failed, left its new pages without an
id for good. Measured 2026-10-03 on staging 278b8bc7b: 593 indexable pages, 592 with an id and
one, pro/integrations/mcp-server/google-gemini/index.mdx, still carrying the all-zero
placeholder it was written with on 2026-01-15. Reading the tree instead of a commit means the
next run picks up whatever an earlier run missed, with no stored state.

WHICH PAGES. Every `.mdx` under src/content/docs except pro/changelog/** and 404.mdx, the same
exclusions as answers-connector.py, which never indexes them. A page lacks an id when its front
matter has no `id`, an empty one, or an id made only of zeros: CLAUDE.md tells authors to write
new pages with a placeholder of zeros, and PyYAML reads the unquoted 34-zero form as the integer
0. Any other id is kept exactly as it is, even when it is not the md5 of today's body.

WHAT ID. The md5 of the page body, as before. When that id is already taken by another page (two
pages with the same body), the md5 of the page's path and body is used instead, so two pages
never share an id.

CAP. At most --max-pages pages (default 50) get an id in one run, in path order, and the run
says how many are left for the next one. One run today has one page to do.

EXIT CODES
  0  done, including nothing to do
  1  a self-test case failed
  2  could not run: no pages found, a page whose front matter cannot be read, or a bad argument.
     A page that cannot be read stops the run before anything is written.
"""

import argparse
import hashlib
import os
import sys

import frontmatter

DOCS = os.path.join("src", "content", "docs")
SKIP_PREFIX = "src/content/docs/pro/changelog/"
SKIP_FILES = {"src/content/docs/404.mdx"}
DEFAULT_MAX_PAGES = 50
MIN_PAGES = 1


class CannotRun(Exception):
    """Exit 2."""


def log(msg=""):
    print(msg, flush=True)


def generate_object_id(text):
    return hashlib.md5(text.encode()).hexdigest()


def lacks_id(metadata):
    """True when the front matter carries no usable id: none, empty, or all zeros."""
    if "id" not in metadata:
        return True
    value = metadata.get("id")
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or set(text) <= {"0"}


def eligible(rel):
    return rel.endswith(".mdx") and not rel.startswith(SKIP_PREFIX) and rel not in SKIP_FILES


def scan(root):
    """[(rel_path, post)] for every eligible page, sorted by path. Raises CannotRun."""
    base = os.path.join(root, DOCS)
    if not os.path.isdir(base):
        raise CannotRun(f"no {DOCS} under {root}")
    pages = []
    unreadable = []
    for folder, _, files in os.walk(base):
        for name in files:
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if not eligible(rel):
                continue
            try:
                pages.append((rel, frontmatter.load(full)))
            except Exception as exc:  # noqa: BLE001 - any parse failure stops the run
                unreadable.append(f"{rel}: {exc}")
    if unreadable:
        raise CannotRun("front matter could not be read, so nothing was written:\n  "
                        + "\n  ".join(unreadable))
    if len(pages) < MIN_PAGES:
        raise CannotRun(f"found no pages under {base}")
    return sorted(pages, key=lambda p: p[0])


def reconcile(root, max_pages=DEFAULT_MAX_PAGES, dry_run=False):
    pages = scan(root)
    taken = {str(post.get("id")).strip().lower() for _, post in pages if not lacks_id(post.metadata)}
    lacking = [(rel, post) for rel, post in pages if lacks_id(post.metadata)]
    todo, later = lacking[:max_pages], lacking[max_pages:]
    log(f"{len(pages)} pages read, {len(lacking)} lack an id. "
        f"{'Would give' if dry_run else 'Giving'} {len(todo)} an id this run (cap {max_pages}).")
    for rel, post in todo:
        new_id = generate_object_id(post.content)
        if new_id in taken:
            new_id = generate_object_id(rel + "\n" + post.content)
        taken.add(new_id)
        old = post.metadata.get("id", "<none>")
        log(f"  {rel}: id {old!r} -> {new_id}{'  (dry run)' if dry_run else ''}")
        if not dry_run:
            post["id"] = new_id
            with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.write(frontmatter.dumps(post))
    if later:
        log(f"::warning::{len(later)} more page(s) lack an id and wait for a later run "
            f"(cap {max_pages} per run). First: {later[0][0]}")
    return 0


# ---------------------------------------------------------------------------------------
# self-test: drives the CLI of --target (default this file) on scratch trees, so the same
# cases can be pointed at an older copy of the script to see which of them it fails.

def _self_test(target):
    import subprocess
    import tempfile

    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        log(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    def page(root, rel, front, body):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\n" + front + "---\n\n" + body)
        return path

    def run(root, *extra):
        r = subprocess.run([sys.executable, target, f"--dir={root}", *extra],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def id_of(root, rel):
        return frontmatter.load(os.path.join(root, rel)).get("id")

    def body_id(body):
        # The md5 of the body as the front matter parser hands it over (it strips the
        # surrounding whitespace), which is what the old per-commit script hashed too.
        return generate_object_id(frontmatter.loads("---\ntitle: x\n---\n\n" + body).content)

    def snapshot(root):
        out = {}
        for folder, _, files in os.walk(root):
            for name in files:
                full = os.path.join(folder, name)
                with open(full, "rb") as fh:
                    out[full] = fh.read()
        return out

    log(f"Self-test of {target}: whole-tree id reconcile.")
    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "tree")
        keep_id = "c15bf2be31c3a7fbded5d13fce7aaab9"
        page(d, "src/content/docs/pro/has-id.mdx", f"id: {keep_id}\ntitle: Has\n", "Body changed since.\n")
        page(d, "src/content/docs/pro/old-no-id.mdx", "title: Old\n", "Added long ago, run dropped.\n")
        page(d, "src/content/docs/pro/zeros34.mdx", "id: 0000000000000000000000000000000000\ntitle: Z\n",
             "Thirty four zeros.\n")
        page(d, "src/content/docs/pro/zeros32.mdx", "id: '00000000000000000000000000000000'\ntitle: Z\n",
             "Thirty two zeros.\n")
        page(d, "src/content/docs/pro/empty.mdx", "id: ''\ntitle: E\n", "Empty id.\n")
        page(d, "src/content/docs/pro/twin-a.mdx", "title: A\n", "Same body.\n")
        page(d, "src/content/docs/pro/twin-b.mdx", "title: B\n", "Same body.\n")
        page(d, "src/content/docs/pro/changelog/2026/x.mdx", "title: C\n", "Changelog.\n")
        page(d, "src/content/docs/404.mdx", "title: N\n", "Not found.\n")
        before = snapshot(d)

        rc, out = run(d)
        ids = {rel: id_of(d, rel) for rel in ("src/content/docs/pro/old-no-id.mdx",
                                              "src/content/docs/pro/zeros34.mdx",
                                              "src/content/docs/pro/zeros32.mdx",
                                              "src/content/docs/pro/empty.mdx")}
        case("a page with no id that this commit did not add gets the md5 of its body",
             rc == 0 and ids["src/content/docs/pro/old-no-id.mdx"]
             == body_id("Added long ago, run dropped.\n"), f"rc={rc} {ids}")
        case("the 34-zero placeholder, which YAML reads as 0, counts as no id",
             ids["src/content/docs/pro/zeros34.mdx"] == body_id("Thirty four zeros.\n"),
             str(ids["src/content/docs/pro/zeros34.mdx"]))
        case("the quoted 32-zero placeholder counts as no id",
             ids["src/content/docs/pro/zeros32.mdx"] == body_id("Thirty two zeros.\n"),
             str(ids["src/content/docs/pro/zeros32.mdx"]))
        case("an empty id counts as no id",
             ids["src/content/docs/pro/empty.mdx"] == body_id("Empty id.\n"),
             str(ids["src/content/docs/pro/empty.mdx"]))
        case("an existing id is never changed, though it is not the md5 of today's body",
             str(id_of(d, "src/content/docs/pro/has-id.mdx")) == keep_id
             and before[os.path.join(d, "src/content/docs/pro/has-id.mdx")]
             == snapshot(d)[os.path.join(d, "src/content/docs/pro/has-id.mdx")])
        a, b = id_of(d, "src/content/docs/pro/twin-a.mdx"), id_of(d, "src/content/docs/pro/twin-b.mdx")
        case("two pages with the same body get two different ids", bool(a) and bool(b) and a != b,
             f"{a} {b}")
        after = snapshot(d)
        case("pro/changelog and 404.mdx are left byte for byte as they were",
             all(after[os.path.join(d, p)] == before[os.path.join(d, p)]
                 for p in ("src/content/docs/pro/changelog/2026/x.mdx", "src/content/docs/404.mdx")))
        rc2, out2 = run(d)
        case("a second run changes nothing (idempotent)",
             rc2 == 0 and snapshot(d) == after and "0 lack an id" in out2, f"rc={rc2}")

    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "tree")
        for i in range(5):
            page(d, f"src/content/docs/pro/p{i}.mdx", "title: P\n", f"Page {i}.\n")
        rc, out = run(d, "--max-pages=2")
        got = [id_of(d, f"src/content/docs/pro/p{i}.mdx") for i in range(5)]
        case("the cap gives ids to --max-pages pages in path order and reports the rest",
             rc == 0 and all(got[:2]) and not any(got[2:]) and "3 more page(s) lack an id" in out,
             f"rc={rc} {got}")
        rc, out = run(d, "--max-pages=2")
        got = [id_of(d, f"src/content/docs/pro/p{i}.mdx") for i in range(5)]
        case("and the next run carries on where it stopped", rc == 0 and all(got[:4]) and not got[4],
             f"rc={rc} {got}")

    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "tree")
        page(d, "src/content/docs/pro/no-id.mdx", "title: N\n", "No id.\n")
        before = snapshot(d)
        rc, out = run(d, "--dry-run")
        case("--dry-run reports the page and writes nothing",
             rc == 0 and snapshot(d) == before and "1 lack an id" in out, f"rc={rc}")

    with tempfile.TemporaryDirectory() as tmp:
        d = os.path.join(tmp, "tree")
        page(d, "src/content/docs/pro/no-id.mdx", "title: N\n", "No id.\n")
        page(d, "src/content/docs/pro/broken.mdx", "title: [unclosed\n", "Broken.\n")
        before = snapshot(d)
        rc, out = run(d)
        case("a page whose front matter cannot be read stops the run before anything is written",
             rc == 2 and snapshot(d) == before and "could not be read" in out, f"rc={rc}")
        rc, out = run(os.path.join(tmp, "nowhere"))
        case("a --dir with no docs tree is exit 2, never 'nothing to do'",
             rc == 2 and "no src/content/docs" in out, f"rc={rc}")

    failed = cases.count(False)
    if failed:
        log(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    log(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Give every documentation page lacking one an id.")
    parser.add_argument("--dir", help="repository root (the folder holding src/content/docs)")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--target", default=os.path.abspath(__file__),
                        help="with --self-test: the copy of this script to test")
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test(os.path.abspath(args.target))
    if not args.dir or args.max_pages < 1:
        log("CANNOT RUN: pass --dir, and --max-pages of 1 or more")
        return 2
    try:
        return reconcile(os.path.abspath(args.dir), args.max_pages, args.dry_run)
    except CannotRun as exc:
        log(f"::error::generate-ids could not run: {exc}")
        log(f"CANNOT RUN: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
