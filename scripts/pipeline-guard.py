#!/usr/bin/env python3
"""
pipeline-guard.py - keep the publishing pipeline to one run per branch at a time, and keep
`sync` from publishing a commit no gate read.

MODES

  --head-sha SHA  The publish guard, run by `sync` before it copies anything (work-queue#2748).
                  The gates read the triggering commit, workflow_run.head_sha. `sync` checks
                  out the branch TIP, because the generator jobs push their own commits and
                  those must ship. So the tip may also hold a newer push that no gate read.
                  This proves every commit in head_sha..HEAD is one the generator jobs make,
                  and refuses when any other commit touches a path in generate-ids.yml's
                  `paths:` filter. A refusal is safe: that commit's push started a run of its
                  own, queued behind this one by the concurrency group, which publishes it
                  after its own gates.

                  A newer commit that touches none of those paths is published, and the
                  report names it. It never gets a run of its own, so refusing on it would
                  hold the gated content back until some later content push. That is a direct
                  CLAUDE.md edit (staging carries several), or a changelog page, which the
                  filter excludes on purpose, so no run ever starts for one.
  --check-wiring  Prove the two workflows that publish are still serialized per branch
                  (tallyfy/documentation#296): documentation-pipeline.yml and
                  generate-ids.yml each carry a `concurrency:` group keyed on the branch the
                  run is about, with `cancel-in-progress: false`, and every step that
                  commits and then pulls pulls with --no-rebase.
  --self-test     Prove --check-wiring and the publish guard each go RED on every defect
                  they exist to catch and GREEN on correct input, using fixture files and
                  scratch git repositories, never the real ones.

EXIT CODES
  0  clean (--head-sha: publish)
  1  a wiring defect, a failed self-test case, or (--head-sha) do not publish
  2  the checker could not run - never read as a pass, and never a publish

WHY THE CONCURRENCY GROUPS

On 2026-09-23 #290 and #292 merged into staging eight seconds apart. Run 35813745697's
update-last-modified job failed with "fatal: Need to specify how to reconcile divergent
branches", because run 35813737212 had already pushed the same change. Two runs that both
reach `sync` can finish out of order, and the one that finishes last publishes its tree even
when it is the older one. A group per branch makes them take turns.

`cancel-in-progress: false` is load-bearing: `true` would cancel a running `sync` part way
through its rsync and push. A pull after a commit must say --no-rebase because git refuses a
bare `git pull` on divergent branches when pull.rebase is not configured (measured here on git
2.43.0 and 2.55.0), which is the exact failure above.
"""

import argparse
import os
import re
import subprocess
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
# publish guard (work-queue#2748)

# Who the generator jobs commit as: `git config --local user.name "GitHub Action"` and
# `user.email "action@github.com"` in generate-ids.yml and in documentation-pipeline.yml's
# generate-snippets, update-last-modified and generate-related-articles jobs.
GENERATOR_NAME = "GitHub Action"
GENERATOR_EMAIL = "action@github.com"
# The exact subject each of them commits with, and where.
GENERATED_SUBJECTS = {
    "Push Articles With ID(s)": "generate-ids.yml, which runs before this pipeline starts",
    "Push Articles With snippet(s)": "generate-snippets",
    "Update lastUpdated dates from Git history": "update-last-modified",
    "Push related articles": "generate-related-articles",
}
# What their `git pull --no-rebase` writes when the branch moved under them. Both forms are in
# this repository's history: "Merge branch 'staging' of https://github.com/tallyfy/documentation
# into staging" (663408a52, 2026-08-12) and "Merge branch 'main' of
# https://github.com/tallyfy/documentation" (bb7f0b601, 2026-02-12). A merge adds no commit
# of its own content; whatever it brings in is in head_sha..HEAD and is judged on its own.
GENERATOR_MERGE_RE = re.compile(
    r"^Merge branch '[^']+' of https://github\.com/tallyfy/documentation( into \S+)?$"
)


