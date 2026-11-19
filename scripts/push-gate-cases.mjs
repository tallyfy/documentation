#!/usr/bin/env node
// push-gate-cases.mjs: what the push gate decides, both ways, with no network (tallyfy/documentation#548).
//
// The push gate is an inline script in generate-ids.yml and documentation-pipeline.yml, and it may run no
// code from the repository. So this test takes the script out of each workflow file, checks that a YAML
// parser reads the same text (as scripts/pipeline-guard.py does), runs it against a fake GitHub API in each
// file's mode, and checks what it decides: a stop (core.setFailed) or a pass, and why it stopped. The gate
// must never wait, so a gate script that names a timer is wrong. Then it plants faults in the script one at a time, and each must turn
// at least one case red, so a test that cannot fail is caught.
//
// It also checks the job the gate trusts, pr-validate.yml's lb-pr-guard: the job name the gate looks for
// is taken from that file, not written here, so the two cannot drift apart; only checkout and setup-python
// run before the step that decides, so no code from the pull request runs first; and that step, run by
// bash in a scratch repository whose base has no guard, refuses a pull request by launchbrightly[bot]
// (by login or by user id) and still uses the pull request's own copy for anyone else.
//
//   node scripts/push-gate-cases.mjs [--repo PATH]
//
// Needs python3 with PyYAML, git and bash. Exit 0: every case and every planted fault went the right way.
// Exit 1: one did not. Exit 2: could not run (a workflow, its gate script or the guard job is missing, the
// YAML parser reads a different script, the two scripts differ, a planted fault's text is not in the script
// exactly once, a planted fault does not compile, or the scratch repository could not be built).

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const argv = process.argv.slice(2);
const repoRoot = argv[0] === '--repo' && argv[1] ? argv[1] : '.';
const WORKFLOWS = {
  pipeline: '.github/workflows/documentation-pipeline.yml',
  push: '.github/workflows/generate-ids.yml',
};

function cannotRun(message) {
  console.error(`COULD NOT RUN: ${message}`);
  process.exit(2);
}

// The push-gate job's inline `script: |` block, without its indent.
function gateScript(path) {
  let text;
  try {
    text = readFileSync(path, 'utf8');
  } catch (err) {
    return null;
  }
  const lines = text.split('\n');
  const job = lines.findIndex((l) => /^ {2}push-gate:\s*$/.test(l));
  if (job < 0) return null;
  let i = job + 1;
  while (i < lines.length && lines[i].trim() !== 'script: |') {
    if (/^ {2}[A-Za-z0-9_-]+:\s*$/.test(lines[i])) return null;
    i += 1;
  }
  const body = lines.slice(i + 1);
  const first = body.find((l) => l.trim());
  if (!first) return null;
  const indent = first.length - first.trimStart().length;
  const out = [];
  for (const l of body) {
    if (l.trim() && l.length - l.trimStart().length < indent) break;
    out.push(l.slice(indent));
  }
  while (out.length && !out[out.length - 1].trim()) out.pop();
  return out.join('\n');
}

// The same script as a YAML parser reads it, the way pipeline-guard.py's gate_script() does.
function yamlGateScript(path) {
  const code = [
    'import sys, yaml',
    'doc = yaml.safe_load(open(sys.argv[1]))',
    'steps = ((doc.get("jobs") or {}).get("push-gate") or {}).get("steps") or []',
    's = [str((x.get("with") or {}).get("script", "")) for x in steps if str(x.get("uses", "")).startswith("actions/github-script@")]',
    'sys.stdout.write(s[0] if len(s) == 1 else "")',
  ].join('\n');
  const r = spawnSync('python3', ['-c', code, path], { encoding: 'utf8' });
  if (r.error || r.status !== 0) cannotRun(`python3 with PyYAML could not read ${path}: ${r.error ? r.error.message : r.stderr.trim()}`);
  return r.stdout.replace(/\s+$/, '');
}

const scripts = {};
for (const [mode, path] of Object.entries(WORKFLOWS)) {
  const full = join(repoRoot, path);
  const s = gateScript(full);
  if (!s) cannotRun(`no push-gate script found in ${path}`);
  if (yamlGateScript(full) !== s.replace(/\s+$/, '')) cannotRun(`the YAML parser reads a different push-gate script in ${path} than this test does`);
  scripts[mode] = s;
}
if (scripts.pipeline !== scripts.push) cannotRun('the push-gate scripts in the two workflows differ');

// pr-validate.yml's lb-pr-guard job, as a YAML parser reads it: its name, whether it may fail without
// failing, and its steps with their `if:` and continue-on-error.
function guardJob() {
  const path = join(repoRoot, '.github/workflows/pr-validate.yml');
  const code = [
    'import json, sys, yaml',
    'doc = yaml.safe_load(open(sys.argv[1]))',
    'job = (doc.get("jobs") or {}).get("lb-pr-guard") or {}',
    'steps = [{"name": str(s.get("name") or ""), "uses": str(s.get("uses") or ""), "run": str(s.get("run") or ""), "with": s.get("with") or {},',
    '          "if": s.get("if"), "continueOnError": s.get("continue-on-error"), "env": s.get("env") or {}}',
    '         for s in (job.get("steps") or []) if isinstance(s, dict)]',
    'print(json.dumps({"name": job.get("name"), "continueOnError": job.get("continue-on-error"), "env": job.get("env") or {},',
    '                  "workflowEnv": doc.get("env") or {}, "steps": steps}))',
  ].join('\n');
  const r = spawnSync('python3', ['-c', code, path], { encoding: 'utf8' });
  if (r.error || r.status !== 0) cannotRun(`python3 with PyYAML could not read ${path}: ${r.error ? r.error.message : r.stderr.trim()}`);
  const job = JSON.parse(r.stdout);
  if (typeof job.name !== 'string' || !job.steps.length) cannotRun('pr-validate.yml has no lb-pr-guard job with a name and steps');
  return job;
}

const GUARD_JOB = guardJob();
const NUMBER_EXPR = '${{ github.event.pull_request.number }}';
const BASE_EXPR = '${{ github.base_ref }}';
for (const expr of [NUMBER_EXPR, BASE_EXPR]) {
  if (GUARD_JOB.name.split(expr).length !== 2) cannotRun(`the lb-pr-guard job name must carry ${expr} once: ${GUARD_JOB.name}`);
}
// The name GitHub gives the guard job for pull request #number into base, as pr-validate.yml writes it.
// A planted fault below swaps in another template for one run.
let guardNameTemplate = GUARD_JOB.name;
const jobName = (number, base = 'staging') => guardNameTemplate.replace(NUMBER_EXPR, String(number)).replace(BASE_EXPR, base);
const CHECK_MARK = '"$guard/scripts/lb-pr-guard.py" --repo';

class ScratchFailure extends Error {}

// A scratch git repository at dir/name whose HEAD is a test merge, as GitHub makes one: the base commit
// holds baseFiles, the pull request commit holds prFiles, and HEAD^1 and HEAD^2 are those two.
function scratchMerge(dir, name, baseFiles, prFiles) {
  const repo = join(dir, name);
  const git = (...args) => {
    const r = spawnSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@example.com', '-c', 'commit.gpgsign=false',
      '-c', 'core.hooksPath=/dev/null', ...args], { cwd: repo, encoding: 'utf8' });
    if (r.error || r.status !== 0) throw new ScratchFailure(`git ${args[0]} in the scratch repository failed: ${r.error ? r.error.message : r.stderr.trim()}`);
  };
  const put = (files) => {
    for (const [path, text] of Object.entries(files)) {
      mkdirSync(join(repo, path, '..'), { recursive: true });
      writeFileSync(join(repo, path), text);
    }
  };
  mkdirSync(repo, { recursive: true });
  git('init', '-q', '-b', 'base');
  put({ 'README.md': 'base\n', ...baseFiles });
  git('add', '-A');
  git('commit', '-q', '-m', 'base');
  git('checkout', '-q', '-b', 'pr');
  put(prFiles);
  git('add', '-A');
  git('commit', '-q', '-m', 'pull request');
  git('checkout', '-q', 'base');
  git('merge', '-q', '--no-ff', '--no-edit', 'pr');
  return repo;
}

