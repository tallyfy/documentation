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
                  CLAUDE.md edit (staging carries several). Until #475 (2026-11-06) the filter
                  also excluded changelog pages, so one was published this way too; it now
                  starts a run of its own. The self-test keeps that exclusion in its own
                  fixture filter, to test a commit outside the filter.
  --check-wiring  Prove the two workflows that publish are still serialized per branch
                  (tallyfy/documentation#296): documentation-pipeline.yml and
                  generate-ids.yml each carry a `concurrency:` group keyed on the branch the
                  run is about, with `cancel-in-progress: false`, and every step that
                  commits and then pulls pulls with --no-rebase.
                  Since #464 it also proves the R2 upload credentials cannot reach a pull
                  request: no workflow uses pull_request_target; no workflow a pull request
                  starts names `secrets` or an `environment`; the r2-screenshots environment
                  is named by the repo-screenshots job alone; its three secrets reach one step,
                  the staging-only ingest, through that step's `env`. And that the job is wired
                  in: generate-snippets and sync wait for it, generate-ids.yml starts on a
                  screenshots/ change, and every commit the pipeline makes as "GitHub Action"
                  uses a subject the publish guard knows.
                  And that a push-gate job runs first in both workflows, unskippable, from an
                  inline actions/github-script step with no checkout, with the same script in
                  both, and that every job holding a secret other than GITHUB_TOKEN, an
                  environment or a `git push` waits for it (a status-function `if:` directly).
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


# ---------------------------------------------------------------------------------------
# the repository screenshots job and its credentials (tallyfy/documentation#464)

SCREENSHOT_JOB = "repo-screenshots"
SCREENSHOT_ENV = "r2-screenshots"
SCREENSHOT_SECRETS = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID")
INGEST_COMMAND = "repo_screenshots.py ingest"
INGEST_BRANCH_TERM = "github.event.workflow_run.head_branch == 'staging'"
# Jobs that must wait for the screenshots job: sync publishes the inventory it commits, and
# generate-snippets starts the chain of generator jobs that push after it.
WAITS_FOR_SCREENSHOTS = ("generate-snippets", "sync")
# A path a LaunchBrightly pull request changes, which must start the pipeline.
SCREENSHOT_SAMPLE_PATH = "screenshots/launchbrightly/example.png"
PR_TRIGGERS = ("pull_request", "pull_request_target")
# Any use of the secrets context in an expression: secrets.X, secrets['X'], toJSON(secrets).
_SECRETS_RE = re.compile(r"\$\{\{[^}]*\bsecrets\b")


def _triggers(doc):
    # PyYAML reads the bare key `on` as the boolean True.
    on = doc.get("on", doc.get(True))
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(t) for t in on}
    if isinstance(on, dict):
        return {str(t) for t in on}
    return set()