def trigger_patterns(repo):
    """generate-ids.yml's push `paths:` filter, read from the checkout being published.

    A push that changes a matching path starts generate-ids.yml, and so this pipeline. Read
    from the file rather than copied here, so the two cannot drift apart.
    """
    try:
        import yaml
    except ImportError:
        raise CheckerError("pyyaml is required to read generate-ids.yml's paths filter")
    path = os.path.join(repo, ".github", "workflows", "generate-ids.yml")
    if not os.path.isfile(path):
        raise CheckerError(f"no {path}, so which pushes start a run cannot be read")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    # PyYAML reads the bare key `on` as the boolean True.
    on = doc.get("on", doc.get(True)) or {}
    patterns = ((on.get("push") or {}) if isinstance(on, dict) else {}).get("paths")
    if not patterns or not all(isinstance(p, str) for p in patterns):
        raise CheckerError(f"{path} has no push `paths:` list to read")
    return [_compile_pattern(p) for p in patterns]


def _compile_pattern(pattern):
    """(is_negative, regex) for a GitHub `paths` pattern. Only `*` and `**` are supported;
    anything else is refused rather than guessed at."""
    negative = pattern.startswith("!")
    body = pattern[1:] if negative else pattern
    if re.search(r"[?\[\]+{}]", body):
        raise CheckerError(f"unsupported character in paths pattern {pattern!r}")
    out = ""
    for part in re.split(r"(\*\*|\*)", body):
        out += ".*" if part == "**" else "[^/]*" if part == "*" else re.escape(part)
    return negative, re.compile(out + r"\Z")


def starts_a_run(paths, patterns):
    """True when a change to any of `paths` matches the filter. As GitHub evaluates it: in
    order, a positive match includes a path and a later `!` match excludes it again."""
    for path in paths:
        included = False
        for negative, regex in patterns:
            if regex.match(path):
                included = not negative
        if included:
            return True
    return False


def _git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr.strip()


def generated_by(parents, author_name, author_email, committer_email, subject):
    """Which generator job made this commit, or None when it is not one of theirs."""
    if (author_name, author_email, committer_email) != (
            GENERATOR_NAME, GENERATOR_EMAIL, GENERATOR_EMAIL):
        return None
    if len(parents) == 1 and subject in GENERATED_SUBJECTS:
        return GENERATED_SUBJECTS[subject]
    if len(parents) >= 2 and GENERATOR_MERGE_RE.match(subject):
        return "a generator job's `git pull --no-rebase`"
    return None


