#!/usr/bin/env python3
"""
lb-pr-guard.py - keep a LaunchBrightly pull request to screenshots and image lines
(tallyfy/documentation#464).

LaunchBrightly's GitHub App opens pull requests that commit screenshots under
screenshots/launchbrightly/ and point article images at them. This check reads what merging the
pull request would change, GitHub's test merge HEAD^1..HEAD as simplicity-pr-report.py does, and
refuses anything else.

A LaunchBrightly pull request (author launchbrightly[bot], or user id 270903805) may only:
  - add, change or delete files under screenshots/launchbrightly/, each an image or sidecar
    that repo_screenshot_rules.py accepts (type by its bytes, at most 3 MiB, the name rule,
    the sidecar keys), and delete one only when no article still links it;
  - change existing articles (src/content/docs/**/*.mdx), never add, delete or rename one, where
    every added line is blank or one image on its own line (IMAGE_LINE_RE) whose alt text is not
    empty and does not name LaunchBrightly, and every removed line is blank or held an image.
It may never change documentation_assets.csv: the pipeline writes those rows after the merge.

Every pull request, whoever opened it:
  - a file it adds or changes under screenshots/ must pass the same file rules, because the
    pipeline refuses the whole run on a bad one after the merge;
  - every /screenshots/ link in the merged articles must sit under /screenshots/launchbrightly/
    and name a file in the merged tree;
  - a pull request from anyone else that touches screenshots/launchbrightly/ gets a warning,
    because the pages linking those images will credit LaunchBrightly.

  python3 scripts/lb-pr-guard.py [--repo PATH]      PR_AUTHOR_LOGIN and PR_AUTHOR_ID from env
  python3 scripts/lb-pr-guard.py --self-test

EXIT CODES
  0  nothing refused (warnings may be printed)
  1  refused
  2  could not decide: HEAD is not a merge commit, the author is unknown, or git failed.
     Never read a 2 as a pass.
"""

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "asset_management"))
import repo_screenshot_rules as rules  # noqa: E402

CSV_NAME = "documentation_assets.csv"
DOCS_PREFIX = "src/content/docs/"
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class CannotDecide(Exception):
    """Exit 2, never a pass."""


def log(msg=""):
    print(msg, flush=True)


def annotate(level, msg):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