def _walk(node, where=()):
    """(location, key, value) for every mapping entry and list item, depth first."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield where + (key,), key, value
            yield from _walk(value, where + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield where + (i,), None, value
            yield from _walk(value, where + (i,))


def _where(name, location):
    return f"{name}: " + ".".join(str(p) for p in location)


def _environment_name(job):
    env = (job or {}).get("environment")
    return env.get("name") if isinstance(env, dict) else env


def check_secret_exposure(workflows, pname):
    """workflows: {file name: parsed doc}; pname: the pipeline's file name. Problems that would
    let a pull request reach the R2 credentials, as a list of strings."""
    problems = []
    env_places = {("jobs", SCREENSHOT_JOB, "environment"), ("jobs", SCREENSHOT_JOB, "environment", "name")}
    for name, doc in sorted(workflows.items()):
        triggers = _triggers(doc)
        if "pull_request_target" in triggers:
            problems.append(f"{name} runs on pull_request_target, which hands a pull request's code "
                            f"the repository's secrets. Use pull_request.")
        if triggers & set(PR_TRIGGERS):
            for location, key, value in _walk(doc):
                if key == "environment":
                    problems.append(f"{_where(name, location)}: a workflow a pull request starts may "
                                    f"not name an environment")
                if key == "secrets":
                    problems.append(f"{_where(name, location)}: a workflow a pull request starts may "
                                    f"not pass secrets on")
                if isinstance(value, str) and _SECRETS_RE.search(value):
                    problems.append(f"{_where(name, location)}: a workflow a pull request starts may "
                                    f"not read secrets")
        in_pipeline = name == pname
        for location, key, value in _walk(doc):
            if not isinstance(value, str):
                continue
            if SCREENSHOT_ENV in value and not (in_pipeline and location in env_places):
                problems.append(f"{_where(name, location)} names {SCREENSHOT_ENV}; only the "
                                f"{SCREENSHOT_JOB} job's `environment` may")
            in_job = in_pipeline and location[:2] == ("jobs", SCREENSHOT_JOB)
            for secret in SCREENSHOT_SECRETS:
                if re.search(r"\b" + secret + r"\b", value) and not in_job:
                    problems.append(f"{_where(name, location)} names {secret}; only the "
                                    f"{SCREENSHOT_JOB} job's ingest step may")
    return problems


def check_screenshot_job(pipeline, pname):
    """The repo-screenshots job: its environment, where its secrets go, and who waits for it."""
    jobs = pipeline.get("jobs") or {}
    job = jobs.get(SCREENSHOT_JOB)
    if not isinstance(job, dict):
        return [f"{pname} has no {SCREENSHOT_JOB!r} job, so screenshots committed under "
                f"screenshots/launchbrightly/ are never uploaded and the support-docs build "
                f"cannot resolve their links (#464)."]
    problems = []
    if _environment_name(job) != SCREENSHOT_ENV:
        problems.append(f"{pname} job {SCREENSHOT_JOB!r} does not use the {SCREENSHOT_ENV!r} "
                        f"environment, which holds its upload credentials.")
    steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
    ingest = [i for i, s in enumerate(steps) if INGEST_COMMAND in str(s.get("run", ""))]
    if len(ingest) != 1:
        problems.append(f"{pname} job {SCREENSHOT_JOB!r} must have exactly one step running "
                        f"`{INGEST_COMMAND}`; it has {len(ingest)}.")
    for location, key, value in _walk(job):
        if not (isinstance(value, str) and _SECRETS_RE.search(value)):
            continue
        in_ingest_env = (len(ingest) == 1 and location[:2] == ("steps", ingest[0])
                         and len(location) == 4 and location[2] == "env")
        if not in_ingest_env:
            problems.append(f"{pname} jobs.{SCREENSHOT_JOB}." + ".".join(str(p) for p in location)
                            + " reads a secret; only the ingest step's `env` may.")
    if len(ingest) == 1:
        step = steps[ingest[0]]
        env = step.get("env") or {}
        for secret in SCREENSHOT_SECRETS:
            wanted = "${{ secrets." + secret + " }}"
            if re.sub(r"\s+", " ", str(env.get(secret, ""))) != wanted:
                problems.append(f"{pname} job {SCREENSHOT_JOB!r}'s ingest step does not set "
                                f"{secret}: {wanted} in its `env`.")
        extra = sorted(k for k, v in env.items() if _SECRETS_RE.search(str(v)) and k not in SCREENSHOT_SECRETS)
        if extra:
            problems.append(f"{pname} job {SCREENSHOT_JOB!r}'s ingest step reads other secrets: {extra}.")
        condition = re.sub(r"\s+", " ", str(step.get("if", ""))).replace('"', "'")
        if INGEST_BRANCH_TERM not in condition:
            problems.append(f"{pname} job {SCREENSHOT_JOB!r}'s ingest step must carry "
                            f"`if: {INGEST_BRANCH_TERM}`, so it uploads from staging only.")
    for name in WAITS_FOR_SCREENSHOTS:
        raw = (jobs.get(name) or {}).get("needs") or []
        needs = [raw] if isinstance(raw, str) else list(raw)
        if name in jobs and SCREENSHOT_JOB not in needs:
            problems.append(f"{pname} job {name!r} does not name {SCREENSHOT_JOB!r} in its `needs`, "
                            f"so it can run before the inventory commit lands.")
    return problems


def check_generated_subjects(doc, name):
    """Every commit a step makes as GitHub Action uses a subject GENERATED_SUBJECTS knows, or the
    publish guard reads it as a person's commit and `sync` refuses to publish."""
    problems = []
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in (job or {}).get("steps") or []:
            if not isinstance(step, dict):
                continue
            run = "\n".join(re.sub(r"(^|\s)#.*$", "", raw) for raw in str(step.get("run", "")).splitlines())
            if not re.search(r"user\.name\s+[\"']" + re.escape(GENERATOR_NAME) + r"[\"']", run):
                continue
            for line in run.splitlines():
                if not re.search(COMMAND_AT + r"git\s+commit\b", line):
                    continue
                m = re.search(r"\s-m\s+([\"'])(.*?)\1", line)
                if not m:
                    problems.append(f"{name} job {job_name!r} commits as {GENERATOR_NAME!r} with no "
                                    f"readable -m subject: {line.strip()!r}")
                elif m.group(2) not in GENERATED_SUBJECTS:
                    problems.append(f"{name} job {job_name!r} commits as {GENERATOR_NAME!r} with the "
                                    f"subject {m.group(2)!r}, which GENERATED_SUBJECTS in "
                                    f"pipeline-guard.py does not list, so `sync` would refuse to "
                                    f"publish after it.")
    return problems


