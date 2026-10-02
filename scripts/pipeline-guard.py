#!/usr/bin/env python3
"""
pipeline-guard.py - keep the publishing pipeline to one run per branch at a time.

MODES

  --check-wiring  Prove the two workflows that publish are still serialized per branch
                  (tallyfy/documentation#296): documentation-pipeline.yml and
                  generate-ids.yml each carry a `concurrency:` group keyed on the branch the
                  run is about, with `cancel-in-progress: false`, and every step that
                  commits and then pulls pulls with --no-rebase.
  --self-test     Prove --check-wiring goes RED on each defect it exists to catch and GREEN
                  on a correct pair of workflows, using fixture files, never the real ones.

EXIT CODES
  0  clean
  1  a wiring defect (or a failed self-test case)
  2  the checker could not run - never read as a pass

WHY THE CONCURRENCY GROUPS

On 2026-09-23 #290 and #292 merged into staging eight seconds apart. Run 35813745697's
update-last-modified job failed with "fatal: Need to specify how to reconcile divergent
branches", because run 35813737212 had already pushed the same change. Two runs that both
reach `sync` can finish out of order, and the one that finishes last publishes its tree even
when it is the older one. A group per branch makes them take turns.

`cancel-in-progress: false` is load-bearing: `true` would cancel a running `sync` part way
through its rsync and push. A pull after a commit must say --no-rebase because git 2.27 and
later refuse a bare `git pull` on divergent branches unless pull.rebase is configured, which
is the exact failure above.
"""

import argparse
import os
import re
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(REPO_ROOT, ".github", "workflows", "documentation-pipeline.yml")
GENERATE_IDS = os.path.join(REPO_ROOT, ".github", "workflows", "generate-ids.yml")

# The expression each group must be keyed on: the branch the run is about. The pipeline runs
# on workflow_run, where github.ref is the DEFAULT branch whatever branch was pushed, so it
# must key on the triggering run's head_branch. generate-ids runs on push, where github.ref is
# the pushed branch.
PIPELINE_KEY = "github.event.workflow_run.head_branch"
GENERATE_IDS_KEY = "github.ref"


class CheckerError(Exception):
    """The checker could not do its job. Always exit 2, never a pass."""


def log(msg=""):
    print(msg, flush=True)


def annotate(level, msg):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


def load_workflow(path):
    try:
        import yaml
    except ImportError:
        raise CheckerError("pyyaml is required for --check-wiring")
    if not os.path.isfile(path):
        raise CheckerError(f"workflow not found at {path}")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict) or not doc.get("jobs"):
        raise CheckerError(f"{path} declares no jobs")
    return doc


def _expressions(text):
    """The `${{ ... }}` expressions in text, with their whitespace normalized."""
    return [re.sub(r"\s+", " ", m.strip()) for m in re.findall(r"\$\{\{(.*?)\}\}", text)]


def check_concurrency(doc, name, key):
    """Problems with a workflow's top-level concurrency group, as a list of strings."""
    conc = doc.get("concurrency")
    if conc is None:
        return [f"{name} has no top-level `concurrency:` group, so two runs for one branch can "
                f"work on it at once (see #296)."]
    if not isinstance(conc, dict):
        # The short form `concurrency: <group>` cancels nothing in progress, but it cannot say
        # so in the file, and the next edit to it would have nowhere to put the setting.
        return [f"{name} uses the short `concurrency:` form; write `group:` and "
                f"`cancel-in-progress: false` out in full so the choice is visible."]
    problems = []
    group = conc.get("group")
    if not isinstance(group, str) or key not in _expressions(group):
        problems.append(
            f"{name}'s concurrency group is {group!r}, which is not keyed on "
            f"`${{{{ {key} }}}}`. A group without the branch in it serializes every branch "
            f"behind every other; a group keyed on something else does not serialize one branch."
        )
    if conc.get("cancel-in-progress") is not False:
        problems.append(
            f"{name} has `cancel-in-progress: {conc.get('cancel-in-progress')!r}`. It must be "
            f"the literal `false`: anything that can be true cancels a running `sync` part way "
            f"through publishing."
        )
    return problems