// A stand-in guard that says which copy of the guard and of its rules ran.
const standIn = (who) => ({
  'scripts/lb-pr-guard.py': [
    'import os, sys',
    'sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset_management"))',
    'import repo_screenshot_rules as rules',
    `print("GUARD=${who} RULES=" + rules.WHO)`,
    '',
  ].join('\n'),
  'scripts/asset_management/repo_screenshot_rules.py': `WHO = "${who}"\n`,
});

// What is wrong with the job the gate trusts, as a list of problems. It runs the deciding step with bash
// in scratch repositories: with no guard on the base, and with the guard on the base and another copy in
// the pull request.
function guardJobProblems(job) {
  const problems = [];
  if (job.continueOnError) problems.push('the lb-pr-guard job has continue-on-error, so it can pass while its check fails');
  const check = job.steps.findIndex((s) => s.run.includes(CHECK_MARK));
  if (check < 0) return [...problems, `no lb-pr-guard step runs ${CHECK_MARK}`];
  for (const s of job.steps.slice(0, check)) {
    if (/^actions\/checkout@/.test(s.uses) && (s.with.ref !== undefined || s.with.repository !== undefined)) {
      problems.push(`the checkout before the step that decides sets ${Object.keys(s.with).filter((k) => k === 'ref' || k === 'repository').join(' and ')}, so HEAD may not be GitHub's test merge and HEAD^1 may not be the base`);
    }
    if (s.run || !/^actions\/(checkout|setup-python)@/.test(s.uses)) {
      problems.push(`"${s.name || s.uses || 'a step'}" runs before the step that decides, and only checkout and setup-python may`);
    }
  }
  const decide = job.steps[check];
  if (decide.if !== null && decide.if !== undefined) problems.push(`the step that decides has an if: (${decide.if}), so it can be skipped and the job pass`);
  if (decide.continueOnError) problems.push('the step that decides has continue-on-error, so the job can pass while it fails');
  // Environment can make bash or python load files from the pull request inside the step that decides
  // (BASH_ENV, PYTHONPATH and the like), so only the step's own two author variables may be set.
  if (Object.keys(job.workflowEnv || {}).length) problems.push(`pr-validate.yml sets env for every job (${Object.keys(job.workflowEnv).join(', ')}), which reaches the step that decides`);
  if (Object.keys(job.env || {}).length) problems.push(`the lb-pr-guard job sets env (${Object.keys(job.env).join(', ')}), which reaches the step that decides`);
  const extra = Object.keys(decide.env || {}).filter((k) => !['PR_AUTHOR_LOGIN', 'PR_AUTHOR_ID'].includes(k));
  if (extra.length) problems.push(`the step that decides sets env beyond its author variables (${extra.join(', ')})`);
  const dir = mkdtempSync(join(tmpdir(), 'push-gate-guard-'));
  let failure = null;
  try {
    mkdirSync(join(dir, 'bin'));
    writeFileSync(join(dir, 'bin', 'python'), '#!/bin/sh\nexec python3 "$@"\n');
    chmodSync(join(dir, 'bin', 'python'), 0o755);
    const step = (repo, login, id) => {
      mkdirSync(join(dir, 'tmp'), { recursive: true });
      const r = spawnSync('bash', ['--noprofile', '--norc', '-eo', 'pipefail', '-c', decide.run], {
        cwd: repo,
        encoding: 'utf8',
        env: { ...process.env, PATH: `${join(dir, 'bin')}:${process.env.PATH}`, RUNNER_TEMP: join(dir, 'tmp'), PR_AUTHOR_LOGIN: login, PR_AUTHOR_ID: id },
      });
      rmSync(join(dir, 'tmp'), { recursive: true, force: true });
      if (r.error) throw new ScratchFailure(`bash could not run the check step: ${r.error.message}`);
      return { rc: r.status, out: String(r.stdout) };
    };
    const THEM = [
      ['launchbrightly[bot]', 'launchbrightly[bot]', '270903805'],
      ['their user id alone', 'someone-else', '270903805'],
      ['their login alone, in another case', 'LaunchBrightly[bot]', '5'],
    ];

    // No guard on the base: a person's pull request is judged by its own copy, theirs is refused.
    const bare = scratchMerge(dir, 'no-guard-on-base', {}, standIn('PR'));
    const person = step(bare, 'amitkoth', '1000');
    if (person.rc !== 0 || !person.out.includes('GUARD=PR RULES=PR')) {
      problems.push(`with no guard on the base, the check step did not use a person's own copy (rc ${person.rc})`);
    }
    for (const [who, login, id] of THEM) {
      const got = step(bare, login, id);
      if (got.rc === 0 || got.out.includes('GUARD=')) problems.push(`with no guard on the base, the check step ran the pull request's own copy for ${who} (rc ${got.rc})`);
    }

    // The guard on the base, and the pull request bringing another copy: the base's copy judges everyone.
    const guarded = scratchMerge(dir, 'guard-on-base', standIn('BASE'), standIn('PR'));
    for (const [who, login, id] of [['a person', 'amitkoth', '1000'], ...THEM]) {
      const got = step(guarded, login, id);
      if (got.rc !== 0 || !got.out.includes('GUARD=BASE RULES=BASE')) {
        problems.push(`with the guard on the base, the check step did not judge ${who}'s pull request with the base's guard and rules (rc ${got.rc}: ${got.out.trim().split('\n').pop() || 'no output'})`);
      }
    }
  } catch (err) {
    if (!(err instanceof ScratchFailure)) throw err;
    failure = err.message;
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  if (failure) cannotRun(failure);
  return problems;
}

const sha = (label) => createHash('sha1').update(label).digest('hex');
const LB = { login: 'launchbrightly[bot]', id: 270903805, type: 'Bot' };
const LOOKALIKE = { login: 'launchbrightly[bot]', id: 5, type: 'Bot' };
const PERSON = { login: 'amitkoth', id: 1000, type: 'User' };
const OTHER_APP = { login: 'some-other-app[bot]', id: 99, type: 'Bot' };
const ACTIONS = { login: 'github-actions[bot]', id: 41898282, type: 'Bot' };
const WEB_FLOW = { login: 'web-flow', id: 19864447, type: 'User' };

const gitIdentity = (u) => ({ name: u.login, email: `${u.id}+${u.login}@users.noreply.github.com` });
// A commit whose git identity names no app and links to no account; GitHub as committer when byGitHub.
const plainCommit = (label, byGitHub) => ({ sha: sha(label), author: null, committer: byGitHub ? WEB_FLOW : null,
  commit: { author: { name: 'Screenshot updater', email: 'updater@example.com' },
    committer: byGitHub ? { name: 'GitHub', email: 'noreply@github.com' } : { name: 'Screenshot updater', email: 'updater@example.com' } } });
const commitBy = (label, author, committer = author) => ({
  sha: sha(label),
  author,
  committer,
  commit: {
    author: gitIdentity(author),
    committer: committer === WEB_FLOW ? { name: 'GitHub', email: 'noreply@github.com' } : gitIdentity(committer),
  },
});

// pr-validate.yml runs on a pull request's head, each with its jobs, for each guard state. n is the pull
// request number. A run may carry totalCount (its jobs list comes back short) and the list itself may carry
// totalCount (the runs list comes back short).
const job = (id, name, status, conclusion) => ({ id, name, status, conclusion });
const GUARD = {
  success: (n) => [{ id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] }],
  failure: (n) => [{ id: 1, jobs: [job(11, jobName(n), 'completed', 'failure')] }],
  pending: (n) => [{ id: 1, jobs: [job(11, jobName(n), 'in_progress', null)] }],
  missing: () => [],
  'no-job': () => [{ id: 1, jobs: [job(11, 'validate', 'completed', 'success')] }],
  'other-base': (n) => [{ id: 1, jobs: [job(11, jobName(n, 'other-branch'), 'completed', 'success')] }],
  'other-pr': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'failure')] },
    { id: 2, jobs: [job(21, jobName(n + 500), 'completed', 'success')] },
  ],
  'newest-has-no-job': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] },
    { id: 2, jobs: [] },
  ],
  'fork-run-newer': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] },
    { id: 2, repo: 'someone/documentation', jobs: [job(21, jobName(n), 'completed', 'failure')] },
  ],
  'many-runs': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] },
    ...Array.from({ length: 149 }, (_, i) => ({ id: i + 2, jobs: [] })),
  ],
  'newer-other-pr-failed': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] },
    { id: 2, jobs: [job(21, jobName(n + 500, 'main'), 'completed', 'failure')] },
  ],
  'cancelled-then-success': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'cancelled')] },
    { id: 2, jobs: [job(21, jobName(n), 'completed', 'success')] },
  ],
  'success-then-cancelled': (n) => [
    { id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] },
    { id: 2, jobs: [job(21, jobName(n), 'completed', 'cancelled')] },
  ],
  duplicate: (n) => [{ id: 1, jobs: [job(11, jobName(n), 'completed', 'failure'), job(12, jobName(n), 'completed', 'success')] }],
  'runs-short': (n) => Object.assign([{ id: 1, jobs: [job(11, jobName(n), 'completed', 'success')] }], { totalCount: 101 }),
  'jobs-short': (n) => [{ id: 1, jobsTotal: 30, jobs: [job(11, jobName(n), 'completed', 'success')] }],
};