def check_screenshot_trigger(generate_ids, gname):
    on = generate_ids.get("on", generate_ids.get(True)) or {}
    paths = ((on.get("push") or {}) if isinstance(on, dict) else {}).get("paths")
    if paths is None:
        return []  # no filter: every push starts a run
    patterns = [_compile_pattern(p) for p in paths]
    if not starts_a_run([SCREENSHOT_SAMPLE_PATH], patterns):
        return [f"{gname}'s push `paths:` filter does not match {SCREENSHOT_SAMPLE_PATH}, so a "
                f"merged LaunchBrightly pull request starts no pipeline run and its images are "
                f"never uploaded. Add `screenshots/**`."]
    return []


# ---------------------------------------------------------------------------------------
# the push gate (tallyfy/documentation#464): a GitHub App with contents: write can push to
# staging or main directly, and a ruleset cannot exempt the pipeline's own pushes, so a first job
# stops everything that holds a secret, an environment or a push when that happens

PUSH_GATE_JOB = "push-gate"
PUSH_GATE_ACTION = "actions/github-script@"
# secrets.NAME, secrets['NAME'], or the bare context, as in toJSON(secrets).
_SECRET_USE_RE = re.compile(r"\bsecrets\b(?:\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)|\s*\[\s*['\"]([^'\"]+)['\"]\s*\])?")
_STATUS_FUNCTION_RE = re.compile(r"\b(?:always|failure|cancelled|success)\s*\(")


def _needs_list(job):
    raw = (job or {}).get("needs") or []
    return [raw] if isinstance(raw, str) else list(raw)


def _needs_closure(jobs, name):
    seen, todo = set(), list(_needs_list(jobs.get(name)))
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo += _needs_list(jobs.get(n))
    return seen


def _reads_secret(job):
    """True when a job uses any secret other than GITHUB_TOKEN, or passes secrets on."""
    for location, key, value in _walk(job):
        if key == "secrets":
            return True
        if isinstance(value, str):
            for expr in _expressions(value):
                for m in _SECRET_USE_RE.finditer(expr):
                    if (m.group(1) or m.group(2)) != "GITHUB_TOKEN":
                        return True
    return False


def _pushes(job):
    for step in (job or {}).get("steps") or []:
        if not isinstance(step, dict):
            continue
        for raw in str(step.get("run", "")).splitlines():
            if re.search(COMMAND_AT + r"git\s+push\b", re.sub(r"(^|\s)#.*$", "", raw)):
                return True
    return False


def gate_script(doc):
    """The inline script of a workflow's push-gate job, or None."""
    gate = (doc.get("jobs") or {}).get(PUSH_GATE_JOB)
    steps = [s for s in ((gate or {}).get("steps") or []) if isinstance(s, dict)]
    scripts = [str((s.get("with") or {}).get("script", "")) for s in steps
               if str(s.get("uses", "")).startswith(PUSH_GATE_ACTION)]
    return scripts[0] if len(scripts) == 1 else None


