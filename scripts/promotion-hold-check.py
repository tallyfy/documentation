#!/usr/bin/env python3
"""Fail a staging -> main promotion that carries a held path.

Background: tallyfy/documentation#88 asked for exactly this and said so itself - "only a
path-based CI check on promotions to main would actually hold". #118 is the issue that built
it. Nine SSO pages published for seven weeks against a screen that did not exist, because the
only thing holding them back was a sentence in an issue.

Three modes, all used by the `promotion-hold-gate` job in documentation-pipeline.yml:

  --self-test     Build throwaway git repositories and prove the checker goes RED on a held
                  path and GREEN once that path is gone. Runs on every invocation in CI, so
                  the gate's ability to fail is asserted on every promotion rather than
                  assumed. A check only ever seen passing is indistinguishable from one that
                  cannot fail.
  --check-wiring  Prove the gate is still wired into the jobs that publish. A red gate that
                  does not block `sync` is decoration.
  (default)       The check itself, against a promoted commit.

Exit codes: 0 pass, 1 a hold was violated (or a self-test/wiring assertion failed), 2 the
checker could not run - a broken checker is never a pass.
"""

import argparse
import fnmatch
import os
import re
import shlex
import subprocess
import sys
import tempfile

HOLD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MIN_REASON_CHARS = 10
# `[release-hold: <id>]` naming ONE hold. Deliberately not a bare keyword: a marker that
# releases everything would get typed by muscle memory, and a keyword that matches anywhere
# in free text fires from inside a sentence that meant the opposite.
RELEASE_RE = re.compile(r"\[release-hold:\s*([a-z0-9][a-z0-9-]*)\s*\]")


class CheckerError(Exception):
    """The checker could not answer. Never treated as a pass."""


def log(msg):
    print(msg, flush=True)