const pullRequest = (number, mergeSha, author, base, head) => ({
  number,
  state: 'closed',
  merged_at: '2026-11-17T12:00:00Z',
  merge_commit_sha: mergeSha,
  user: author,
  base: { ref: base },
  head: { sha: head, repo: { full_name: 'tallyfy/documentation' } },
});

// A person closed the gate's issue as completed. Its title is the gate's own, or the one it used before #548.
const acceptIssue = (world, shaToAccept, oldTitle) => {
  const title = oldTitle ? `Docs pipeline stopped: commits reached ${world.branch} without a pull request`
    : `Docs pipeline stopped: the push gate did not let commits on ${world.branch} through`;
  world.closedIssues = [{ number: 7, title }];
  world.issues[7] = { state: 'closed', state_reason: 'completed', closed_by: PERSON, body: `- \`${shaToAccept}\`: accepted` };
};

// One change since the last good run. merge: a squash merge of a pull request, so its commit carries the
// pull request author's name and GitHub as committer; push: a commit pushed straight to the branch.
function scenario({ branch = 'staging', changes = [] }) {
  const anchor = sha(`anchor-${branch}`);
  const world = {
    branch, anchor, head: anchor, commits: [], activity: [], pulls: {}, guard: {}, guardPr: {}, jobs: {},
    closedIssues: [], issues: {},
  };
  let n = 100;
  for (const ch of changes) {
    n += 1;
    const label = `${ch.kind}-${n}`;
    const author = ch.commitAuthor || (ch.kind === 'merge' ? ch.prAuthor : ch.by);
    const c = ch.kind === 'merge' ? commitBy(label, author, WEB_FLOW) : commitBy(label, author);
    world.commits.push(c);
    if (ch.kind === 'merge' && !ch.noPullRequest) {
      const head = sha(`${label}-head`);
      world.pulls[c.sha] = [pullRequest(n, c.sha, ch.prAuthor, ch.base || branch, head)];
      world.guard[head] = ch.guard || 'success';
      world.guardPr[head] = n;
    }
    world.activity.unshift({
      activity_type: ch.kind === 'merge' ? 'pr_merge' : 'push',
      actor: ch.actorless ? null : ch.by,
      after: c.sha,
      timestamp: `2026-11-17T12:${String(n - 100).padStart(2, '0')}:00Z`,
    });
  }
  // The starting point is a person's merge of a person's pull request.
  world.activity.push({ activity_type: 'pr_merge', actor: PERSON, after: anchor, timestamp: '2026-11-17T11:00:00Z' });
  world.pulls[anchor] = [pullRequest(100, anchor, PERSON, branch, sha(`anchor-head-${branch}`))];
  if (world.commits.length) world.head = world.commits[world.commits.length - 1].sha;
  return world;
}

function fakeGitHub(world, broken) {
  return {
    async request(route, params = {}) {
      if (route.startsWith('POST ') || route.startsWith('PATCH ')) world.writes = (world.writes || 0) + 1;
      if (broken.includes(route)) throw Object.assign(new Error('fake outage'), { status: 500 });
      if (world.flaky && world.flaky[route]) {
        world.flaky[route] -= 1;
        throw Object.assign(new Error('fake brief outage'), { status: 502 });
      }
      switch (route) {
        case 'GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs': {
          if (params.workflow_id === 'generate-ids.yml') {
            return { data: { total_count: 1, workflow_runs: [{ id: 1, head_branch: world.branch, conclusion: 'success', head_sha: world.anchor }] } };
          }
          if (params.workflow_id !== 'pr-validate.yml' || params.event !== 'pull_request') {
            throw new Error(`the fake has no runs for ${params.workflow_id} ${params.event}`);
          }
          const state = world.guard[params.head_sha] || 'missing';
          if (state === 'broken') throw Object.assign(new Error('fake outage'), { status: 500 });
          let runs = GUARD[state](world.guardPr[params.head_sha]);
          if (world.guardSecond && params.head_sha === world.head) {
            // A second pull request of theirs on the same head: its runs, with their own ids, come after.
            const extra = GUARD[world.guardSecond.state](world.guardSecond.number)
              .map((r) => ({ ...r, id: r.id + 1000, jobs: r.jobs.map((j) => ({ ...j, id: j.id + 1000 })) }));
            runs = [...runs, ...extra];
          }
          for (const r of runs) world.jobs[r.id] = r;
          const listed = runs.map((r) => ({ id: r.id, event: 'pull_request', head_sha: params.head_sha, path: '.github/workflows/pr-validate.yml',
            head_repository: { full_name: r.repo || 'tallyfy/documentation' } }));
          const per = params.per_page || 30;
          const page = params.page || 1;
          return { data: { total_count: runs.totalCount || listed.length, workflow_runs: listed.slice((page - 1) * per, page * per) } };
        }
        case 'GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs': {
          const r = world.jobs[params.run_id] || { jobs: [] };
          return { data: { total_count: r.jobsTotal || r.jobs.length, jobs: r.jobs } };
        }
        case 'GET /repos/{owner}/{repo}/branches/{branch}':
          return { data: { commit: { sha: world.head } } };
        case 'GET /repos/{owner}/{repo}/compare/{basehead}':
          return { data: { status: world.commits.length ? 'ahead' : 'identical', total_commits: world.commits.length, commits: world.commits } };
        case 'GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls':
          world.commitReads = (world.commitReads || 0) + 1;
          // GitHub may link a commit to its pull request a little after the merge.
          return { data: (world.linkLag && world.linkLag.includes(params.commit_sha)) ? [] : (world.pulls[params.commit_sha] || []) };
        case 'GET /repos/{owner}/{repo}/pulls': {
          if (!['closed', 'open'].includes(params.state) || params.base !== world.branch) throw new Error(`the fake has no pull request list for ${params.state} ${params.base}`);
          // extraPulls come first, so a pull request of the case's own can sit past the first page.
          const all = new Map();
          for (const pr of world.extraPulls || []) all.set(pr.number, pr);
          for (const prs of Object.values(world.pulls)) for (const pr of prs) all.set(pr.number, pr);
          const listed = [...all.values()].filter((pr) => (pr.state || 'closed') === params.state);
          // notInClosedList: more than 100 other pull requests were closed since, so the case's own are not listed.
          if (params.state === 'closed') return { data: world.notInClosedList ? [] : listed };
          const per = params.per_page || 30;
          const page = params.page || 1;
          return { data: listed.slice((page - 1) * per, page * per) };
        }
        case 'GET /repos/{owner}/{repo}/activity':
          return { data: world.activity, headers: {} };
        case 'GET /repos/{owner}/{repo}/issues':
          return { data: params.state === 'closed' ? world.closedIssues : [] };
        case 'GET /repos/{owner}/{repo}/issues/{issue_number}':
          return { data: world.issues[params.issue_number] || {} };
        case 'POST /repos/{owner}/{repo}/issues':
          return { data: { number: 999 } };
        default:
          throw new Error(`the fake GitHub has no answer for ${route}`);
      }
    },
  };
}

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor;
const PARAMS = ['github', 'context', 'core', 'process'];