def check_push_gate(doc, name):
    """The push gate runs first, unskippable, from inline code only, and every job that holds a
    secret, an environment or a push waits for it."""
    jobs = doc.get("jobs") or {}
    gate = jobs.get(PUSH_GATE_JOB)
    if not isinstance(gate, dict):
        return [f"{name} has no {PUSH_GATE_JOB!r} job, so a commit a GitHub App pushed straight to "
                f"the branch reaches every job that holds a secret (#464)."]
    problems = []
    if _needs_list(gate):
        problems.append(f"{name} job {PUSH_GATE_JOB!r} has `needs`; it must be the first job, so a "
                        f"failure elsewhere cannot skip it.")
    if gate.get("if") is not None:
        problems.append(f"{name} job {PUSH_GATE_JOB!r} has an `if:`; a gate that can be skipped lets a "
                        f"status-function job such as sync run without it.")
    steps = [s for s in (gate.get("steps") or []) if isinstance(s, dict)]
    if not steps:
        problems.append(f"{name} job {PUSH_GATE_JOB!r} has no steps.")
    for i, step in enumerate(steps, start=1):
        script = str((step.get("with") or {}).get("script", "")).strip()
        if "run" in step or not str(step.get("uses", "")).startswith(PUSH_GATE_ACTION) or not script:
            problems.append(f"{name} job {PUSH_GATE_JOB!r} step {i} must be {PUSH_GATE_ACTION}... with "
                            f"an inline script. The gate may not check out or run code from the "
                            f"repository, which the push it judges could have changed.")
    perms = gate.get("permissions")
    if not isinstance(perms, dict) or perms.get("issues") != "write" \
            or perms.get("contents") not in (None, "read"):
        problems.append(f"{name} job {PUSH_GATE_JOB!r} needs its own `permissions:` with "
                        f"`issues: write` and no more than `contents: read`.")
    for job_name, job in jobs.items():
        if job_name == PUSH_GATE_JOB or not isinstance(job, dict):
            continue
        if not (_reads_secret(job) or "environment" in job or _pushes(job)):
            continue
        if PUSH_GATE_JOB not in _needs_closure(jobs, job_name):
            problems.append(f"{name} job {job_name!r} holds a secret, an environment or a push but does "
                            f"not wait for {PUSH_GATE_JOB!r}, directly or through `needs`.")
        elif _STATUS_FUNCTION_RE.search(str(job.get("if", ""))) and PUSH_GATE_JOB not in _needs_list(job):
            problems.append(f"{name} job {job_name!r} has a status-function `if:`, so it must name "
                            f"{PUSH_GATE_JOB!r} in its own `needs`, not only through another job.")
    return problems


def check_gate_scripts_match(pipeline, generate_ids, pname, gname):
    a, b = gate_script(pipeline), gate_script(generate_ids)
    if a and b and a != b:
        return [f"the {PUSH_GATE_JOB!r} scripts in {pname} and {gname} differ; they must be identical, "
                f"with only their env telling them apart."]
    return []


def load_workflows(folder):
    docs = {}
    for entry in sorted(os.listdir(folder)):
        if entry.endswith((".yml", ".yaml")):
            docs[entry] = load_workflow(os.path.join(folder, entry))
    return docs