def decide(repo, head_sha):
    """(exit code, report lines). 0 publish, 1 do not publish. Raises CheckerError (exit 2)
    whenever it cannot read the answer, so an unreadable range is never a publish."""
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha or ""):
        raise CheckerError(f"--head-sha {head_sha!r} is not a full 40-character commit id")
    rc, out, err = _git(repo, "rev-parse", "--is-shallow-repository")
    if rc != 0:
        raise CheckerError(f"{repo} is not a git checkout: {err}")
    if out.strip() != "false":
        raise CheckerError("this checkout is shallow, so it cannot show whether head_sha is an "
                           "ancestor of the tree about to be published. Check out with "
                           "fetch-depth: 0.")
    rc, out, err = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if rc != 0:
        raise CheckerError(f"HEAD does not resolve to a commit: {err}")
    tip = out.strip()
    if tip == head_sha:
        return 0, [f"PUBLISH: the tree to publish is {tip[:12]}, the commit the gates read."]
    rc, _, _ = _git(repo, "cat-file", "-e", f"{head_sha}^{{commit}}")
    if rc != 0:
        # A full clone holds every ancestor of HEAD, so a commit it lacks is not one.
        return 1, [f"DO NOT PUBLISH: {head_sha[:12]}, the commit the gates read, is not in this "
                   f"full clone, so it is not an ancestor of {tip[:12]}. The branch was rewritten "
                   f"after that push; the run for the rewrite publishes it."]
    rc, _, err = _git(repo, "merge-base", "--is-ancestor", head_sha, tip)
    if rc == 1:
        return 1, [f"DO NOT PUBLISH: {head_sha[:12]}, the commit the gates read, is not an "
                   f"ancestor of {tip[:12]}. The branch was rewritten after that push; the run "
                   f"for the rewrite publishes it."]
    if rc != 0:
        raise CheckerError(f"git merge-base --is-ancestor failed: {err}")
    rc, out, err = _git(repo, "log", "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%ce%x1f%s%x1e",
                        f"{head_sha}..{tip}")
    if rc != 0:
        raise CheckerError(f"git log {head_sha[:12]}..{tip[:12]} failed: {err}")
    records = [r.strip("\n") for r in out.split("\x1e") if r.strip("\n")]
    if not records:
        raise CheckerError(f"{head_sha[:12]} is a proper ancestor of {tip[:12]} but git listed "
                           f"no commits between them")
    patterns = trigger_patterns(repo)
    lines = [f"Commits between {head_sha[:12]} (read by the gates) and {tip[:12]} (about to "
             f"be published), newest first:"]
    foreign, outside = [], []
    for record in records:
        fields = record.split("\x1f")
        if len(fields) != 6:
            raise CheckerError(f"could not parse git log record {record!r}")
        sha, parents, an, ae, ce, subject = fields
        job = generated_by(parents.split(), an, ae, ce, subject)
        if job:
            lines.append(f"  generated  {sha[:12]}  {subject}  ({job})")
            continue
        # -m lists a merge's changes against EACH parent, so a merge is judged on everything
        # it could have brought in, which can only make a refusal more likely.
        rc, out, err = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-m",
                            "--root", sha)
        if rc != 0:
            raise CheckerError(f"could not list the files {sha[:12]} changed: {err}")
        if starts_a_run([f for f in out.splitlines() if f], patterns):
            foreign.append(sha)
            lines.append(f"  NOT GATED  {sha[:12]}  {subject}  (by {an} <{ae}>)")
        else:
            outside.append(sha)
            lines.append(f"  no run     {sha[:12]}  {subject}  (by {an} <{ae}>; touches no path "
                         f"in generate-ids.yml's paths filter)")
    if foreign:
        lines.append(f"DO NOT PUBLISH: {len(foreign)} commit(s) above were pushed after "
                     f"{head_sha[:12]} and no gate in this run read them. The run for the newest "
                     f"of them is queued behind this one and publishes them after its own gates.")
        return 1, lines
    if outside:
        lines.append(f"PUBLISH: every commit after {head_sha[:12]} is the pipeline's own, "
                     f"except {len(outside)} that start no run of their own (marked above). "
                     f"Refusing on those would only hold the gated content back.")
    else:
        lines.append(f"PUBLISH: all {len(records)} commit(s) after {head_sha[:12]} are the "
                     f"pipeline's own generated commits.")
    return 0, lines


def guard(repo, head_sha):
    code, lines = decide(repo, head_sha)
    for line in lines:
        log(line)
    if code != 0:
        annotate("notice", lines[-1])
    return code


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


_HUMAN = ("Amit", "amit@tallyfy.com")
_BOT = (GENERATOR_NAME, GENERATOR_EMAIL)
_STAGING_MERGE = "Merge branch 'staging' of https://github.com/tallyfy/documentation into staging"
_MAIN_MERGE = "Merge branch 'main' of https://github.com/tallyfy/documentation"


_FIXTURE_FILTER = """\
on:
  push:
    paths:
      - src/content/docs/**
      - documentation_assets.csv
      - scripts/**
      - '!src/content/docs/pro/changelog/**'
"""