def annotate(level, msg):
    """GitHub Actions annotation, so a failure is visible in the run summary, not just logs."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise CheckerError(
            f"git {' '.join(args)} failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


# --------------------------------------------------------------------------------------
# hold list


class Hold:
    def __init__(self, hold_id, glob, reason, line_no):
        self.id = hold_id
        self.glob = glob
        self.reason = reason
        self.line_no = line_no


def parse_holds(path):
    """Parse the hold list. Any malformed line is fatal.

    A hold that silently fails to parse is the exact failure this whole control exists to
    prevent, so there is no lenient path here and no skipping.
    """
    if not os.path.isfile(path):
        raise CheckerError(
            f"hold list not found at {path}. The list is required even when it holds "
            f"nothing - a missing list must be loud, not silently permissive."
        )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise CheckerError(f"cannot read hold list at {path}: {exc}")

    holds = []
    seen = {}
    for line_no, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 2)
        if len(parts) < 3:
            raise CheckerError(
                f"{path}:{line_no}: expected three fields '<id> <glob> <reason>', got "
                f"{len(parts)}: {stripped!r}"
            )
        hold_id, glob, reason = parts[0], parts[1], parts[2].strip()
        if not HOLD_ID_RE.match(hold_id):
            raise CheckerError(
                f"{path}:{line_no}: id {hold_id!r} must be lowercase letters, digits and "
                f"hyphens"
            )
        if hold_id in seen:
            raise CheckerError(
                f"{path}:{line_no}: duplicate id {hold_id!r}, already defined on line "
                f"{seen[hold_id]}. An override names one id, so ids must be unique."
            )
        if len(reason) < MIN_REASON_CHARS:
            raise CheckerError(
                f"{path}:{line_no}: hold {hold_id!r} needs a real reason beside it "
                f"(at least {MIN_REASON_CHARS} characters), got {reason!r}"
            )
        seen[hold_id] = line_no
        holds.append(Hold(hold_id, glob, reason, line_no))
    return holds


def matching_paths(holds, tracked_paths):
    """Map each hold to the tracked files it matches. fnmatch `*` spans `/` by design."""
    hits = {}
    for hold in holds:
        matched = [p for p in tracked_paths if fnmatch.fnmatchcase(p, hold.glob)]
        if matched:
            hits[hold.id] = (hold, sorted(matched))
    return hits


def released_ids(commit_message):
    return set(RELEASE_RE.findall(commit_message or ""))


# --------------------------------------------------------------------------------------
# the check


def check(repo, commit, holds_path, branch, require_on_branch=True):
    """Return 0 to pass, 1 to fail. Raises CheckerError when it cannot answer."""
    holds = parse_holds(holds_path)
    log(f"Hold list {holds_path}: {len(holds)} active hold(s).")
    for hold in holds:
        log(f"  - {hold.id}: {hold.glob}  ({hold.reason})")

    if branch != "main":
        log(
            f"Branch is {branch!r}, not 'main'. Holds are enforced on promotions to "
            f"production only, so nothing to enforce here."
        )
        return 0

    # Assert the commit really is on main before trusting the tree. A probe that takes a
    # name and hands back an object must confirm the object is the one it was asked for -
    # otherwise the gate could pass on a tree that was never promoted.
    if require_on_branch:
        proc = subprocess.run(
            ["git", "-C", repo, "merge-base", "--is-ancestor", commit, "origin/main"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise CheckerError(
                f"{commit} is not an ancestor of origin/main (rc={proc.returncode}). "
                f"Refusing to pass on a tree that cannot be shown to be the promoted one. "
                f"{proc.stderr.strip()}"
            )
        log(f"Verified {commit[:9]} is on origin/main.")

    tracked = [p for p in git(repo, "ls-tree", "-r", "--name-only", commit).splitlines() if p]
    if not tracked:
        raise CheckerError(
            f"{commit} lists zero tracked files. A hold check over an empty file set passes "
            f"every assertion made about it and proves nothing."
        )
    log(f"Promoted tree {commit[:9]}: {len(tracked)} tracked path(s).")

    if not holds:
        log("No active holds. Nothing can be violated.")
        return 0

    hits = matching_paths(holds, tracked)
    if not hits:
        log("PASS: the promoted tree contains no held path.")
        return 0

    message = git(repo, "log", "-1", "--format=%B", commit)
    released = released_ids(message)

    violations = []
    for hold_id, (hold, files) in sorted(hits.items()):
        if hold_id in released:
            log("")
            log(f"RELEASED: hold {hold_id!r} released by this promotion's commit message.")
            log(f"  reason on file : {hold.reason}")
            log(f"  files it covers: {len(files)}")
            for path in files[:20]:
                log(f"    {path}")
            if len(files) > 20:
                log(f"    ... and {len(files) - 20} more (not truncated silently: {len(files)} total)")
            annotate(
                "warning",
                f"Promotion hold {hold_id} was deliberately released by the commit message. "
                f"{len(files)} held file(s) are being published.",
            )
        else:
            violations.append((hold, files))

    unknown = released - {h.id for h in holds}
    for ghost in sorted(unknown):
        annotate(
            "warning",
            f"Commit message releases hold {ghost!r}, which is not in the hold list. "
            f"Nothing was released by it.",
        )

    if not violations:
        log("")
        log("PASS: every matched hold was deliberately released by this promotion.")
        return 0

    log("")
    log("FAIL: this promotion carries paths that are on hold.")
    for hold, files in violations:
        log("")
        log(f"  hold   : {hold.id}   ({holds_path}:{hold.line_no})")
        log(f"  pattern: {hold.glob}")
        log(f"  reason : {hold.reason}")
        log(f"  matched: {len(files)} file(s)")
        for path in files[:20]:
            log(f"    {path}")
        if len(files) > 20:
            log(f"    ... and {len(files) - 20} more (not truncated silently: {len(files)} total)")
        annotate(
            "error",
            f"Promotion blocked by hold '{hold.id}': {len(files)} held file(s) present. "
            f"{hold.reason}",
        )
    log("")
    log("To proceed, either delete the hold from the list (a reviewable diff), or release it")
    log("for this promotion only:")
    log("  git merge --no-ff staging -m \"Promote staging to main [release-hold: <id>] <why>\"")
    return 1


# --------------------------------------------------------------------------------------
# self-test: the red/green control, run on every invocation


def _build_fixture(tmp, files, hold_lines, commit_message="fixture commit"):
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "Fixture"], check=True)
    for rel in files:
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("fixture\n")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", repo, "commit", "-q", "-m", commit_message], check=True
    )
    holds_path = os.path.join(tmp, "holds.txt")
    with open(holds_path, "w", encoding="utf-8") as fh:
        fh.write("# fixture hold list\n" + "\n".join(hold_lines) + "\n")
    sha = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return repo, sha, holds_path


HELD_PAGE = "src/content/docs/pro/settings/how-to-configure-sso.mdx"
OTHER_PAGE = "src/content/docs/pro/tracking-and-tasks/tasks/index.mdx"
FIXTURE_HOLD = "sso-screens  src/content/docs/pro/*sso*  Screen not in production yet."


def self_test():
    """Prove the checker fails on a held path and passes without it. Both directions.

    Neither half means anything alone. A red-only control cannot distinguish a working gate
    from one that fails on everything; a green-only control cannot distinguish a working gate
    from one that cannot fail.
    """
    cases = []

    def case(name, expected, fn):
        try:
            actual = fn()
        except CheckerError as exc:
            actual = f"CheckerError: {exc}"
        ok = actual == expected
        cases.append((name, expected, actual, ok))
        log(f"  [{'ok' if ok else 'FAILED'}] {name}: expected {expected!r}, got {actual!r}")

    with tempfile.TemporaryDirectory() as tmp_red:
        repo, sha, holds = _build_fixture(
            tmp_red, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD]
        )
        case(
            "RED - promotion carrying a held path is blocked",
            1,
            lambda: check(repo, sha, holds, "main", require_on_branch=False),
        )

    with tempfile.TemporaryDirectory() as tmp_green:
        repo, sha, holds = _build_fixture(tmp_green, [OTHER_PAGE], [FIXTURE_HOLD])
        case(
            "GREEN - same promotion with the held path removed passes",
            0,
            lambda: check(repo, sha, holds, "main", require_on_branch=False),
        )

    with tempfile.TemporaryDirectory() as tmp_rel:
        repo, sha, holds = _build_fixture(
            tmp_rel,
            [HELD_PAGE, OTHER_PAGE],
            [FIXTURE_HOLD],
            commit_message="Promote staging to main [release-hold: sso-screens] shipping now",
        )
        case(
            "RELEASE - a commit message naming the hold releases it",
            0,
            lambda: check(repo, sha, holds, "main", require_on_branch=False),
        )

    with tempfile.TemporaryDirectory() as tmp_wrong:
        repo, sha, holds = _build_fixture(
            tmp_wrong,
            [HELD_PAGE, OTHER_PAGE],
            [FIXTURE_HOLD],
            commit_message="Promote staging to main [release-hold: some-other-hold]",
        )
        case(
            "RELEASE is specific - naming a different hold releases nothing",
            1,
            lambda: check(repo, sha, holds, "main", require_on_branch=False),
        )

    with tempfile.TemporaryDirectory() as tmp_staging:
        repo, sha, holds = _build_fixture(
            tmp_staging, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD]
        )
        case(
            "SCOPE - the same held tree on staging is not blocked",
            0,
            lambda: check(repo, sha, holds, "staging", require_on_branch=False),
        )

    with tempfile.TemporaryDirectory() as tmp_bad:
        repo, sha, _ = _build_fixture(tmp_bad, [OTHER_PAGE], [])
        # Without this the commit is on no origin/main, so check() raises an ANCESTRY error
        # whatever parse_holds does, and both arms below pass on a parser that refuses nothing.
        # With it, the only CheckerError available is the one they are about.
        subprocess.run(
            ["git", "-C", repo, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True
        )
        bad = os.path.join(tmp_bad, "malformed.txt")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("sso-screens src/content/docs/pro/*sso*\n")  # no reason
        case(
            "FAIL CLOSED - a malformed hold line is fatal, never skipped",
            "CheckerError",
            lambda: _error_kind(check, repo, sha, bad, "main"),
        )
        case(
            "FAIL CLOSED - a missing hold list is fatal",
            "CheckerError",
            lambda: _error_kind(
                check, repo, sha, os.path.join(tmp_bad, "nope.txt"), "main"
            ),
        )

    # WHICH copy of the list the gate reads decides the verdict, and the two copies differ by
    # design: a hold is written on the authoring branch, and a promote branched off the target
    # never carries it. Same tree, same commit, two lists, two answers. Measured on the real
    # thing 2026-09-20: run 35532856946 promoted 0a6b25249 to main and logged "0 active
    # hold(s) ... No active holds. Nothing can be violated." while vault-screen was live on
    # staging. See tallyfy/documentation#270.
    def _verdicts_for_both_lists():
        with tempfile.TemporaryDirectory() as tmp:
            repo, sha, authoring = _build_fixture(
                tmp, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD]
            )
            promoted = os.path.join(tmp, "promoted-tree-holds.txt")
            with open(promoted, "w", encoding="utf-8") as fh:
                fh.write("# the target branch's own copy, which the hold was never written to\n")
            return (
                check(repo, sha, authoring, "main", require_on_branch=False),
                check(repo, sha, promoted, "main", require_on_branch=False),
            )

    case(
        "SOURCE - one promotion, two hold lists, two verdicts",
        (1, 0),
        _verdicts_for_both_lists,
    )

    # The gate must not refuse everything once it reads the authoring branch's list. A subset
    # promote carries a handful of files off the target branch, and the held glob matches none
    # of them, so it has to pass with the full list in force. A gate that blocks every
    # promotion is as useless as one that blocks none, and it fails in the direction where
    # nothing ships at all.
    with tempfile.TemporaryDirectory() as tmp_subset:
        repo, sha, holds = _build_fixture(
            tmp_subset,
            [OTHER_PAGE, "src/content/docs/pro/launching/index.mdx"],
            [
                FIXTURE_HOLD,
                "vault-screen  src/content/docs/pro/integrations/vault/*  Not in production.",
            ],
        )
        case(
            "SUBSET - a clean subset promote still passes with every hold in force",
            0,
            lambda: check(repo, sha, holds, "main", require_on_branch=False),
        )

    # The wiring assertion that keeps both readers pointed at the authoring branch. Each shape
    # below is one an UNBOUND check accepts: naming the branch in a comment, fetching the wrong
    # branch, splitting --holds onto another step, or passing the promoted tree's own copy with
    # the flag present. The last is the one to care about, because it is #270 wearing the fix,
    # and a guard that accepts it reports that the hole is closed while it is open.
    _FETCH_STEP = {
        "env": {"AUTHORING_BRANCH": AUTHORING_BRANCH},
        "run": 'git fetch --no-tags origin "$AUTHORING_BRANCH"\n'
               'git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"',
    }
    _CHECK_STEP = {
        "run": 'python promotion-hold-check.py --commit "$HEAD_SHA" --branch "$HEAD_BRANCH" \\\n'
               '  --holds "$RUNNER_TEMP/holds.txt"'
    }
    _GOOD_GATE = {"steps": [_FETCH_STEP, _CHECK_STEP]}
    _GATE_BEFORE_270 = {
        "steps": [
            {"run": 'python promotion-hold-check.py --commit "$HEAD_SHA" --branch "$HEAD_BRANCH"'}
        ]
    }
    _GATE_WRONG_BRANCH = {
        "steps": [
            {
                "env": {"AUTHORING_BRANCH": AUTHORING_BRANCH},
                "run": "git fetch --no-tags origin main\n"
                       'git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"',
            },
            _CHECK_STEP,
        ]
    }
    _GATE_SPLIT_HOLDS = {
        "steps": [
            _FETCH_STEP,
            {"run": 'python promotion-hold-check.py --commit "$HEAD_SHA" --branch "$HEAD_BRANCH"'},
            {"run": 'echo --holds "$RUNNER_TEMP/holds.txt"'},
        ]
    }
    _GATE_PROMOTED_COPY = {
        "steps": [
            _FETCH_STEP,
            {
                "run": 'python promotion-hold-check.py --commit "$HEAD_SHA" '
                       "--branch \"$HEAD_BRANCH\" --holds .github/promotion-holds.txt"
            },
        ]
    }
    _GATE_COMMENT_ONLY = {
        "steps": [
            {
                "env": {"AUTHORING_BRANCH": AUTHORING_BRANCH},
                # The comment is the COMPLETE, correct command. Only comment-stripping separates
                # this from the good shape, so the arm tests the code rather than the fixture.
                "run": '# git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"\n'
                       "# git fetch --no-tags origin staging\n"
                       "echo nothing",
            },
            _CHECK_STEP,
        ]
    }

    _GATE_EXPLICIT_WRONG_REF = {
        "steps": [
            {
                "run": 'git show "origin/main:.github/promotion-holds.txt" '
                       '> "$RUNNER_TEMP/holds.txt"'
            },
            _CHECK_STEP,
        ]
    }
    _GATE_EXPLICIT_RIGHT_REF = {
        "steps": [
            {
                "run": 'git show "origin/staging:.github/promotion-holds.txt" '
                       '> "$RUNNER_TEMP/holds.txt"'
            },
            _CHECK_STEP,
        ]
    }

    _GATE_REFETCHES_TARGET = {
        "steps": [
            {
                "run": "git fetch --no-tags origin staging\n"
                       "git fetch --no-tags origin main\n"
                       'git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"',
            },
            _CHECK_STEP,
        ]
    }
    _GATE_FETCHES_TARGET_AFTER = {
        "steps": [
            {
                "run": "git fetch --no-tags origin staging\n"
                       'git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"\n'
                       "git fetch --no-tags origin main",
            },
            _CHECK_STEP,
        ]
    }
    _GATE_TRAILING_COMMENT = {
        "steps": [
            {
                "run": "git fetch --no-tags origin main   # staging is the authoring branch\n"
                       'git show "FETCH_HEAD:.github/promotion-holds.txt" > "$RUNNER_TEMP/holds.txt"',
            },
            _CHECK_STEP,
        ]
    }
    _GATE_LOOKALIKE_BRANCH = {
        "steps": [
            {
                "run": 'git show "origin/staging-archive:.github/promotion-holds.txt" '
                       '> "$RUNNER_TEMP/holds.txt"'
            },
            _CHECK_STEP,
        ]
    }
    _GATE_TWO_SOURCES = {
        "steps": [
            _FETCH_STEP,
            {
                "run": 'git show "origin/main:.github/promotion-holds.txt" '
                       '> "$RUNNER_TEMP/holds.txt"'
            },
            _CHECK_STEP,
        ]
    }
    _GATE_NO_CHECKER = {"steps": [_FETCH_STEP, {"run": "echo done"}]}
    _GATE_FETCH_HEAD_UNFETCHED = {
        "steps": [
            {
                "run": 'git show "FETCH_HEAD:.github/promotion-holds.txt" '
                       '> "$RUNNER_TEMP/holds.txt"'
            },
            _CHECK_STEP,
        ]
    }

    def _source_verdict(job):
        return 1 if check_hold_source(job, "--commit", GATE_JOB) else 0

    case(
        "SOURCE GREEN - fetch from the authoring branch and hand that file over is accepted",
        0,
        lambda: _source_verdict(_GOOD_GATE),
    )
    case(
        "SOURCE RED - the shape this job had before #270 is refused",
        1,
        lambda: _source_verdict(_GATE_BEFORE_270),
    )
    case(
        "SOURCE RED - fetching the list from the TARGET branch is refused",
        1,
        lambda: _source_verdict(_GATE_WRONG_BRANCH),
    )
    case(
        "SOURCE RED - --holds on a step other than the checker call is refused",
        1,
        lambda: _source_verdict(_GATE_SPLIT_HOLDS),
    )
    case(
        "SOURCE RED - --holds pointing at the promoted tree's own copy is refused",
        1,
        lambda: _source_verdict(_GATE_PROMOTED_COPY),
    )
    case(
        "SOURCE RED - a comment naming the branch, with no git command, is refused",
        1,
        lambda: _source_verdict(_GATE_COMMENT_ONLY),
    )

    case(
        "SOURCE GREEN - an explicit origin/<authoring> ref is accepted",
        0,
        lambda: _source_verdict(_GATE_EXPLICIT_RIGHT_REF),
    )
    case(
        "SOURCE RED - an explicit ref naming the TARGET branch is refused",
        1,
        lambda: _source_verdict(_GATE_EXPLICIT_WRONG_REF),
    )

    case(
        "SOURCE RED - fetching the target branch AFTER the authoring one is refused",
        1,
        lambda: _source_verdict(_GATE_REFETCHES_TARGET),
    )
    case(
        "SOURCE GREEN - a fetch AFTER the show cannot change it, so it is allowed",
        0,
        lambda: _source_verdict(_GATE_FETCHES_TARGET_AFTER),
    )
    case(
        "SOURCE RED - a trailing comment claiming the authoring branch is refused",
        1,
        lambda: _source_verdict(_GATE_TRAILING_COMMENT),
    )
    case(
        "SOURCE RED - a branch merely CONTAINING the authoring name is refused",
        1,
        lambda: _source_verdict(_GATE_LOOKALIKE_BRANCH),
    )
    case(
        "SOURCE RED - writing the list twice is refused rather than guessed",
        1,
        lambda: _source_verdict(_GATE_TWO_SOURCES),
    )
    case(
        "SOURCE RED - FETCH_HEAD with no fetch before it at all is refused",
        1,
        lambda: _source_verdict(_GATE_FETCH_HEAD_UNFETCHED),
    )
    case(
        "SOURCE RED - fetching the list and never invoking the checker is refused",
        1,
        lambda: _source_verdict(_GATE_NO_CHECKER),
    )

    # main()'s --holds plumbing, driven through argv rather than by calling check() directly.
    # Nothing else executes it: a main() that parsed --holds and then read the promoted tree's
    # copy anyway passed every other arm here and --check-wiring at the same time.
    def _main_honours_holds():
        with tempfile.TemporaryDirectory() as tmp:
            repo, sha, authoring = _build_fixture(
                tmp, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD]
            )
            # main() requires the commit to be on origin/main, which a fixture has no remote for.
            subprocess.run(
                ["git", "-C", repo, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True
            )
            promoted = os.path.join(tmp, "promoted-tree-holds.txt")
            with open(promoted, "w", encoding="utf-8") as fh:
                fh.write("# the target branch's own copy, which the hold was never written to\n")
            argv = ["--repo", repo, "--commit", sha, "--branch", "main", "--holds"]
            return (main(argv + [authoring]), main(argv + [promoted]))

    case(
        "CLI - main() honours --holds rather than the promoted tree's own copy",
        (1, 0),
        _main_honours_holds,
    )

    # The effective hold list handed to support-docs. Both directions matter: a hold that is
    # still active must survive the trip, and one released for this promotion must not, or the
    # other side's build fails on content this side deliberately shipped.
    def _emit_and_parse(commit_message):
        with tempfile.TemporaryDirectory() as tmp:
            repo, sha, holds = _build_fixture(
                tmp, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD], commit_message=commit_message
            )
            out = os.path.join(tmp, "emitted.txt")
            emit_effective_holds(repo, sha, holds, out)
            # Parsed with the same parser, so a malformed emission is caught here rather than
            # in a Cloudflare build log where nobody is watching.
            return [h.id for h in parse_holds(out)]

    case(
        "EMIT - an active hold survives into the effective list",
        ["sso-screens"],
        lambda: _emit_and_parse("Promote staging to main"),
    )
    case(
        "EMIT - a hold released by this promotion is dropped from it",
        [],
        lambda: _emit_and_parse("Promote staging to main [release-hold: sso-screens] shipping"),
    )
    case(
        "EMIT - releasing a DIFFERENT hold drops nothing",
        ["sso-screens"],
        lambda: _emit_and_parse("Promote staging to main [release-hold: some-other-hold]"),
    )

    # tallyfy/documentation#171. The `sync` job writes this file to support-docs `staging` on
    # one road and to `production` on the other, and those two roads are never the same commit.
    # So the emitted BODY must not depend on which commit produced it, or the two branches
    # always differ and every merge between them conflicts - on a file that is a security gate.
    # This case FAILS on the pre-#171 emitter, which wrote a `# Source commit:` line, so it is a
    # real discriminator rather than an assertion that happens to hold.
    def _emit_bytes(commit_message):
        with tempfile.TemporaryDirectory() as tmp:
            repo, sha, holds = _build_fixture(
                tmp, [HELD_PAGE, OTHER_PAGE], [FIXTURE_HOLD], commit_message=commit_message
            )
            out = os.path.join(tmp, "emitted.txt")
            emit_effective_holds(repo, sha, holds, out)
            with open(out, encoding="utf-8") as fh:
                return fh.read()

    def _two_roads_identical():
        # Two different commits, same effective hold set: what the two roads look like on a
        # normal cycle. Asserted non-empty first, because two failed emissions would both be
        # the empty string and compare equal, which is a pass for the wrong reason.
        a = _emit_bytes("Sync from staging")
        b = _emit_bytes("Promote staging to main: a different commit entirely")
        if not a or not b:
            return "EMPTY EMISSION - cannot compare"
        return a == b

    case(
        "EMIT-IDENTICAL - two different source commits emit byte-identical bodies (#171)",
        True,
        _two_roads_identical,
    )

    def _release_still_changes_bytes():
        # The substitution arm for the case above. An emitter "fixed" by writing a constant
        # body would pass that one and fail this one, so the pair pins the body to the
        # effective hold SET rather than to nothing at all.
        plain = _emit_bytes("Promote staging to main")
        released = _emit_bytes("Promote staging to main [release-hold: sso-screens] shipping")
        if not plain or not released:
            return "EMPTY EMISSION - cannot compare"
        return plain != released

    case(
        "EMIT-IDENTICAL - a release marker still CHANGES the bytes (not a constant body)",
        True,
        _release_still_changes_bytes,
    )

    failed = [c for c in cases if not c[3]]
    log("")
    if failed:
        annotate("error", f"promotion-hold-check self-test FAILED ({len(failed)} case(s))")
        log(f"SELF-TEST FAILED: {len(failed)} of {len(cases)} case(s).")
        return 1
    log(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s), red and green both proven.")
    return 0


def _error_kind(fn, *args):
    try:
        fn(*args)
    except CheckerError:
        return "CheckerError"
    return "no error"


# --------------------------------------------------------------------------------------
# effective hold list, for the OTHER road into production


def emit_effective_holds(repo, commit, holds_path, out_path):
    """Write the hold list as it stands AFTER this promotion's release markers are applied.

    support-docs enforces holds at build time, because publishing that site is the Cloudflare
    Pages git integration and a merge of its `staging` into `production` never touches this
    pipeline (tallyfy/documentation#135). Its gate needs the hold list, and the `sync` job is
    what puts it there.

    It must be the EFFECTIVE list, not this file verbatim. A hold released for one promotion
    only, via `[release-hold: <id>]`, stays on its line in this file by design - the release is
    scoped to the promotion, not to the list. Copying the raw file would therefore hand
    support-docs a hold that this repo's own gate has already allowed past, and its production
    build would fail on content we deliberately shipped. Resolving the marker here keeps one
    source of truth for what "held" means and leaves the other side a plain list to match.

    THE BODY IS A PURE FUNCTION OF THE EFFECTIVE HOLD SET, AND IT MUST STAY ONE. Nothing about
    WHICH promotion produced it may appear here. The `sync` job writes this same file to
    support-docs `staging` on one road and to `production` on the other, and those two roads are
    never the same commit, so any per-promotion value in the body guarantees the two branches
    differ and guarantees a merge conflict on a SECURITY gate file. That is
    tallyfy/documentation#171: it cost three pull requests whose only content was clearing the
    conflict (support-docs #238, #239, #240), and routine conflicts in a gate file train people
    to resolve by eye. Provenance now travels in the sync COMMIT MESSAGE, which cannot conflict.
    A release marker is separately durable: it lives in the promotion's own commit message in
    `main`'s history forever. Asserted by the two EMIT-IDENTICAL cases in the self-test.
    """
    holds = parse_holds(holds_path)
    # Still resolved, because `released_ids` reads that commit's message. It is deliberately
    # NOT written into the body - see the paragraph above.
    resolved = git(repo, "rev-parse", commit).strip()
    message = git(repo, "log", "-1", "--format=%B", resolved)
    released = released_ids(message)
    effective = [h for h in holds if h.id not in released]
    dropped = [h.id for h in holds if h.id in released]

    lines = [
        "# GENERATED - do not edit here.",
        "#",
        "# Written by the `sync` job in tallyfy/documentation's documentation-pipeline.yml,",
        "# from .github/promotion-holds.txt in that repo. Edit it there; an edit here is",
        "# overwritten by the next sync.",
        "#",
        "# Enforced by scripts/promotion-hold-build-gate.mjs, chained into `npm run build`, so",
        "# a held path cannot reach production down the support-docs road either (#135).",
        "#",
        "# This body carries NO per-promotion value, deliberately: it is written to two branches",
        "# that are never the same commit, so anything of that kind here forces a conflict on",
        "# every merge between them (tallyfy/documentation#171). The producing commit is named in",
        "# the sync commit message instead.",
    ]
    lines.append("#")
    if effective:
        for hold in effective:
            lines.append(f"{hold.id}  {hold.glob}  {hold.reason}")
    else:
        lines.append("# ACTIVE HOLDS - none.")

    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir and not os.path.isdir(out_dir):
        raise CheckerError(f"cannot write effective hold list, no such directory: {out_dir}")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    log(
        f"Effective hold list written to {out_path}: {len(effective)} hold(s)"
        + (f", {len(dropped)} released by this promotion" if dropped else "")
    )
    return 0


# --------------------------------------------------------------------------------------
# wiring guard: a red gate that blocks nothing is decoration


GATE_JOB = "promotion-hold-gate"
PUBLISH_JOB = "sync"
UPSTREAM_SUCCESS_TERM = "github.event.workflow_run.conclusion == 'success'"
# The branch content is authored on, and therefore the branch whose copy of the hold list
# governs. A hold gets written on staging; a promote that branches off main never carries it,
# so reading the list out of the PROMOTED tree asks the promotion to police itself. Measured
# on run 35532856946 (#270): the gate read main's copy, found 0 active holds, and passed a
# tree it had no list to judge. Both terms below are asserted, because passing --holds with a
# file fetched from the wrong place would satisfy the second on its own.
AUTHORING_BRANCH = "staging"
HOLDS_FILE = "promotion-holds.txt"
# Jobs that may legitimately run without waiting for the gate, each with the reason it is
# harmless. Anything NOT listed here must depend on the gate, so adding a job forces a
# decision instead of silently escaping the gate. Derived from the workflow file itself, so
# it grows with the file rather than freezing at today's job list.
WIRING_EXEMPT = {
    GATE_JOB: "the gate itself",
    "ai-tell-gate": "the other root gate (tallyfy/documentation#191); read-only, publishes "
                    "nothing, and it must stay a ROOT job - giving it `needs` here would let a "
                    "failure elsewhere SKIP it, which is the exact defect both gates exist to "
                    "avoid",
    "validate-markdown": "read-only lint, publishes nothing",
    "generate-snippets": "early-exits on main; writes only to staging",
    "update-last-modified": "early-exits on main; writes only to staging",
    "generate-related-articles": "early-exits on main; writes only to staging",
    "check-deleted-files": "only removes Answers entries for files deleted in this commit; "
                           "cannot publish held content",
}


def _strip_comment(line):
    """Drop a shell comment, whole-line or trailing, without touching a # inside quotes.

    Whole-line stripping alone is not enough: a trailing comment lets a command claim in words
    to read the authoring branch while reading the target branch, and the claim is the part a
    reader believes.
    """
    out = []
    quote = None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1].isspace()):
            break
        out.append(ch)
    return "".join(out)


def _names_branch(ref, branch):
    """`origin/staging` yes. `origin/staging-archive` and `origin/not-staging` no.

    A substring test accepts both of those, and either is a different branch whose hold list
    may say anything.
    """
    return ref == branch or ref.endswith("/" + branch)


def _fetches_branch(command, branch):
    """True when a `git fetch` command names the branch as a whole argument."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    return any(_names_branch(token, branch) for token in tokens)


def _shell_commands(job):
    """Every runnable command in a job, comments dropped and continuations joined.

    Dropping comment lines is what stops a job satisfying this check with prose. Joining
    continuations is what lets --holds and --commit be recognised as ONE command when the
    invocation is wrapped, which is how anyone would actually write it.
    """
    commands = []
    for step in (job.get("steps") or []):
        if not isinstance(step, dict):
            continue
        env = {k: str(v) for k, v in (step.get("env") or {}).items()}
        buf = ""
        for raw in str(step.get("run", "")).splitlines():
            line = _strip_comment(raw).rstrip()
            if not line.strip():
                continue
            if line.endswith("\\"):
                buf += line[:-1] + " "
                continue
            command = (buf + line).strip()
            buf = ""
            if not command:
                continue
            for key, value in env.items():
                command = command.replace("${" + key + "}", value).replace("$" + key, value)
            commands.append(command)
        if buf.strip():
            commands.append(buf.strip())
    return commands


def check_hold_source(job, marker, job_name):
    """Prove a job READS the hold list from the authoring branch and HANDS THAT FILE over.

    Each clause is bound to the next rather than tested on its own. A string-presence check
    passes on a job that names the authoring branch in a comment and then reads the promoted
    tree's own copy anyway, which is #270 with the flag present, and it would report that the
    fix is in place. Four shapes an unbound check accepts are self-tested below.
    """
    commands = _shell_commands(job)
    problems = []

    pattern = (
        r"git\s+show\s+[\"']?([^\"'\s:]+):[^\"'\s]*"
        + re.escape(HOLDS_FILE)
        + r"[\"']?\s*>\s*[\"']?([^\"'\s]+)"
    )
    shows = [(i, m) for i, c in enumerate(commands) for m in [re.search(pattern, c)] if m]
    if not shows:
        problems.append(
            f"job {job_name!r} never runs a `git show <ref>:{HOLDS_FILE}` writing the list to a "
            f"file, so it has no copy from the {AUTHORING_BRANCH!r} branch to check against. A "
            f"hold lives on the authoring branch, and a promote branched off the target carries "
            f"an empty list (see #270)."
        )
        return problems
    if len(shows) > 1:
        # Which one wins depends on ordering and on the target paths, so refuse rather than
        # pick. Refusing is a red gate; guessing is a gate that reports on the wrong file.
        problems.append(
            f"job {job_name!r} writes {HOLDS_FILE!r} out of git {len(shows)} times, so which "
            f"copy the checker is handed depends on ordering. Write it once."
        )
        return problems

    show_index, show = shows[0]
    ref, target = show.group(1), show.group(2)
    if ref == "FETCH_HEAD":
        # FETCH_HEAD is whatever the LAST fetch wrote, so only the fetch immediately before
        # the show decides what this file is. An any() over every command accepts a job that
        # fetches the authoring branch and then fetches the target branch, which is a plausible
        # edit here because check() itself resolves origin/main.
        earlier = [c for c in commands[:show_index] if re.search(r"git\s+fetch\b", c)]
        if not _fetches_branch(earlier[-1] if earlier else "", AUTHORING_BRANCH):
            problems.append(
                f"job {job_name!r} reads the hold list from FETCH_HEAD, but the last fetch "
                f"before it is {(earlier[-1] if earlier else None)!r}, not a fetch of "
                f"{AUTHORING_BRANCH!r}. FETCH_HEAD "
                f"follows the most recent fetch (see #270)."
            )
    elif not _names_branch(ref, AUTHORING_BRANCH):
        problems.append(
            f"job {job_name!r} reads the hold list from {ref!r}, which is not "
            f"{AUTHORING_BRANCH!r} nor a remote-tracking ref for it (see #270)."
        )

    # Matched on `python` plus the marker rather than on this file's own name: keying on
    # __file__ breaks the moment the script is copied or renamed, including by a mutation
    # battery testing this very function, and then every job reads as "invokes nothing".
    invocations = [c for c in commands if marker in c and "python" in c]
    if not invocations:
        problems.append(
            f"job {job_name!r} never invokes the checker with {marker}, so it checks nothing."
        )
        return problems
    for command in invocations:
        passed = re.search(r"--holds[=\s]+[\"']?([^\"'\s]+)", command)
        if not passed:
            problems.append(
                f"job {job_name!r} runs the checker with {marker} and no --holds, so it falls "
                f"back to the PROMOTED tree's copy of {HOLDS_FILE!r} (see #270)."
            )
        elif passed.group(1) != target:
            problems.append(
                f"job {job_name!r} passes --holds {passed.group(1)!r}, which is not the file it "
                f"fetched from {AUTHORING_BRANCH!r} ({target!r}). Reading the promoted tree's "
                f"own copy with the flag present is #270 wearing the fix (see #270)."
            )
    return problems


def check_wiring(workflow_path):
    try:
        import yaml
    except ImportError:
        raise CheckerError("pyyaml is required for --check-wiring")
    if not os.path.isfile(workflow_path):
        raise CheckerError(f"workflow not found at {workflow_path}")
    with open(workflow_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    jobs = doc.get("jobs") or {}
    if not jobs:
        raise CheckerError(f"{workflow_path} declares no jobs")
    if GATE_JOB not in jobs:
        raise CheckerError(f"{workflow_path} has no {GATE_JOB!r} job")

    def needs_of(name):
        raw = (jobs.get(name) or {}).get("needs") or []
        return [raw] if isinstance(raw, str) else list(raw)

    def depends_on_gate(name):
        """DIRECT dependency only, deliberately not transitive.

        `sync` guards itself with `if: !failure() && !cancelled()`. Whether `failure()`
        reaches a failure several edges up the needs graph is not something this repo has
        measured, and run 27840821129 shows skip-propagation does NOT behave the way the
        graph suggests: every job was skipped there and `sync` ran anyway. So a publishing
        job must name the gate itself rather than inheriting it through a neighbour that
        might merely be skipped.
        """
        return GATE_JOB in needs_of(name)

    problems = []

    # `sync` is the job that actually publishes, and it guards itself with a status-function
    # conditional (`!failure() && !cancelled()`), which replaces the default "skip when a
    # needed job was skipped". Without an explicit upstream-success term it therefore
    # publishes on runs where every validation job skipped - measured on run 27840821129,
    # where all six other jobs read `skipped` and `sync` read `success` (#122). That term
    # cannot be observed locally, because it needs a real failed upstream run, so it is
    # asserted statically here instead and this assertion has a control in both directions.
    sync_if = str((jobs.get(PUBLISH_JOB) or {}).get("if", ""))
    if PUBLISH_JOB in jobs and UPSTREAM_SUCCESS_TERM not in sync_if.replace('"', "'"):
        problems.append(
            f"job {PUBLISH_JOB!r} does not require {UPSTREAM_SUCCESS_TERM!r} in its `if`, so "
            f"it will publish on runs where every validation job was skipped (see #122). "
            f"Its condition is currently: {sync_if!r}"
        )

    # Both readers of the hold list must take it from the authoring branch: the gate, which
    # blocks the promotion, and the sync job's --emit-effective-holds, which writes the list
    # support-docs enforces at build time on the other road into production.
    problems += check_hold_source(jobs.get(GATE_JOB) or {}, "--commit", GATE_JOB)
    problems += check_hold_source(
        jobs.get(PUBLISH_JOB) or {}, "--emit-effective-holds", PUBLISH_JOB
    )

    for name in jobs:
        if name in WIRING_EXEMPT:
            continue
        if not depends_on_gate(name):
            problems.append(
                f"job {name!r} does not depend on {GATE_JOB!r}, so a red gate would not "
                f"stop it. Add {GATE_JOB!r} to its `needs`, or add it to WIRING_EXEMPT in "
                f"{os.path.basename(__file__)} with the reason it cannot publish held content."
            )
    if needs_of(GATE_JOB):
        problems.append(
            f"{GATE_JOB!r} has `needs`, so another job failing would SKIP the gate. It must "
            f"be a root job."
        )

    log(f"Workflow {workflow_path}: {len(jobs)} job(s).")
    for name in sorted(jobs):
        if name in WIRING_EXEMPT:
            log(f"  - {name}: exempt ({WIRING_EXEMPT[name]})")
        else:
            log(f"  - {name}: gated ({'ok' if depends_on_gate(name) else 'NOT GATED'})")

    if problems:
        for problem in problems:
            log(f"WIRING FAIL: {problem}")
            annotate("error", f"promotion hold gate wiring: {problem}")
        return 1
    log("WIRING OK: every publishing job waits for the gate, and the gate is a root job.")
    return 0


# --------------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--branch", default="")
    parser.add_argument("--holds", default=".github/promotion-holds.txt")
    parser.add_argument("--workflow", default=".github/workflows/documentation-pipeline.yml")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-wiring", action="store_true")
    parser.add_argument(
        "--emit-effective-holds",
        default="",
        metavar="PATH",
        help="write the hold list with this promotion's release markers applied, for the "
        "support-docs build gate to enforce (#135)",
    )
    args = parser.parse_args(argv)

    try:
        if args.self_test:
            log("Self-test: proving the gate can go RED and GREEN before trusting it.")
            return self_test()
        if args.check_wiring:
            return check_wiring(os.path.join(args.repo, args.workflow))
        if args.emit_effective_holds:
            holds_path = args.holds
            if not os.path.isabs(holds_path):
                holds_path = os.path.join(args.repo, holds_path)
            return emit_effective_holds(
                args.repo, args.commit, holds_path, args.emit_effective_holds
            )
        if not args.branch:
            raise CheckerError("--branch is required for the check")
        holds_path = args.holds
        if not os.path.isabs(holds_path):
            holds_path = os.path.join(args.repo, holds_path)
        return check(args.repo, args.commit, holds_path, args.branch)
    except CheckerError as exc:
        log(f"CHECKER ERROR: {exc}")
        annotate("error", f"promotion hold check could not run: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