def check_wiring(pipeline_path=PIPELINE, generate_ids_path=GENERATE_IDS):
    pipeline = load_workflow(pipeline_path)
    generate_ids = load_workflow(generate_ids_path)
    pname, gname = os.path.basename(pipeline_path), os.path.basename(generate_ids_path)

    problems = []
    problems += check_secret_exposure(load_workflows(os.path.dirname(os.path.abspath(pipeline_path))), pname)
    problems += check_screenshot_job(pipeline, pname)
    problems += check_generated_subjects(pipeline, pname)
    problems += check_generated_subjects(generate_ids, gname)
    problems += check_screenshot_trigger(generate_ids, gname)
    problems += check_push_gate(pipeline, pname)
    problems += check_push_gate(generate_ids, gname)
    problems += check_gate_scripts_match(pipeline, generate_ids, pname, gname)
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
        f"neither cancels a run in progress, and every pull after a commit says --no-rebase. "
        f"No pull request workflow can read a secret or an environment, {SCREENSHOT_ENV} and its "
        f"secrets reach only the staging ingest step of {SCREENSHOT_JOB}, which "
        f"{' and '.join(WAITS_FOR_SCREENSHOTS)} wait for, and every generator commit subject is known. "
        f"{PUSH_GATE_JOB} runs first in both workflows from one inline script, and every job that "
        f"holds a secret, an environment or a push waits for it.")
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
    "Inventory repository screenshots": "repo-screenshots",
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
  push-gate:
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      pull-requests: read
      issues: write
    steps:
      - uses: actions/github-script@v9
        with:
          script: |
            core.info('the push gate')
  validate-markdown:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/markdown-lint.py
  repo-screenshots:
    needs: [validate-markdown, push-gate]
    runs-on: ubuntu-latest
    environment: r2-screenshots
    steps:
      - name: Verify on main
        if: ${{ github.event.workflow_run.head_branch == 'main' }}
        run: python scripts/asset_management/repo_screenshots.py verify --online
      - name: Upload and record on staging
        if: ${{ github.event.workflow_run.head_branch == 'staging' }}
        env:
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: python scripts/asset_management/repo_screenshots.py ingest
      - name: Commit the inventory
        if: ${{ github.event.workflow_run.head_branch == 'staging' }}
        run: |
          git config --local user.name "GitHub Action"
          git commit -m "Inventory repository screenshots" -- documentation_assets.csv
          git pull --no-rebase
          git push
  generate-snippets:
    needs: [validate-markdown, repo-screenshots]
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/generate-snippets.py --token ${{ secrets.CLAUDE_API_KEY }}
  update-last-modified:
    needs: push-gate
    runs-on: ubuntu-latest
    steps:
      - name: Commit and push lastUpdated dates
        run: |
          git commit -m "Update lastUpdated dates from Git history" -a
          git pull --no-rebase   # a trailing comment is not the flag
          git push
          echo "No changes to commit after git pull"
  sync:
    needs: [push-gate, validate-markdown, repo-screenshots]
    if: ${{ !failure() && !cancelled() }}
    runs-on: ubuntu-latest
    steps:
      - run: echo publish with ${{ secrets.GH_TOKEN }}
"""

_GOOD_PR = """\
name: PR validation
on:
  pull_request:
permissions:
  contents: read
jobs:
  lb-pr-guard:
    runs-on: ubuntu-latest
    steps:
      - name: Check what this pull request changes
        env:
          PR_AUTHOR_LOGIN: ${{ github.event.pull_request.user.login }}
          PR_AUTHOR_ID: ${{ github.event.pull_request.user.id }}
        run: python scripts/lb-pr-guard.py