def _git(repo, *args, binary=False, ok=(0,)):
    env = dict(os.environ, GIT_LITERAL_PATHSPECS="1")
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, env=env)
    if proc.returncode not in ok:
        raise CannotDecide(f"git {' '.join(args[:2])} failed: "
                           f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout if binary else proc.stdout.decode("utf-8", "surrogateescape")


def changed_files(repo):
    """[(status, path)] that merging adds: HEAD^1 (the base) against HEAD (the test merge).
    Renames are listed as a delete and an add, so a renamed article is caught as both."""
    parents = _git(repo, "rev-list", "--parents", "-n1", "HEAD").split()
    if len(parents) != 3:
        raise CannotDecide(f"expected the pull request's test merge commit, with 2 parents; HEAD has "
                           f"{len(parents) - 1}. Check out the pull_request event's default ref "
                           f"with fetch-depth: 2.")
    out = _git(repo, "diff", "--no-renames", "--name-status", "-z", "HEAD^1", "HEAD")
    tokens = [t for t in out.split("\0")]
    pairs = []
    i = 0
    while i + 1 < len(tokens) and tokens[i]:
        pairs.append((tokens[i][0], tokens[i + 1]))
        i += 2
    return pairs


def tree_files(repo, prefix):
    """{path: (mode, blob)} for every file under prefix in HEAD."""
    out = _git(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", prefix)
    files = {}
    for record in out.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        mode, _type, blob = meta.split()
        files[path] = (mode, blob)
    return files


def blob_reader(repo, blob):
    return lambda: _git(repo, "cat-file", "blob", blob, binary=True)


def diff_lines(repo, path):
    """([(line, text)] added, [(line, text)] removed) for one file, HEAD^1 against HEAD."""
    out = _git(repo, "diff", "--no-renames", "--no-color", "--no-ext-diff", "-U0",
               "HEAD^1", "HEAD", "--", path)
    added, removed = [], []
    old_n = new_n = 0
    in_hunk = False
    for raw in out.split("\n"):
        m = _HUNK_RE.match(raw)
        if m:
            old_n, new_n, in_hunk = int(m.group(1)), int(m.group(2)), True
            continue
        if not in_hunk or raw.startswith("\\"):
            continue
        text = raw[1:].rstrip("\r")
        if raw.startswith("+"):
            added.append((new_n, text))
            new_n += 1
        elif raw.startswith("-"):
            removed.append((old_n, text))
            old_n += 1
    return added, removed


def merged_references(repo):
    """[(path, file, line)] for every /screenshots/ link in the articles of HEAD."""
    out = _git(repo, "grep", "-l", "-z", "-I", "-F", "-e", "/screenshots/", "HEAD", "--",
               DOCS_PREFIX.rstrip("/"), ok=(0, 1))
    refs = []
    for name in out.split("\0"):
        if not name:
            continue
        path = name.split(":", 1)[1] if name.startswith("HEAD:") else name
        text = _git(repo, "cat-file", "blob", f"HEAD:{path}", binary=True).decode("utf-8", "replace")
        refs += [(ref, path, line) for ref, line, _alt in rules.find_references(text)]
    return refs


def decide(repo, login, author_id):
    """(exit code, refusals, warnings, notices)."""
    login, author_id = (login or "").strip(), (author_id or "").strip()
    if not login or not author_id:
        raise CannotDecide("PR_AUTHOR_LOGIN and PR_AUTHOR_ID must both be set, so this check knows "
                           "whether LaunchBrightly opened the pull request")
    is_lb = login == rules.LB_LOGIN or author_id == rules.LB_ID
    refusals, warnings, notices = [], [], []
    if is_lb and not (login == rules.LB_LOGIN and author_id == rules.LB_ID):
        notices.append(f"the author is {login} with id {author_id}; one of them is LaunchBrightly's, "
                       f"so its rules apply")
    changed = changed_files(repo)
    tree = tree_files(repo, rules.REPO_FOLDER)
    deleted = {p for s, p in changed if s == "D"}

    # Every pull request: files it adds or changes under screenshots/.
    to_check = {p: (tree[p][0], blob_reader(repo, tree[p][1]))
                for s, p in changed if p.startswith(rules.REPO_FOLDER) and s != "D" and p in tree}
    report = rules.check_tree(to_check, all_paths=set(tree))
    refusals += report.problems
    notices += report.notices

    # Every pull request: every /screenshots/ link in the merged articles.
    for ref, path, line in merged_references(repo):
        rel = ref[1:]
        if not rel.startswith(rules.ROOT):
            refusals.append(f"{path}:{line} links {ref}, which is outside /{rules.ROOT}")
        elif rel not in tree:
            refusals.append(f"{path}:{line} links {ref}, which is not in the merged tree"
                            + (" (this pull request deletes it)" if rel in deleted else ""))
        elif rules.extension(rel) not in rules.IMAGE_EXTS:
            refusals.append(f"{path}:{line} links {ref}, which is not an image")

    if is_lb:
        for status, path in changed:
            if path == CSV_NAME:
                refusals.append(f"{CSV_NAME}: a LaunchBrightly pull request may not change it; the "
                                f"pipeline writes these rows after the merge")
            elif path.startswith(rules.ROOT):
                continue  # judged by the file rules above, and by the link check for a delete
            elif path.startswith(DOCS_PREFIX) and path.endswith(".mdx"):
                if status != "M":
                    refusals.append(f"{path}: a LaunchBrightly pull request may change an existing "
                                    f"article but not add, delete or rename one (status {status})")
                    continue
                added, removed = diff_lines(repo, path)
                for number, text in added:
                    if not text.strip():
                        continue
                    m = rules.IMAGE_LINE_RE.match(text)
                    if not m:
                        refusals.append(f"{path}:{number} adds a line that is not one image on its "
                                        f"own line: {text[:160]!r}")
                        continue
                    problem = rules.alt_problem(m.group("alt"))
                    if problem:
                        refusals.append(f"{path}:{number}: {problem}")
                for number, text in removed:
                    if not rules.REMOVABLE_LINE_RE.search(text):
                        refusals.append(f"{path}:{number} (in the base) removes a line that holds no "
                                        f"image: {text[:160]!r}")
            else:
                refusals.append(f"{path}: a LaunchBrightly pull request may only change files under "
                                f"{rules.ROOT} and existing articles")
    elif any(p.startswith(rules.ROOT) for _s, p in changed):
        warnings.append(f"this pull request is not from LaunchBrightly but changes {rules.ROOT}; "
                        f"pages that link those images will credit LaunchBrightly")

    return (1 if refusals else 0), refusals, warnings, notices


def guard(repo, login, author_id):
    code, refusals, warnings, notices = decide(repo, login, author_id)
    who = "LaunchBrightly" if (login == rules.LB_LOGIN or author_id == rules.LB_ID) else login
    for notice in notices:
        log(f"NOTICE: {notice}")
    for warning in warnings:
        log(f"WARNING: {warning}")
        annotate("warning", warning)
    for refusal in refusals:
        log(f"REFUSED: {refusal}")
        annotate("error", refusal)
    if code == 0:
        log(f"PASS: nothing refused for this pull request from {who}.")
    else:
        log(f"REFUSED: {len(refusals)} problem(s) in this pull request from {who}.")
    return code


# ---------------------------------------------------------------------------------------
# self-test

_HUMAN = ("Amit", "amit@tallyfy.com")
_LB = (rules.LB_LOGIN, rules.LB_EMAIL)
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 4
PNG2 = b"\x89PNG\r\n\x1a\n" + b"other" * 4
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg" * 4
ROOT = rules.ROOT
ARTICLE = "src/content/docs/pro/tasks.mdx"
BASE_ARTICLE = (
    "---\nid: " + "c" * 32 + "\ntitle: Tasks\n---\n\n"
    "## Your task list\n\n"
    "Open the list to see what is due.\n\n"
    "![Task list](https://screenshots.tallyfy.com/tallyfy/pro/tasks.png)\n\n"
    '<img src="https://screenshots.tallyfy.com/tallyfy/pro/old.png" alt="Old" />\n\n'
    "![Linked](/screenshots/launchbrightly/linked.png)\n"
)


def _scratch(tmp, name, change, who=_LB):
    """A repository whose HEAD is a test merge of a branch, made by `change`, into staging."""
    repo = os.path.join(tmp, name)
    os.makedirs(repo)

    def git(*args, author=_HUMAN):
        env = dict(os.environ, GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
                   GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1])
        subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                       cwd=repo, env=env, check=True, capture_output=True)

    def write(rel, content):
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content.encode() if isinstance(content, str) else content)

    git("init", "-q", "-b", "staging")
    write(ARTICLE, BASE_ARTICLE)
    write("src/content/docs/pro/other.mdx", "---\ntitle: Other\n---\n\nText.\n")
    write(ROOT + "linked.png", PNG)
    write(ROOT + "unused.png", PNG2)
    write(CSV_NAME, "filename,r2_key\n")
    write("scripts/x.py", "print('x')\n")
    git("add", "-A")
    git("commit", "-q", "-m", "Base")
    git("checkout", "-q", "-b", "pr")
    change(repo, write)
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", "The pull request", author=who)
    git("checkout", "-q", "staging")
    git("merge", "--no-ff", "-q", "-m", "Merge pr into staging", "pr")
    return repo