async function decide(script, mode, world, broken = []) {
  const failed = [];
  const errors = [];
  const core = { info() {}, warning() {}, error: (m) => errors.push(String(m)), setFailed: (m) => failed.push(String(m)) };
  const context = { repo: { owner: 'tallyfy', repo: 'documentation' }, serverUrl: 'https://github.com', runId: 2 };
  const env = mode === 'pipeline'
    ? { GATE_MODE: 'pipeline', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_TRIGGER_RUN_ID: '1', GATE_TRIGGER_CONCLUSION: 'success', GATE_TRIGGER_HEAD: world.anchor }
    : { GATE_MODE: 'push', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_HEAD: world.head };
  const gate = new AsyncFunction(...PARAMS, script);
  await gate(fakeGitHub(world, broken), context, core, { env });
  return { outcome: failed.length ? 'stop' : 'pass', text: [...failed, ...errors].join('\n'), writes: world.writes || 0, commitReads: world.commitReads || 0 };
}

const lbMerge = (extra = {}) => ({ kind: 'merge', by: LB, prAuthor: LB, ...extra });

// [name, expected outcome, text a stop must give, world]. Every case runs in both modes.
const CASES = [
  ['their app merges its own pull request into staging, guard passed', 'pass', null, { changes: [lbMerge()] }],
  ['their app merges its own pull request into staging, guard failed', 'stop', 'ended failure', { changes: [lbMerge({ guard: 'failure' })] }],
  ['their app merges before the guard has finished', 'stop', 'had not finished', { changes: [lbMerge({ guard: 'pending' })] }],
  ['their app merges and no guard run exists', 'stop', 'never ran', { changes: [lbMerge({ guard: 'missing' })] }],
  ['their app merges and no run has their guard job', 'stop', 'never ran', { changes: [lbMerge({ guard: 'no-job' })] }],
  ['their pull request passed the guard only against another base', 'stop', 'never ran', { changes: [lbMerge({ guard: 'other-base' })] }],
  ['their guard failed, and only another pull request on the same commit passed, later', 'stop', 'ended failure',
    { changes: [lbMerge({ guard: 'other-pr' })] }],
  ['their guard passed, and a newer run on the same commit without the job (awaiting approval) does not hide it', 'pass', null,
    { changes: [lbMerge({ guard: 'newest-has-no-job' })] }],
  ['their guard passed, and another pull request\'s newer failing run on the same commit does not stand in for it', 'pass', null,
    { changes: [lbMerge({ guard: 'newer-other-pr-failed' })] }],
  ['an older guard run was cancelled and the newest passed', 'pass', null, { changes: [lbMerge({ guard: 'cancelled-then-success' })] }],
  ['the newest guard run was cancelled after an older pass', 'stop', 'ended cancelled', { changes: [lbMerge({ guard: 'success-then-cancelled' })] }],
  ['the run has two guard jobs of that name', 'stop', 'jobs named', { changes: [lbMerge({ guard: 'duplicate' })] }],
  ['the list of guard runs comes back short', 'stop', 'read 1 of 101', { changes: [lbMerge({ guard: 'runs-short' })] }],
  ['the list of guard jobs comes back short', 'stop', 'read 1 of 30', { changes: [lbMerge({ guard: 'jobs-short' })] }],
  ['their app merges its own pull request into main', 'stop', 'may merge only into staging', { branch: 'main', changes: [lbMerge()] }],
  ['their app\'s merge shows up on main as the merge of its staging pull request', 'stop', 'may merge only into staging',
    { branch: 'main', changes: [lbMerge({ base: 'staging' })] }],
  ['their app merges a pull request a person opened', 'stop', 'opened by amitkoth', { changes: [lbMerge({ prAuthor: PERSON })] }],
  ['their pull request into another branch lands on staging', 'stop', 'merged into other-branch', { changes: [lbMerge({ base: 'other-branch' })] }],
  ['their app merges a commit no pull request has', 'stop', 'no merged pull request',
    { changes: [lbMerge({ prAuthor: PERSON, commitAuthor: PERSON, noPullRequest: true })] }],
  ['their app merges with a merge commit, not a squash', 'stop', 'no merged pull request has it as its merge commit', { mergeCommit: true }],
  ['their app pushes straight to staging', 'stop', 'push to staging by launchbrightly[bot]', { changes: [{ kind: 'push', by: LB }] }],
  ['their app pushes, as a push, the merge commit of its own passing pull request', 'stop', 'push to staging by launchbrightly[bot]',
    { changes: [lbMerge()], pushInstead: true }],
  ['an app with their login but another id merges', 'stop', 'pr_merge to staging by launchbrightly[bot]',
    { changes: [{ kind: 'merge', by: LOOKALIKE, prAuthor: LOOKALIKE }] }],
  ['another app merges its own pull request into staging', 'stop', 'by some-other-app[bot]', { changes: [{ kind: 'merge', by: OTHER_APP, prAuthor: OTHER_APP }] }],
  ['another app merges their pull request, guard passed', 'stop', 'by some-other-app[bot]', { changes: [{ kind: 'merge', by: OTHER_APP, prAuthor: LB }] }],
  ['a person merges a person\'s pull request', 'pass', null, { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON }] }],
  ['a person merges their pull request, guard passed', 'pass', null, { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB }] }],
  ['a person merges their pull request, guard failed', 'stop', 'ended failure', { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: 'failure' }] }],
  ['a person merges a person\'s pull request that carries one of their commits (as before this change)', 'pass', null,
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, commitAuthor: LB }] }],
  ['on main, a person merges their pull request straight in with a failed guard (as before this change)', 'pass', null,
    { branch: 'main', changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: 'failure' }] }],
  ['on main, a person merges a promotion that carries their commit', 'pass', null, {
    branch: 'main',
    changes: [
      { kind: 'merge', by: PERSON, prAuthor: LB, base: 'staging' },
      { kind: 'merge', by: PERSON, prAuthor: PERSON },
    ],
    promotion: true,
  }],
  ['main merged back into staging brings their commit from a pull request into main', 'stop', 'merged into main',
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, base: 'main' }] }],
  ['their merge that made the starting point is judged again, and its guard now reads failed', 'stop', 'ended failure',
    { anchorIsTheirMerge: 'failure' }],
  ['their merge that made the starting point is judged again, and its guard passed', 'pass', null, { anchorIsTheirMerge: 'success' }],
  ['their app\'s merge of a person\'s pull request, listed only after the run that made it the starting point', 'stop',
    'opened by amitkoth', { anchorIsTheirMergeOfPersonPr: true }],
  ['an entry with no readable actor that made the starting point is judged again', 'stop', 'could not read', { anchorActorless: true }],
  ['an entry with no readable actor at the starting point that a person accepted', 'pass', null, { anchorActorless: true, acceptAnchor: true }],
  ['a person merges their pull request with a merge commit, its commits naming no app, guard failed', 'stop', 'ended failure',
    { personMerge: 'merge-commit', guard: 'failure' }],
  ['a person merges their pull request with a merge commit, its commits naming no app, guard passed', 'pass', null,
    { personMerge: 'merge-commit', guard: 'success' }],
  ['a person rebases their pull request in, its commits naming no app, guard failed', 'stop', 'ended failure',
    { personMerge: 'rebase', guard: 'failure' }],
  ['a person squashes their pull request in before the activity log lists it, guard failed', 'stop', 'ended failure',
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: 'failure' }], activityLate: true }],
  ['their single commit naming another app, rebased in by a person before the activity log lists it, guard failed', 'stop',
    'ended failure', { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, commitAuthor: OTHER_APP, guard: 'failure' }], activityLate: true }],
  ['a person merges their pull request with a merge commit before the activity log lists it, guard failed', 'stop', 'ended failure',
    { personMerge: 'merge-commit', guard: 'failure', activityLate: true }],
  ['a person\'s merge of their pull request at the starting point, guard failed', 'stop', 'ended failure', { anchorPersonMergeOfTheirPr: true }],
  ['a person pushes the head of their pull request straight to staging, commits naming their app, guard failed', 'stop',
    'ended failure', { personPushHead: { names: 'app', guard: 'failure' } }],
  ['a person pushes the head of their pull request straight to staging, commits naming their app, guard passed', 'pass', null,
    { personPushHead: { names: 'app', guard: 'success' } }],
  ['a person pushes the head of their pull request straight to staging, its commit naming another app, guard failed', 'stop',
    'ended failure', { personPushHead: { names: 'other', guard: 'failure' } }],
  ['a person pushes the head of their pull request straight to staging, and another pull request on that head is listed first, guard failed',
    'stop', 'ended failure', { personPushHead: { names: 'app', guard: 'failure', shared: true } }],
  ['a person pushes the head of their pull request straight to staging, and another pull request on that head is listed first, guard passed',
    'pass', null, { personPushHead: { names: 'app', guard: 'success', shared: true } }],
  ['a person pushes a head that two pull requests of theirs share, one guard passed and one not finished', 'stop',
    'had not finished', { personPushHead: { names: 'app', guard: 'success', sharedTheirs: 'pending' } }],
  ['a person pushes the head of their pull request straight to staging before GitHub marks it merged', 'stop',
    'no merged pull request has it as its merge commit', { personPushHead: { names: 'app', guard: 'success', notMergedYet: true } }],
  ['a person pushes the head of their two-commit pull request straight to staging, commits naming their app: the first stops', 'stop',
    'no merged pull request has it as its merge commit', { personPushHead: { names: 'app', count: 2, guard: 'success' } }],
  ['a person pushes the head of their pull request straight to staging, commits naming no app, guard failed', 'stop',
    'ended failure', { personPushHead: { names: 'none', guard: 'failure' } }],
  ['a person pushes the head of their pull request straight to staging, commits naming no app, guard passed', 'pass', null,
    { personPushHead: { names: 'none', guard: 'success' } }],
  ['a person pushes the head of their two-commit pull request straight to staging, commits naming no app, guard failed', 'stop',
    'ended failure', { personPushHead: { names: 'none', count: 2, guard: 'failure' } }],
  ['a person pushes the head of their two-commit pull request straight to staging, commits naming no app, guard passed', 'pass', null,
    { personPushHead: { names: 'none', count: 2, guard: 'success' } }],
  ['a person pushes a merge commit made on their machine that lands their pull request, commits naming no app, guard failed', 'stop',
    'ended failure', { personPushHead: { names: 'none', count: 2, localMerge: true, guard: 'failure' } }],
  ['a person pushes a merge commit made on their machine that lands their pull request, commits naming no app, guard passed', 'pass',
    null, { personPushHead: { names: 'none', count: 2, localMerge: true, guard: 'success' } }],
  ['a person pushes the head of their pull request, commits naming no app, before GitHub marks it merged', 'stop',
    'has not marked it merged', { personPushHead: { names: 'none', guard: 'success', notMergedYet: true } }],
  ['the same push before GitHub marks it merged, with their pull request past the first 100 open', 'stop',
    'has not marked it merged', { personPushHead: { names: 'none', guard: 'success', notMergedYet: true }, manyOpen: true }],
  // Not among the 100 most recently closed: only the lookup of each commit by its pull request can find these.
  ['a person squashes their pull request in before the activity log lists it, not among the 100 most recently closed, guard failed',
    'stop', 'ended failure', { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: 'failure' }], activityLate: true, notInClosedList: true }],
  ['a person pushes the head of their pull request, commits naming their app, not among the 100 most recently closed, guard failed',
    'stop', 'ended failure', { personPushHead: { names: 'app', guard: 'failure' }, notInClosedList: true }],
  ['a person pushes the head of their pull request, commits naming their app, not among the 100 most recently closed, guard passed',
    'pass', null, { personPushHead: { names: 'app', guard: 'success' }, notInClosedList: true }],
  ['a person pushes the head of their pull request, its commit naming another app, not among the 100 most recently closed, guard failed',
    'stop', 'ended failure', { personPushHead: { names: 'other', guard: 'failure' }, notInClosedList: true }],
  ['a person pushes a head another pull request shares, listed first, not among the 100 most recently closed, guard failed',
    'stop', 'ended failure', { personPushHead: { names: 'app', guard: 'failure', shared: true }, notInClosedList: true }],
  ['their pull request merged before the starting point, guard failed, is not judged again', 'pass', null,
    { changes: [{ kind: 'push', by: PERSON }], theirsMergedBefore: 'failure' }],
  ['their pull request open into staging, its head not on the branch, guard failed', 'pass', null,
    { changes: [{ kind: 'push', by: PERSON }], theirsOpen: 'failure' }],
  ['people\'s and the pipeline\'s own pushes cost no read of their own', 'pass', null,
    { changes: [{ kind: 'push', by: PERSON }, { kind: 'push', by: ACTIONS }, { kind: 'push', by: PERSON }], maxCommitReads: 0 }],
  ['a person\'s merge whose pull request cannot be found', 'stop', 'cannot tell whose',
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, noPullRequest: true }] }],
  ['GitHub has not linked a person\'s merge to its pull request yet, and the closed pull requests list it', 'pass', null,
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON }], linkLag: true }],
  ['GitHub has not linked a person\'s merge of their pull request yet, guard failed', 'stop', 'ended failure',
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: 'failure' }], linkLag: true }],
  ['a fork\'s newer run on the same commit, with a job of that name, does not count', 'pass', null,
    { changes: [lbMerge({ guard: 'fork-run-newer' })] }],
  ['more than 100 runs on their head are read across pages', 'pass', null, { changes: [lbMerge({ guard: 'many-runs' })] }],
  ['a write that fails is not tried again', 'stop', 'could not decide',
    { changes: [lbMerge({ guard: 'failure' })], flaky: ['POST /repos/{owner}/{repo}/issues'] }],
  ['a read that fails once on GitHub\'s side is tried again', 'pass', null,
    { changes: [lbMerge()], flaky: ['GET /repos/{owner}/{repo}/pulls'] }],
  ['their merge with no passed guard that a person accepted on the gate\'s issue', 'pass', null,
    { changes: [lbMerge({ guard: 'pending' })], acceptFirst: true }],
  ['their merge with no passed guard that a person accepted on an issue with the title used before #548', 'pass', null,
    { changes: [lbMerge({ guard: 'pending' })], acceptFirst: true, oldTitle: true }],
  ['a closed issue with another title accepts nothing', 'stop', 'had not finished',
    { changes: [lbMerge({ guard: 'pending' })], acceptFirst: true, otherTitle: true }],
  ['github-actions pushes generated files', 'pass', null, { changes: [{ kind: 'push', by: ACTIONS }] }],
  ['nothing changed since the last good run', 'pass', null, { changes: [] }],
  ['a push or merge that names no commit is not judged', 'pass', null, { noCommitActivity: true }],
  ['who made a change cannot be read', 'stop', 'could not read', { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, actorless: true }] }],
  ['the pull requests closed into the branch cannot be read', 'stop', 'could not decide',
    { changes: [lbMerge()], broken: ['GET /repos/{owner}/{repo}/pulls'] }],
  ['the pull requests of a merge not among the recently closed cannot be read', 'stop', 'could not decide',
    { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, noPullRequest: true }], broken: ['GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls'] }],
  ['the guard runs cannot be read', 'stop', 'could not decide', { changes: [lbMerge({ guard: 'broken' })] }],
  ['the guard jobs cannot be read', 'stop', 'could not decide',
    { changes: [lbMerge()], broken: ['GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs'] }],
];