"""

_GOOD_GENERATE_IDS = """\
name: Tallyfy Answers - Generate IDs
on:
  push:
    branches: [main, staging]
    paths:
      - src/content/docs/**
      - screenshots/**
      - '!src/content/docs/pro/changelog/**'
concurrency:
  group: generate-ids-${{ github.ref }}
  cancel-in-progress: false
jobs:
  push-gate:
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      pull-requests: read
      issues: write
    steps:
      - uses: actions/github-script@v9
        with:
          script: |
            core.info('the push gate')
  generate-ids:
    needs: push-gate
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
    case(f"PUBLISH only the {len(GENERATED_SUBJECTS)} generator commits sit after head_sha",
         rc == 0 and out.count("  generated  ") == len(GENERATED_SUBJECTS), f"rc={rc}")

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

    def wiring(pipeline_text, generate_ids_text, tmp, tag, extra=None):
        # One folder per case, because --check-wiring reads every workflow beside the pipeline.
        folder = os.path.join(tmp, tag)
        os.makedirs(folder)
        p = os.path.join(folder, "documentation-pipeline.yml")
        g = os.path.join(folder, "generate-ids.yml")
        if pipeline_text is not None:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(pipeline_text)
        if generate_ids_text is not None:
            with open(g, "w", encoding="utf-8") as fh:
                fh.write(generate_ids_text)
        for name, text in dict({"pr-validate.yml": _GOOD_PR}, **(extra or {})).items():
            with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                fh.write(text)
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
    env_line = "    environment: r2-screenshots\n"
    ingest_if = ("        if: ${{ github.event.workflow_run.head_branch == 'staging' }}\n"
                 "        env:\n")
    commit_step = "      - name: Commit the inventory\n"
    # (name, pipeline, generate-ids, extra workflow files, text the report must contain)
    red_464 = [
        ("the R2 environment is on another job (#464)",
         gp.replace(env_line, "").replace("  sync:\n", "  sync:\n" + env_line), gi, None,
         "only the repo-screenshots job's `environment` may"),
        ("the screenshots job has no environment (#464)", gp.replace(env_line, ""), gi, None,
         "does not use the 'r2-screenshots' environment"),
        ("an R2 secret in the job's own env, where every step sees it (#464)",
         gp.replace(env_line, env_line + "    env:\n      R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}\n"),
         gi, None, "reads a secret; only the ingest step's `env` may"),
        ("an R2 secret in a second step (#464)",
         gp.replace(commit_step, commit_step + "        env:\n"
                    "          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}\n"),
         gi, None, "reads a secret; only the ingest step's `env` may"),
        ("toJSON(secrets) in another step of the job (#464)",
         gp.replace("run: python scripts/asset_management/repo_screenshots.py verify --online",
                    "run: echo '${{ toJSON(secrets) }}'"), gi, None, "reads a secret"),
        ("the ingest step is not limited to staging (#464)",
         gp.replace(ingest_if, "        env:\n"), gi, None, "so it uploads from staging only"),
        ("the ingest step lacks one of its secrets (#464)",
         gp.replace("          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}\n", ""), gi, None,
         "does not set CLOUDFLARE_ACCOUNT_ID"),
        ("the pipeline has no repo-screenshots job (#464)",
         re.sub(r"(?s)  repo-screenshots:\n.*?(?=  generate-snippets:\n)", "", gp), gi, None,
         "has no 'repo-screenshots' job"),
        ("sync does not wait for the screenshots job (#464)",
         gp.replace("[push-gate, validate-markdown, repo-screenshots]", "[push-gate, validate-markdown]"),
         gi, None, "job 'sync' does not name"),
        ("generate-snippets does not wait for the screenshots job (#464)",
         gp.replace("  generate-snippets:\n    needs: [validate-markdown, repo-screenshots]",
                    "  generate-snippets:\n    needs: validate-markdown"), gi, None,
         "job 'generate-snippets' does not name"),
        ("a generator commit subject the publish guard does not know (#464)",
         gp.replace("Inventory repository screenshots", "Record the screenshots"), gi, None,
         "which GENERATED_SUBJECTS"),
        ("generate-ids does not start on a screenshots/ change (#464)",
         gp, gi.replace("      - screenshots/**\n", ""), None, "does not match screenshots/launchbrightly/"),
        ("a workflow runs on pull_request_target (#464)",
         gp, gi, {"pr-validate.yml": _GOOD_PR.replace("pull_request:", "pull_request_target:")},
         "runs on pull_request_target"),
        ("a pull request workflow reads a secret (#464)",
         gp, gi, {"pr-validate.yml": _GOOD_PR.replace("github.event.pull_request.user.id",
                                                       "secrets.ANSWERS_API_KEY")},
         "may not read secrets"),
        ("a pull request workflow names an environment (#464)",
         gp, gi, {"pr-validate.yml": _GOOD_PR.replace("    runs-on: ubuntu-latest\n",
                                                       "    runs-on: ubuntu-latest\n    environment: preview\n")},
         "may not name an environment"),
        ("a pull request workflow in list form reads a secret (#464)",
         gp, gi, {"other.yml": "on: [push, pull_request]\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
                               "    steps:\n      - run: echo ${{ secrets.GH_TOKEN }}\n"},
         "may not read secrets"),
        ("a pull request workflow passes secrets to a reusable workflow (#464)",
         gp, gi, {"other.yml": "on: pull_request\njobs:\n  a:\n    uses: ./.github/workflows/x.yml\n"
                               "    secrets: inherit\n"},
         "may not pass secrets on"),
        ("another workflow names an R2 secret (#464)",
         gp, gi, {"other.yml": "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
                               "      - run: echo ${{ secrets.R2_ACCESS_KEY_ID }}\n"},
         "names R2_ACCESS_KEY_ID"),
        ("a job that reads a secret does not wait for push-gate (#464)",
         gp.replace("  sync:\n", "  leaky:\n    runs-on: ubuntu-latest\n    steps:\n"
                    "      - run: echo ${{ secrets.ANSWERS_API_KEY }}\n  sync:\n"), gi, None,
         "job 'leaky' holds a secret, an environment or a push but does not wait for 'push-gate'"),
        ("a job that pushes does not wait for push-gate (#464)",
         gp.replace("  update-last-modified:\n    needs: push-gate\n", "  update-last-modified:\n"), gi, None,
         "job 'update-last-modified' holds a secret, an environment or a push but does not wait"),
        ("generate-ids pushes without waiting for push-gate (#464)",
         gp, gi.replace("  generate-ids:\n    needs: push-gate\n", "  generate-ids:\n"), None,
         "generate-ids.yml job 'generate-ids' holds a secret, an environment or a push"),
        ("a push-gate step runs a repository script (#464)",
         gp.replace("            core.info('the push gate')\n",
                    "            core.info('the push gate')\n      - run: python scripts/push-gate.py\n"), gi, None,
         "with an inline script. The gate may not check out or run code"),
        ("the push gate checks out the repository (#464)",
         gp.replace("    steps:\n      - uses: actions/github-script@v9\n",
                    "    steps:\n      - uses: actions/checkout@v7\n      - uses: actions/github-script@v9\n"), gi, None,
         "with an inline script. The gate may not check out or run code"),
        ("the push gate has needs (#464)",
         gp.replace("  push-gate:\n    runs-on", "  push-gate:\n    needs: validate-markdown\n    runs-on"), gi, None,
         "it must be the first job"),
        ("the push gate has an if (#464)",
         gp.replace("  push-gate:\n    runs-on", "  push-gate:\n    if: ${{ always() }}\n    runs-on"), gi, None,
         "has an `if:`"),
        ("the push gate cannot write issues (#464)",
         gp.replace("      issues: write\n", ""), gi, None, "`issues: write`"),
        ("the push gate can write the repository (#464)",
         gp.replace("      contents: read\n      pull-requests: read\n      issues: write\n",
                    "      contents: write\n      pull-requests: read\n      issues: write\n"), gi, None,
         "no more than `contents: read`"),
        ("the two push-gate scripts differ (#464)",
         gp, gi.replace("core.info('the push gate')", "core.info('another gate')"), None,
         "scripts in documentation-pipeline.yml and generate-ids.yml differ"),
        ("sync reaches push-gate only through another job, under a status-function if (#464)",
         gp.replace("[push-gate, validate-markdown, repo-screenshots]", "[validate-markdown, repo-screenshots]"),
         gi, None, "has a status-function `if:`, so it must name 'push-gate'"),
        ("generate-ids.yml has no push-gate job (#464)",
         gp, re.sub(r"(?s)  push-gate:\n.*?(?=  generate-ids:\n)", "", gi), None,
         "generate-ids.yml has no 'push-gate' job"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = wiring(gp, gi, tmp, "good")
        case("GREEN correct workflows pass, including a bare pull in a step that commits "
             "nothing and an echo that mentions git pull", rc == 0,
             f"rc={rc}" + ("" if rc == 0 else f" {out[-600:]}"))
        for i, (name, p, g) in enumerate(red):
            rc, out = wiring(p, g, tmp, f"red{i}")
            case(f"RED {name}", rc == 1 and "WIRING FAIL" in out, f"rc={rc}")
        for i, (name, p, g, extra, needle) in enumerate(red_464):
            rc, out = wiring(p, g, tmp, f"red464-{i}", extra)
            ok = rc == 1 and "WIRING FAIL" in out and needle in out
            case(f"RED {name}", ok, f"rc={rc}" + ("" if ok else f" {out[-600:]}"))
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
