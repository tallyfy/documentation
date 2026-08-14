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
    """
    holds = parse_holds(holds_path)
    # Resolve to a real SHA. Recording the literal "HEAD" would make the provenance line
    # unusable for anyone trying to work out which promotion produced this list.
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
        f"# Source commit: {resolved}",
    ]
    if dropped:
        lines.append(
            "# Released for this promotion by its commit message: " + ", ".join(sorted(dropped))
        )
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
# Jobs that may legitimately run without waiting for the gate, each with the reason it is
# harmless. Anything NOT listed here must depend on the gate, so adding a job forces a
# decision instead of silently escaping the gate. Derived from the workflow file itself, so
# it grows with the file rather than freezing at today's job list.
WIRING_EXEMPT = {
    GATE_JOB: "the gate itself",
    "validate-markdown": "read-only lint, publishes nothing",
    "generate-snippets": "early-exits on main; writes only to staging",
    "update-last-modified": "early-exits on main; writes only to staging",
    "generate-related-articles": "early-exits on main; writes only to staging",
    "check-deleted-files": "only removes Answers entries for files deleted in this commit; "
                           "cannot publish held content",
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