# Start of a shell command: the start of the line, or after `;`, `&&`, `||` or `|`.
COMMAND_AT = r"(?:^|[;&|])\s*"


def check_pull_after_commit(doc, name):
    """Every step that commits and pulls must pull with --no-rebase."""
    problems = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            if not isinstance(step, dict):
                continue
            # Comments dropped, and only `git` in command position counts, so neither
            # `# git pull --no-rebase` nor `echo "... git pull"` satisfies or trips this.
            lines = [re.sub(r"(^|\s)#.*$", "", raw) for raw in str(step.get("run", "")).splitlines()]
            if not any(re.search(COMMAND_AT + r"git\s+commit\b", line) for line in lines):
                continue
            for line in lines:
                if re.search(COMMAND_AT + r"git\s+pull\b", line) and "--no-rebase" not in line:
                    problems.append(
                        f"{name} job {job_name!r} step {step.get('name')!r} commits and then "
                        f"runs {line.strip()!r} without --no-rebase. On divergent branches git "
                        f"refuses that with 'Need to specify how to reconcile divergent "
                        f"branches', which is how run 35813745697 failed (see #296)."
                    )
    return problems


def check_wiring(pipeline_path=PIPELINE, generate_ids_path=GENERATE_IDS):
    pipeline = load_workflow(pipeline_path)
    generate_ids = load_workflow(generate_ids_path)
    pname, gname = os.path.basename(pipeline_path), os.path.basename(generate_ids_path)

    problems = []
    problems += check_concurrency(pipeline, pname, PIPELINE_KEY)
    problems += check_concurrency(generate_ids, gname, GENERATE_IDS_KEY)
    pg = (pipeline.get("concurrency") or {}) if isinstance(pipeline.get("concurrency"), dict) else {}
    gg = (generate_ids.get("concurrency") or {}) if isinstance(generate_ids.get("concurrency"), dict) else {}
    if pg.get("group") is not None and pg.get("group") == gg.get("group"):
        # Groups are repository-wide. A shared one would let a generate-ids run waiting in the
        # queue displace a waiting pipeline run, or the other way round.
        problems.append(f"{pname} and {gname} share the concurrency group {pg.get('group')!r}.")
    problems += check_pull_after_commit(pipeline, pname)
    problems += check_pull_after_commit(generate_ids, gname)

    log(f"Workflows: {pname}, {gname}.")
    if problems:
        for problem in problems:
            log(f"WIRING FAIL: {problem}")
            annotate("error", f"pipeline wiring: {problem}")
        return 1
    log(f"WIRING OK: {pname} is grouped on {PIPELINE_KEY} and {gname} on {GENERATE_IDS_KEY}, "
        f"neither cancels a run in progress, and every pull after a commit says --no-rebase.")
    return 0


# ---------------------------------------------------------------------------------------
# self-test

_GOOD_PIPELINE = """\
name: Documentation Pipeline
on:
  workflow_run:
    workflows: ["Tallyfy Answers - Generate IDs"]
    types: [completed]
concurrency:
  group: documentation-pipeline-${{ github.event.workflow_run.head_branch }}
  cancel-in-progress: false
jobs:
  update-last-modified:
    runs-on: ubuntu-latest
    steps:
      - name: Commit and push lastUpdated dates
        run: |
          git commit -m "Update lastUpdated dates from Git history" -a
          git pull --no-rebase   # a trailing comment is not the flag
          git push
          echo "No changes to commit after git pull"
"""

_GOOD_GENERATE_IDS = """\
name: Tallyfy Answers - Generate IDs
on:
  push:
    branches: [main, staging]
concurrency:
  group: generate-ids-${{ github.ref }}
  cancel-in-progress: false
jobs:
  generate-ids:
    runs-on: ubuntu-latest
    steps:
      - name: Generate IDs script
        run: |
          git pull
      - name: Commit and push new articles with IDs
        run: |
          git pull --no-rebase
          git commit -m "Push Articles With ID(s)"
          git push
"""