def _edit_article(old, new):
    def change(repo, write):
        path = os.path.join(repo, ARTICLE)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert text.count(old) == 1, old
        write(ARTICLE, text.replace(old, new))
    return change


def self_test():
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        log(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail and not ok else ""))

    def verdict(repo, login=rules.LB_LOGIN, author_id=rules.LB_ID):
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                return guard(repo, login, author_id), buf.getvalue()
        except CannotDecide as exc:
            return 2, str(exc)

    def add(files):
        def change(repo, write):
            for rel, content in files.items():
                write(rel, content)
        return change

    def remove(*paths):
        def change(repo, write):
            for rel in paths:
                os.remove(os.path.join(repo, rel))
        return change

    def both(*changes):
        def change(repo, write):
            for c in changes:
                c(repo, write)
        return change

    new_line = "![Task list with due dates](/screenshots/launchbrightly/tasks.png)"
    swap = _edit_article("![Task list](https://screenshots.tallyfy.com/tallyfy/pro/tasks.png)", new_line)
    human = ("amit", "12345")

    cases = [
        # (name, change, author (login, id) or None for LaunchBrightly, expected rc, text that must appear)
        ("GREEN LaunchBrightly adds an image and points an image line at it",
         both(add({ROOT + "tasks.png": PNG}), swap), None, 0, "PASS"),
        ("GREEN LaunchBrightly adds an image with a good sidecar",
         add({ROOT + "new.png": PNG, ROOT + "new.json": '{"screen": "Tasks", "app_url": "/tasks"}'}),
         None, 0, "PASS"),
        ("GREEN LaunchBrightly deletes an image nothing links", remove(ROOT + "unused.png"), None, 0, "PASS"),
        ("GREEN LaunchBrightly replaces an <img> line with an image line",
         both(add({ROOT + "old.png": PNG}),
              _edit_article('<img src="https://screenshots.tallyfy.com/tallyfy/pro/old.png" alt="Old" />',
                            "![Old screen](/screenshots/launchbrightly/old.png)")), None, 0, "PASS"),
        ("GREEN a person edits prose", _edit_article("Open the list", "Open your list"), human, 0, "PASS"),
        ("GREEN a person adds an image to the folder, with a warning",
         add({ROOT + "by-hand.png": PNG}), human, 0, "WARNING: this pull request is not from LaunchBrightly"),
        ("RED LaunchBrightly changes a script", add({"scripts/x.py": "print('y')\n"}), None, 1,
         "scripts/x.py: a LaunchBrightly pull request may only change"),
        ("RED LaunchBrightly changes documentation_assets.csv", add({CSV_NAME: "filename,r2_key\na,b\n"}),
         None, 1, f"{CSV_NAME}: a LaunchBrightly pull request may not change it"),
        ("RED LaunchBrightly adds an article", add({"src/content/docs/pro/new.mdx": "---\ntitle: N\n---\n"}),
         None, 1, "not add, delete or rename one (status A)"),
        ("RED LaunchBrightly deletes an article", remove("src/content/docs/pro/other.mdx"), None, 1,
         "not add, delete or rename one (status D)"),
        ("RED LaunchBrightly renames an article",
         lambda repo, write: os.rename(os.path.join(repo, "src/content/docs/pro/other.mdx"),
                                       os.path.join(repo, "src/content/docs/pro/renamed.mdx")),
         None, 1, "(status A)"),
        ("RED LaunchBrightly adds an SVG", add({ROOT + "logo.svg": "<svg/>"}), None, 1, "is not an allowed image"),
        ("RED LaunchBrightly adds JPEG bytes named .png", add({ROOT + "a.png": JPEG}), None, 1,
         "the name says png but the bytes are jpeg"),
        ("RED LaunchBrightly adds an image over 3 MiB",
         add({ROOT + "a.png": PNG + b"\x00" * (rules.MAX_IMAGE_BYTES - len(PNG) + 1)}), None, 1,
         "over the 3,145,728 byte limit"),
        ("RED LaunchBrightly adds an upper-case name", add({ROOT + "Tasks.png": PNG}), None, 1, "the name must be"),
        ("RED LaunchBrightly adds a sidecar with another host",
         add({ROOT + "new.png": PNG, ROOT + "new.json": '{"app_url": "https://evil.example/x"}'}), None, 1,
         "is not on tallyfy.com"),
        ("RED LaunchBrightly adds a symlink",
         lambda repo, write: os.symlink("../../scripts/x.py", os.path.join(repo, ROOT, "link.png")),
         None, 1, "is not a regular file"),
        ("RED LaunchBrightly adds a prose line to an article",
         _edit_article("Open the list to see what is due.\n", "Open the list to see what is due.\nBuy now.\n"),
         None, 1, "adds a line that is not one image"),
        ("RED LaunchBrightly adds an image line with blank alt",
         both(add({ROOT + "tasks.png": PNG}),
              _edit_article("![Task list](https://screenshots.tallyfy.com/tallyfy/pro/tasks.png)",
                            "![   ](/screenshots/launchbrightly/tasks.png)")), None, 1, "the alt text is empty"),
        ("RED LaunchBrightly adds alt text naming itself",
         both(add({ROOT + "tasks.png": PNG}),
              _edit_article("![Task list](https://screenshots.tallyfy.com/tallyfy/pro/tasks.png)",
                            "![Screenshot by LaunchBrightly](/screenshots/launchbrightly/tasks.png)")),
         None, 1, "names LaunchBrightly"),
        ("RED LaunchBrightly adds an image line with a second link riding on it",
         both(add({ROOT + "tasks.png": PNG}),
              _edit_article("![Task list](https://screenshots.tallyfy.com/tallyfy/pro/tasks.png)",
                            new_line + "[x](https://example.com/)")), None, 1, "adds a line that is not one image"),
        ("RED LaunchBrightly removes a prose line",
         _edit_article("Open the list to see what is due.\n", ""), None, 1, "removes a line that holds no image"),
        ("RED LaunchBrightly deletes an image an article still links", remove(ROOT + "linked.png"), None, 1,
         "is not in the merged tree (this pull request deletes it)"),
        ("RED LaunchBrightly points an image line at a file that is not there",
         swap, None, 1, "links /screenshots/launchbrightly/tasks.png, which is not in the merged tree"),
        ("RED anyone: a link to a missing file",
         _edit_article("Open the list", "![Gone](/screenshots/launchbrightly/gone.png) Open the list"),
         human, 1, "which is not in the merged tree"),
        ("RED anyone: a link outside /screenshots/launchbrightly/",
         _edit_article("Open the list", "![Other](/screenshots/other.png) Open the list"), human, 1,
         "which is outside /screenshots/launchbrightly/"),
        ("RED anyone: an SVG under the folder", add({ROOT + "logo.svg": "<svg/>"}), human, 1,
         "is not an allowed image"),
        ("RED LaunchBrightly's user id alone is enough to apply its rules",
         add({"scripts/x.py": "print('y')\n"}), ("someone", rules.LB_ID), 1, "may only change"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        log("Self-test: one red and one green case per rule, on scratch test merges.")
        for i, (name, change, author, want, needle) in enumerate(cases):
            login, author_id = author or (rules.LB_LOGIN, rules.LB_ID)
            committer = _LB if author is None else _HUMAN
            repo = _scratch(tmp, f"case{i}", change, who=committer)
            rc, out = verdict(repo, login, author_id)
            check(name, rc == want and needle in out, f"rc={rc} want={want} {out.strip()[-400:]}")

        log("Self-test: it cannot decide without a test merge or an author.")
        repo = _scratch(tmp, "not-merge", add({ROOT + "tasks.png": PNG}))
        subprocess.run(["git", "reset", "-q", "--hard", "HEAD^2"], cwd=repo, check=True, capture_output=True)
        rc, out = verdict(repo)
        check("CANNOT DECIDE HEAD is not a merge commit (exit 2)", rc == 2 and "2 parents" in out, out)
        repo = _scratch(tmp, "no-author", add({ROOT + "tasks.png": PNG}))
        rc, out = verdict(repo, "", "")
        check("CANNOT DECIDE no author given (exit 2)", rc == 2 and "PR_AUTHOR_LOGIN" in out, out)

        log("Self-test: the command line reads the author from the environment.")
        repo = _scratch(tmp, "cli", add({"scripts/x.py": "print('y')\n"}))
        saved = {k: os.environ.get(k) for k in ("PR_AUTHOR_LOGIN", "PR_AUTHOR_ID")}
        try:
            for login, author_id, want in ((rules.LB_LOGIN, rules.LB_ID, 1), ("amit", "12345", 0), ("", "", 2)):
                os.environ["PR_AUTHOR_LOGIN"], os.environ["PR_AUTHOR_ID"] = login, author_id
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = main(["--repo", repo])
                check(f"the command line exits {want} for author {login or '(none)'}", rc == want, f"rc={rc}")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    passed = sum(results)
    log(f"SELF-TEST {'PASSED' if passed == len(results) else 'FAILED'}: {passed} of {len(results)} case(s)")
    return 0 if passed == len(results) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=".", help="the checkout of the pull request's test merge")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            return self_test()
        return guard(args.repo, os.environ.get("PR_AUTHOR_LOGIN", ""), os.environ.get("PR_AUTHOR_ID", ""))
    except CannotDecide as exc:
        log(f"CANNOT DECIDE: {exc}")
        annotate("error", f"LaunchBrightly PR guard could not decide, so it refuses: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - a crash must be 2, never a pass
        import traceback
        traceback.print_exc()
        log(f"CRASHED: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