// Builds the world for a case, with the shapes the generic builder does not make.
function worldFor(spec) {
  const world = scenario(spec);
  if (spec.pushInstead) world.activity[0].activity_type = 'push';
  if (spec.promotion) {
    // On main only the person's promotion merge is activity; their earlier squash commit arrives inside it.
    world.activity.splice(1, 1);
  }
  if (spec.mergeCommit) {
    // Their pull request's own commit plus a true merge commit, both by their app.
    const own = commitBy('lb-own-commit', LB);
    const merge = commitBy('lb-merge-commit', LB);
    const head = sha('lb-merge-commit-head');
    const pr = pullRequest(201, merge.sha, LB, 'staging', head);
    world.commits.push(own, merge);
    world.pulls[own.sha] = [pr];
    world.pulls[merge.sha] = [pr];
    world.guard[head] = 'success';
    world.guardPr[head] = 201;
    world.activity.unshift({ activity_type: 'pr_merge', actor: LB, after: merge.sha, timestamp: '2026-11-17T12:30:00Z' });
    world.head = merge.sha;
  }
  if (spec.anchorIsTheirMerge || spec.anchorIsTheirMergeOfPersonPr) {
    // The last good run started from their app's merge, which every run judges again.
    const head = sha('anchor-merge-head');
    const prAuthor = spec.anchorIsTheirMergeOfPersonPr ? PERSON : LB;
    world.activity = [{ activity_type: 'pr_merge', actor: LB, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
    world.pulls[world.anchor] = [pullRequest(202, world.anchor, prAuthor, 'staging', head)];
    world.guard[head] = spec.anchorIsTheirMerge || 'success';
    world.guardPr[head] = 202;
  }
  if (spec.anchorActorless) {
    world.activity = [{ activity_type: 'push', actor: null, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
  }
  if (spec.acceptAnchor) acceptIssue(world, world.anchor);
  if (spec.personMerge) {
    // Their pull request's commits carry a git identity that names no app and links to no account, and a
    // person merges it with a merge commit, or rebases it in (the last rebased commit is the merge commit).
    // GitHub commits the merge, and rewrites the committer of rebased commits, as itself.
    const own = [plainCommit(`${spec.personMerge}-own-1`, true), plainCommit(`${spec.personMerge}-own-2`, true)];
    const last = spec.personMerge === 'rebase' ? own[1] : commitBy(`${spec.personMerge}-merge`, PERSON, WEB_FLOW);
    const head = sha(`${spec.personMerge}-head`);
    const pr = pullRequest(203, last.sha, LB, 'staging', head);
    world.commits.push(...own);
    if (last !== own[1]) world.commits.push(last);
    for (const c of world.commits) world.pulls[c.sha] = [pr];
    world.guard[head] = spec.guard;
    world.guardPr[head] = 203;
    world.activity.unshift({ activity_type: 'pr_merge', actor: PERSON, after: last.sha, timestamp: '2026-11-17T12:30:00Z' });
    world.head = last.sha;
  }
  if (spec.activityLate) world.activity = world.activity.filter((a) => a.after === world.anchor);
  if (spec.anchorPersonMergeOfTheirPr) {
    // The last good run started from a person's merge of their pull request, whose guard reads failed.
    const head = sha('anchor-person-merge-head');
    world.activity = [{ activity_type: 'pr_merge', actor: PERSON, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
    world.pulls[world.anchor] = [pullRequest(204, world.anchor, LB, 'staging', head)];
    world.guard[head] = 'failure';
    world.guardPr[head] = 204;
  }
  if (spec.personPushHead) {
    // A person merges their pull request from the command line by pushing its head straight to staging.
    // GitHub records the pushed commit as the pull request's merge commit, or with localMerge the merge
    // commit the person made on their machine (measured 2026-11-19, #560); notMergedYet is the moment
    // before it does, while the pull request is still open. shared adds another person's pull request on
    // the same head, listed first, which GitHub marks merged too.
    const { names = 'app', count = 1, notMergedYet = false, shared = false, sharedTheirs = null, localMerge = false } = spec.personPushHead;
    const make = (label) => (names === 'app' ? commitBy(label, LB) : names === 'other' ? commitBy(label, OTHER_APP) : plainCommit(label, false));
    const own = Array.from({ length: count }, (_, i) => make(`person-push-head-${names}-${i}`));
    const c = own[own.length - 1];
    const local = localMerge ? commitBy('person-local-merge', PERSON) : null;
    const landed = local || c;
    world.commits.push(...own);
    if (local) world.commits.push(local);
    const pr = pullRequest(205, landed.sha, LB, 'staging', c.sha);
    if (notMergedYet) Object.assign(pr, { state: 'open', merged_at: null, merge_commit_sha: sha('test-merge-205') });
    const prs = shared ? [pullRequest(206, c.sha, PERSON, 'staging', c.sha), pr] : [pr];
    if (sharedTheirs) {
      // Their second pull request on the same head; its guard runs carry its own number, under its own head key.
      prs.push(pullRequest(207, c.sha, LB, 'staging', c.sha));
      world.guardSecond = { number: 207, state: sharedTheirs };
    }
    for (const o of [...own, ...(local ? [local] : [])]) world.pulls[o.sha] = prs;
    world.guard[c.sha] = spec.personPushHead.guard;
    world.guardPr[c.sha] = 205;
    world.activity.unshift({ activity_type: 'push', actor: PERSON, after: landed.sha, timestamp: '2026-11-18T12:30:00Z' });
    world.head = landed.sha;
  }
  if (spec.manyOpen) {
    // 150 people's pull requests open into staging, listed before theirs, so theirs is on the second page.
    world.extraPulls = Array.from({ length: 150 }, (_, i) => ({
      ...pullRequest(400 + i, sha(`open-test-merge-${i}`), PERSON, 'staging', sha(`open-head-${i}`)), state: 'open', merged_at: null }));
  }
  if (spec.theirsMergedBefore) {
    // Their pull request merged before the starting point; a run before this one judged it.
    const head = sha('merged-before-head');
    world.extraPulls = [pullRequest(208, sha('merged-before'), LB, 'staging', head)];
    world.guard[head] = spec.theirsMergedBefore;
    world.guardPr[head] = 208;
  }
  if (spec.theirsOpen) {
    // Their pull request open into staging, its head on their own branch.
    const head = sha('open-theirs-head');
    world.extraPulls = [{ ...pullRequest(209, sha('open-theirs-test-merge'), LB, 'staging', head), state: 'open', merged_at: null }];
    world.guard[head] = spec.theirsOpen;
    world.guardPr[head] = 209;
  }
  if (spec.notInClosedList) world.notInClosedList = true;
  if (spec.linkLag) world.linkLag = world.commits.map((c) => c.sha);
  if (spec.flaky) world.flaky = Object.fromEntries(spec.flaky.map((route) => [route, 1]));
  if (spec.acceptFirst) acceptIssue(world, world.commits[0].sha, spec.oldTitle);
  if (spec.otherTitle) world.closedIssues[0].title = `Docs pipeline stopped on ${world.branch}`;
  if (spec.noCommitActivity) {
    world.activity.unshift({ activity_type: 'push', actor: OTHER_APP, after: null, timestamp: '2026-11-17T12:40:00Z' });
  }
  return world;
}

async function runCases(gate, label) {
  const wrong = [];
  for (const [name, want, reason, spec] of CASES) {
    for (const mode of Object.keys(WORKFLOWS)) {
      let got;
      try {
        got = await decide(gate[mode], mode, worldFor(spec), spec.broken || []);
      } catch (err) {
        got = { outcome: 'crash', text: String(err && err.message) };
      }
      const problems = [];
      if (got.outcome !== want) problems.push(`expected ${want}, got ${got.outcome}`);
      if (want === 'stop' && got.outcome === 'stop' && reason && !got.text.includes(reason)) problems.push(`the stop does not say "${reason}"`);
      if (/crashed/.test(got.text)) problems.push('the gate crashed');
      if (got.writes > 1) problems.push(`made ${got.writes} writes; a stop opens or updates one issue once`);
      if (spec.maxCommitReads !== undefined && got.commitReads > spec.maxCommitReads) {
        problems.push(`read the pull requests of ${got.commitReads} commit(s) one by one; at most ${spec.maxCommitReads} should cost a read`);
      }
      if (problems.length) wrong.push(`${name} [${mode}]: ${problems.join('; ')}${got.text ? `: ${got.text.split('\n')[0]}` : ''}`);
      if (label === 'real') console.log(`${problems.length ? 'FAIL' : 'ok  '} ${want.padEnd(4)} ${name} [${mode}]${problems.length ? ` -> ${problems.join('; ')}` : ''}`);
    }
  }
  return wrong;
}

// Each planted fault is one exact edit to the gate script. Each must make at least one case go wrong.
const FAULTS = [
  ['their merge allowed on any branch', 'if (branch !== LB_BRANCH) return', 'if (false) return'],
  ['the guard result ignored', "if (job.conclusion !== 'success') {", 'if (false) {'],
  ['an unfinished guard counted as finished', "if (job.status !== 'completed') {", 'if (false) {'],
  ['no guard run counted as passed', 'if (!guard) return `no', "if (!guard) return ''; if (false) return `no"],
  ['the oldest guard run decides', '.sort((a, b) => Number(b.id) - Number(a.id));', '.sort((a, b) => Number(a.id) - Number(b.id));'],
  ['a guard job for another pull request or base accepted', 'jobs.filter((j) => j && j.name === jobName)', "jobs.filter((j) => j && String(j.name).startsWith('LaunchBrightly PR guard ('))"],
  ['two guard jobs of one name trusted', 'if (named.length > 1) throw', 'if (false) throw'],
  ['a short list of guard runs trusted', 'if (runs.length !== total) throw', 'if (false) throw'],
  ['a short list of guard jobs trusted', 'if (jobs.length !== listed.total_count) throw', 'if (false) throw'],
  ['the newest run decides even without the guard job', 'if (named.length) return { run, job: named[0] };',
    'return named.length ? { run, job: named[0] } : null;'],
  ['the pull request author not checked', 'if (!theirs.length) {', 'if (false) {'],
  ['the pull request base not checked', 'if (base !== LB_BRANCH) return', 'if (false) return'],
  ['a merge with no pull request let through', 'if (!prs.length) return `no merged pull request', "if (!prs.length) return ''; if (false) return `no merged pull request"],
  ['their id not checked', '=== LB_BOT && id === LB_BOT_ID', '=== LB_BOT'],
  ['any app\'s merge let through on their terms', "if (a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)) {", "if (a.activity_type === 'pr_merge') {"],
  ['a push by their app let through on their terms', "a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)", 'isLaunchBrightly(who, a.actor.id)'],
  ['the commits on staging not looked up by their pull request', 'const problem = await theirMergeProblem(c.sha);', 'const problem = null;'],
  ['anyone\'s pull request held to their rules', 'if (!(await mergedPrsOf(sha)).some(isTheirs)) return null;', 'if (!(await mergedPrsOf(sha)).length) return null;'],
  ['the closed pull requests not read when a commit is not linked yet', 'const listed = (await recentlyClosed()).filter(isMerge);', 'const listed = [];'],
  ['the merges GitHub made not looked up', '(byGitHub(c) || bots.length)', '(!byGitHub(c) && bots.length)'],
  ['the commits naming an app not looked up', '(byGitHub(c) || bots.length)', '(byGitHub(c))'],
  ['only the commits naming their own app looked up', '(byGitHub(c) || bots.length)', '(byGitHub(c) || bots.includes(LB_BOT))'],
  ['every staging commit looked up', '(byGitHub(c) || bots.length)', '(true)'],
  ['the stop for a commit no merged pull request has dropped', 'add(c.sha, `${identity(c)}; no merged pull request has it as its merge commit`);',
    '/* that stop dropped */'],
  ['only the first pull request on a shared commit judged', 'if (!(await mergedPrsOf(sha)).some(isTheirs)) return null;',
    'if (!isTheirs((await mergedPrsOf(sha))[0])) return null;'],
  ['only the first pull request of theirs on a shared commit judged', 'for (const pr of theirs) {', 'for (const pr of theirs.slice(0, 1)) {'],
  ['a fork\'s runs on the same commit counted', '&& r.head_repository && r.head_repository.full_name === headRepo)', ')'],
  ['only the first page of guard runs read', 'for (let page = 1; page <= MAX_GUARD_RUN_PAGES; page += 1) {', 'for (let page = 1; page <= 1; page += 1) {'],
  ['a failed write tried again', "if (!route.startsWith('GET ') || !(Number(err.status) >= 500)) throw err;", 'if (!(Number(err.status) >= 500)) throw err;'],
  ['a failed read not tried again', "if (!route.startsWith('GET ') || !(Number(err.status) >= 500)) throw err;", 'throw err;'],
  ['an unreadable actor let through', 'if (!who) {', 'if (!who) { continue;'],
  ['the anchor\'s own entry skipped', 'const who = a.actor && a.actor.login;', 'if (a.after === anchor.sha) continue; const who = a.actor && a.actor.login;'],
  ['a person\'s merge of their pull request not looked up', "if (branch === LB_BRANCH && a.activity_type === 'pr_merge') {", 'if (false) {'],
  ['a person\'s merge with no pull request let through', 'if (!(await mergedPrOf(a.after))) {', 'if (false) {'],
  ['their pull requests that reached staging not judged', 'const problem = merged ? await lbMergeProblem(at)', "const problem = merged ? ''"],
  ['their unmerged pull request with its head on staging let through', '      : `the head of ${LB_BOT}', "      : '' && `the head of ${LB_BOT}"],
  ['the open pull requests not read', '...(await openInto())', ''],
  ['only the first page of open pull requests read', 'if (data.length < 100) return out;', 'return out;'],
  ['their pull requests judged outside the range', 'if (!onBranch.has(at) || found.has(at)) continue;', 'if (found.has(at)) continue;'],
  ['an unmerged pull request judged by its merge commit', 'const at = merged ? pr.merge_commit_sha : pr.head && pr.head.sha;',
    'const at = pr.merge_commit_sha;'],
  ['the old issue title no longer accepted', '(issue.title === title || issue.title === oldTitle)', 'issue.title === title'],
  ['the gate\'s own issue title not accepted', '(issue.title === title || issue.title === oldTitle)', 'issue.title === oldTitle'],
];

// Each planted fault in the guard job is one change to the job as read from pr-validate.yml. Each must
// give at least one problem. The check step's text must hold each fault's text exactly once.
const checkStep = GUARD_JOB.steps.findIndex((s) => s.run.includes(CHECK_MARK));
const editCheck = (from, to) => (job) => {
  const steps = job.steps.map((s) => ({ ...s }));
  if (checkStep < 0 || steps[checkStep].run.split(from).length !== 2) return null;
  steps[checkStep].run = steps[checkStep].run.replace(from, to);
  return { ...job, steps };
};
const GUARD_FAULTS = [
  ['the refusal for their pull requests removed', editCheck('if [ "$author" = "launchbrightly[bot]" ] || [ "$PR_AUTHOR_ID" = "270903805" ]; then', 'if false; then')],
  ['the refusal by their login dropped', editCheck('[ "$author" = "launchbrightly[bot]" ] || ', '')],
  ['the refusal by their user id dropped', editCheck(' || [ "$PR_AUTHOR_ID" = "270903805" ]', '')],
  ['their login compared without lowering its case', editCheck("| tr '[:upper:]' '[:lower:]'", '| cat')],
  ['the pull request\'s own self-test moved before the check', (job) => {
    const own = job.steps.findIndex((s) => s.run.includes('python scripts/lb-pr-guard.py --self-test'));
    if (own < 0 || checkStep < 0) return null;
    const steps = job.steps.filter((_, i) => i !== own);
    steps.splice(checkStep, 0, job.steps[own]);
    return { ...job, steps };
  }],
  ['a step that runs a command added before the check', (job) => ({ ...job, steps: [{ name: 'Set up', uses: '', run: 'make setup' }, ...job.steps] })],
  ['the pull request\'s copy of the guard read instead of the base\'s',
    editCheck('git show HEAD^1:scripts/lb-pr-guard.py', 'git show HEAD^2:scripts/lb-pr-guard.py')],
  ['the pull request\'s copy of the rules read instead of the base\'s',
    editCheck('git show HEAD^1:scripts/asset_management/repo_screenshot_rules.py', 'git show HEAD^2:scripts/asset_management/repo_screenshot_rules.py')],
  ['the deciding step given an if:', (job) => (checkStep < 0 ? null
    : { ...job, steps: job.steps.map((s, i) => (i === checkStep ? { ...s, if: "github.event.pull_request.draft == false" } : s)) })],
  ['the deciding step allowed to fail', (job) => (checkStep < 0 ? null
    : { ...job, steps: job.steps.map((s, i) => (i === checkStep ? { ...s, continueOnError: true } : s)) })],
  ['the guard job allowed to fail', (job) => ({ ...job, continueOnError: true })],
  ['BASH_ENV set for the guard job', (job) => ({ ...job, env: { ...job.env, BASH_ENV: './scripts/setup.sh' } })],
  ['PYTHONPATH set on the deciding step', (job) => (checkStep < 0 ? null
    : { ...job, steps: job.steps.map((s, i) => (i === checkStep ? { ...s, env: { ...s.env, PYTHONPATH: '${{ github.workspace }}/scripts' } } : s)) })],
  ['env set for every job in pr-validate.yml', (job) => ({ ...job, workflowEnv: { ...job.workflowEnv, PYTHONSTARTUP: './x.py' } })],
  ['the checkout made to fetch the pull request\'s head', (job) => ({ ...job,
    steps: job.steps.map((s) => (/^actions\/checkout@/.test(s.uses) ? { ...s, with: { ...s.with, ref: '${{ github.event.pull_request.head.sha }}' } } : s)) })],
  ['the checkout made to fetch another repository', (job) => ({ ...job,
    steps: job.steps.map((s) => (/^actions\/checkout@/.test(s.uses) ? { ...s, with: { ...s.with, repository: '${{ github.event.pull_request.head.repo.full_name }}' } } : s)) })],
];

const realWrong = await runCases(scripts, 'real');
if (/\bset(Timeout|Interval)\b/.test(scripts.pipeline)) realWrong.push('the gate script names a timer, and the gate must never wait');
console.log(`\n${CASES.length} cases in each of 2 workflows: ${CASES.length * 2 - realWrong.length} right, ${realWrong.length} wrong.`);

const guardWrong = guardJobProblems(GUARD_JOB);
for (const p of guardWrong) console.log(`FAIL guard job: ${p}`);
console.log(`The guard job pr-validate.yml defines: ${guardWrong.length ? `${guardWrong.length} problem(s)` : 'nothing runs before the check that decides, it cannot be skipped or allowed to fail, with the guard on the base it judges everyone with the base\'s guard and rules, and with no guard on the base it refuses their pull request and uses anyone else\'s own copy'}.`);
for (const [name, plant] of GUARD_FAULTS) {
  const mutant = plant(GUARD_JOB);
  if (!mutant) cannotRun(`planted guard job fault "${name}": its text is not in the check step exactly once`);
  const caught = guardJobProblems(mutant).length > 0;
  console.log(`${caught ? 'caught' : 'MISSED'} planted fault in the guard job: ${name}`);
  if (!caught) realWrong.push(`no check catches the planted guard job fault "${name}"`);
}
realWrong.push(...guardWrong.map((p) => `guard job: ${p}`));

// The name the gate looks for must be the one pr-validate.yml gives the job: with another template the
// cases that pass must go wrong.
guardNameTemplate = GUARD_JOB.name.replace(' into ', ' on ');
const drift = await runCases(scripts, 'fault');
guardNameTemplate = GUARD_JOB.name;
console.log(`${drift.length ? 'caught' : 'MISSED'} planted fault: the guard job renamed in pr-validate.yml only${drift.length ? ` (${drift.length} case run(s) went wrong)` : ''}`);
if (!drift.length) realWrong.push('no case catches a guard job name that differs from the one the gate looks for');

const unseen = [];
for (const [name, from, to] of FAULTS) {
  const count = scripts.pipeline.split(from).length - 1;
  if (count !== 1) cannotRun(`planted fault "${name}": its text is in the gate script ${count} times, not once`);
  const mutant = scripts.pipeline.replace(from, to);
  try {
    new AsyncFunction(...PARAMS, mutant);
  } catch (err) {
    cannotRun(`planted fault "${name}" does not compile, so it would test nothing: ${err.message}`);
  }
  const wrong = await runCases({ pipeline: mutant, push: mutant }, 'fault');
  console.log(`${wrong.length ? 'caught' : 'MISSED'} planted fault: ${name}${wrong.length ? ` (${wrong.length} case run(s) went wrong)` : ''}`);
  if (!wrong.length) unseen.push(name);
}

if (realWrong.length || unseen.length) {
  for (const w of realWrong) console.error(`WRONG: ${w}`);
  for (const u of unseen) console.error(`MISSED: no case catches the planted fault "${u}"`);
  process.exit(1);
}
console.log(`All ${FAULTS.length} planted faults caught.`);