def _commit(repo, who, subject, merge=None, folder="src/content/docs"):
    """Commit as `who` (name, email) for both author and committer, and return the sha."""
    env = dict(os.environ, GIT_AUTHOR_NAME=who[0], GIT_AUTHOR_EMAIL=who[1],
               GIT_COMMITTER_NAME=who[0], GIT_COMMITTER_EMAIL=who[1])
    base = ["git", "-c", "commit.gpgsign=false"]
    if merge:
        cmd = base + ["merge", "--no-ff", "-q", "-m", subject, merge]
    else:
        # A new file per commit, so two branches never conflict when a case merges them.
        os.makedirs(os.path.join(repo, folder), exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".mdx", dir=os.path.join(repo, folder))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(subject + "\n")
        subprocess.run(["git", "add", os.path.relpath(path, repo)], cwd=repo, check=True,
                       capture_output=True)
        cmd = base + ["commit", "-q", "-m", subject]
    subprocess.run(cmd, cwd=repo, env=env, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def _guard_self_test(tmp, case):
    def fresh(name):
        repo = os.path.join(tmp, name)
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", "-b", "staging"], cwd=repo, check=True,
                       capture_output=True)
        os.makedirs(os.path.join(repo, ".github", "workflows"))
        with open(os.path.join(repo, ".github", "workflows", "generate-ids.yml"), "w",
                  encoding="utf-8") as fh:
            fh.write(_FIXTURE_FILTER)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        _commit(repo, _HUMAN, "An earlier page edit")
        return repo, _commit(repo, _HUMAN, "The push the gates read (#999)")

    def verdict(repo, head):
        import contextlib
        import io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                return guard(repo, head), buf.getvalue()
        except CheckerError as exc:
            return 2, str(exc)

    repo, head = fresh("tip")
    rc, out = verdict(repo, head)
    case("PUBLISH head_sha is the tip", rc == 0, f"rc={rc}")

    repo, head = fresh("generated")
    for subject in GENERATED_SUBJECTS:
        _commit(repo, _BOT, subject)
    rc, out = verdict(repo, head)
    case("PUBLISH only the four generator commits sit after head_sha",
         rc == 0 and out.count("  generated  ") == 4, f"rc={rc}")

    repo, head = fresh("generator-merge")
    subprocess.run(["git", "branch", "other"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Push related articles")
    subprocess.run(["git", "checkout", "-q", "other"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Update lastUpdated dates from Git history")
    subprocess.run(["git", "checkout", "-q", "staging"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, _STAGING_MERGE, merge="other")
    rc, out = verdict(repo, head)
    case("PUBLISH a generator's own merge of two generator commits", rc == 0, f"rc={rc}")

    repo, head = fresh("foreign")
    _commit(repo, _BOT, "Push related articles")
    newer = _commit(repo, _HUMAN, "A newer push nobody gated (#1000)")
    _commit(repo, _BOT, "Update lastUpdated dates from Git history")
    rc, out = verdict(repo, head)
    case("REFUSE a person's commit after head_sha, and name it",
         rc == 1 and f"NOT GATED  {newer[:12]}" in out and "DO NOT PUBLISH" in out, f"rc={rc}")

    repo, head = fresh("foreign-behind-merge")
    subprocess.run(["git", "branch", "other"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Push related articles")
    subprocess.run(["git", "checkout", "-q", "other"], cwd=repo, check=True, capture_output=True)
    newer = _commit(repo, _HUMAN, "A newer push nobody gated (#1000)")
    subprocess.run(["git", "checkout", "-q", "staging"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, _MAIN_MERGE, merge="other")
    rc, out = verdict(repo, head)
    case("REFUSE a person's commit brought in by a generator's merge",
         rc == 1 and f"NOT GATED  {newer[:12]}" in out, f"rc={rc}")

    repo, head = fresh("outside-filter")
    _commit(repo, _BOT, "Push related articles")
    claude_md = _commit(repo, _HUMAN, "docs(CLAUDE.md): a direct edit", folder=".")
    _commit(repo, _HUMAN, "A changelog entry", folder="src/content/docs/pro/changelog/2026")
    rc, out = verdict(repo, head)
    case("PUBLISH newer commits that start no run (CLAUDE.md, a changelog page), and name them",
         rc == 0 and f"no run     {claude_md[:12]}" in out and out.count("  no run  ") == 2,
         f"rc={rc}")

    repo, head = fresh("script-change")
    _commit(repo, _HUMAN, "Change a pipeline script", folder="scripts")
    rc, out = verdict(repo, head)
    case("REFUSE a newer commit to scripts/, which starts a run of its own", rc == 1, f"rc={rc}")

    repo, head = fresh("no-filter")
    os.remove(os.path.join(repo, ".github", "workflows", "generate-ids.yml"))
    newer = _commit(repo, _HUMAN, "A newer push nobody gated (#1000)")
    rc, out = verdict(repo, head)
    case("FAIL CLOSED no readable paths filter is exit 2, never a publish", rc == 2, f"rc={rc}")

    repo, head = fresh("impostor-subject")
    _commit(repo, _HUMAN, "Push related articles")
    rc, out = verdict(repo, head)
    case("REFUSE a generator's subject on a person's commit", rc == 1, f"rc={rc}")

    repo, head = fresh("unknown-subject")
    _commit(repo, _BOT, "Push something new")
    rc, out = verdict(repo, head)
    case("REFUSE a generator commit with a subject no generator job writes", rc == 1, f"rc={rc}")

    repo, head = fresh("fork-merge")
    subprocess.run(["git", "branch", "other"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Push related articles")
    subprocess.run(["git", "checkout", "-q", "other"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Update lastUpdated dates from Git history")
    subprocess.run(["git", "checkout", "-q", "staging"], cwd=repo, check=True, capture_output=True)
    _commit(repo, _BOT, "Merge branch 'staging' of https://github.com/someone/documentation",
            merge="other")
    rc, out = verdict(repo, head)
    case("REFUSE a merge of some other repository", rc == 1, f"rc={rc}")

    repo, head = fresh("rewritten")
    subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=repo, check=True,
                   capture_output=True)
    _commit(repo, _HUMAN, "A rewrite pushed over the gated commit")
    rc, out = verdict(repo, head)
    case("REFUSE head_sha that is not an ancestor of the tip", rc == 1, f"rc={rc}")

    rc, out = verdict(repo, "0123456789abcdef0123456789abcdef01234567")
    case("REFUSE head_sha that a full clone does not have", rc == 1, f"rc={rc}")

    repo, head = fresh("to-clone")
    _commit(repo, _BOT, "Push related articles")
    shallow = os.path.join(tmp, "shallow")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + repo, shallow], check=True,
                   capture_output=True)
    rc, out = verdict(shallow, head)
    case("FAIL CLOSED a shallow checkout is exit 2, never a publish", rc == 2, f"rc={rc}")

    rc, out = verdict(repo, head[:12])
    case("FAIL CLOSED an abbreviated head_sha is exit 2", rc == 2, f"rc={rc}")
    rc, out = verdict(repo, "")
    case("FAIL CLOSED an empty head_sha is exit 2", rc == 2, f"rc={rc}")
    not_git = os.path.join(tmp, "not-a-repo")
    os.makedirs(not_git)
    rc, out = verdict(not_git, head)
    case("FAIL CLOSED a folder that is not a git checkout is exit 2", rc == 2, f"rc={rc}")


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

    log("Self-test: the publish guard publishes only generated commits after head_sha.")
    with tempfile.TemporaryDirectory() as tmp:
        _guard_self_test(tmp, case)

    failed = cases.count(False)
    if failed:
        annotate("error", f"pipeline-guard self-test FAILED ({failed} case(s))")
        log(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    log(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--head-sha", help="the commit the gates read (workflow_run.head_sha)")
    parser.add_argument("--repo", default=".", help="the checkout about to be published")
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
        if args.head_sha is not None:
            return guard(args.repo, args.head_sha)
        parser.print_usage()
        log("CHECKER ERROR: pass --head-sha, --check-wiring or --self-test")
        return 2
    except CheckerError as exc:
        log(f"CHECKER ERROR: {exc}")
        annotate("error", f"pipeline-guard could not run, so nothing is published: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 - deliberate
        # A crash must be 2, never Python's default 1, which here means a wiring defect.
        import traceback
        traceback.print_exc()
        log(f"CHECKER CRASHED: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