def self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        log(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    def wiring(pipeline_text, generate_ids_text, tmp, tag):
        p = os.path.join(tmp, f"{tag}-pipeline.yml")
        g = os.path.join(tmp, f"{tag}-generate-ids.yml")
        if pipeline_text is not None:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(pipeline_text)
        if generate_ids_text is not None:
            with open(g, "w", encoding="utf-8") as fh:
                fh.write(generate_ids_text)
        import contextlib
        import io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = check_wiring(p, g)
        except CheckerError as exc:
            rc = 2
            buf.write(str(exc))
        return rc, buf.getvalue()

    log("Self-test: --check-wiring goes red on each defect and green on correct workflows.")
    gp, gi = _GOOD_PIPELINE, _GOOD_GENERATE_IDS
    no_group = re.sub(r"(?m)^concurrency:\n(  .*\n)+", "", gp)
    red = [
        ("the pipeline has no concurrency group", no_group, gi),
        ("the pipeline cancels a run in progress",
         gp.replace("cancel-in-progress: false", "cancel-in-progress: true"), gi),
        ("the pipeline's cancel-in-progress is an expression, not the literal false",
         gp.replace("cancel-in-progress: false", "cancel-in-progress: ${{ false }}"), gi),
        ("the pipeline group is not keyed on the branch",
         gp.replace("-${{ github.event.workflow_run.head_branch }}", ""), gi),
        ("the pipeline group is keyed on github.ref, the DEFAULT branch on workflow_run",
         gp.replace("github.event.workflow_run.head_branch", "github.ref"), gi),
        ("generate-ids has no concurrency group",
         gp, re.sub(r"(?m)^concurrency:\n(  .*\n)+", "", gi)),
        ("generate-ids is keyed on the commit, so it serializes nothing",
         gp, gi.replace("github.ref", "github.sha")),
        ("generate-ids cancels a run in progress",
         gp, gi.replace("cancel-in-progress: false", "cancel-in-progress: true")),
        ("both workflows share one group",
         gp, gi.replace("generate-ids-${{ github.ref }}",
                        "documentation-pipeline-${{ github.event.workflow_run.head_branch }}")),
        ("a step commits and then pulls without --no-rebase (#296)",
         gp.replace("git pull --no-rebase   # a trailing comment is not the flag",
                    "git pull   # --no-rebase"), gi),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = wiring(gp, gi, tmp, "good")
        case("GREEN correct workflows pass, including a bare pull in a step that commits "
             "nothing and an echo that mentions git pull", rc == 0, f"rc={rc}")
        for i, (name, p, g) in enumerate(red):
            rc, out = wiring(p, g, tmp, f"red{i}")
            case(f"RED {name}", rc == 1 and "WIRING FAIL" in out, f"rc={rc}")
        rc, out = wiring(None, gi, tmp, "missing")
        case("FAIL CLOSED a missing workflow file is exit 2, never a pass", rc == 2, f"rc={rc}")
        rc, out = wiring("jobs: {}\n", gi, tmp, "nojobs")
        case("FAIL CLOSED a workflow with no jobs is exit 2", rc == 2, f"rc={rc}")

    failed = cases.count(False)
    if failed:
        annotate("error", f"pipeline-guard self-test FAILED ({failed} case(s))")
        log(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    log(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check-wiring", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--pipeline", default=PIPELINE)
    parser.add_argument("--generate-ids", default=GENERATE_IDS)
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            return self_test()
        if args.check_wiring:
            return check_wiring(args.pipeline, args.generate_ids)
        parser.print_usage()
        log("CHECKER ERROR: pass --check-wiring or --self-test")
        return 2
    except CheckerError as exc:
        log(f"CHECKER ERROR: {exc}")
        annotate("error", f"pipeline-guard could not run: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - deliberate
        # A crash must be 2, never Python's default 1, which here means a wiring defect.
        import traceback
        traceback.print_exc()
        log(f"CHECKER CRASHED: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
