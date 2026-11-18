#!/usr/bin/env node
// push-gate-cases.mjs: what the push gate decides, both ways, with no network (tallyfy/documentation#548).
//
// The push gate is an inline script in generate-ids.yml and documentation-pipeline.yml, and it may run no
// code from the repository. So this test takes the script out of each workflow file, checks that a YAML
// parser reads the same text (as scripts/pipeline-guard.py does), runs it against a fake GitHub API in each
// file's mode, and checks what it decides: a stop (core.setFailed) or a pass, and why it stopped. The gate
// never waits, so any wait is wrong. Then it plants faults in the script one at a time, and each must turn
// at least one case red, so a test that cannot fail is caught.
//
//   node scripts/push-gate-cases.mjs [--repo PATH]
//
// Needs python3 with PyYAML for the parser check. Exit 0: every case and every planted fault went the right
// way. Exit 1: one did not. Exit 2: could not run (a workflow or its gate script is missing, the YAML parser
// reads a different script, the two scripts differ, a planted fault's text is not in the script exactly
// once, or a planted fault does not compile).

import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
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

const sha = (label) => createHash('sha1').update(label).digest('hex');
const jobName = (number, base = 'staging') => `LaunchBrightly PR guard (#${number} into ${base})`;
const LB = { login: 'launchbrightly[bot]', id: 270903805, type: 'Bot' };
const LOOKALIKE = { login: 'launchbrightly[bot]', id: 5, type: 'Bot' };
const PERSON = { login: 'amitkoth', id: 1000, type: 'User' };
const OTHER_APP = { login: 'some-other-app[bot]', id: 99, type: 'Bot' };
const ACTIONS = { login: 'github-actions[bot]', id: 41898282, type: 'Bot' };
const WEB_FLOW = { login: 'web-flow', id: 19864447, type: 'User' };

const gitIdentity = (u) => ({ name: u.login, email: `${u.id}+${u.login}@users.noreply.github.com` });
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
  merged_at: '2026-11-17T12:00:00Z',
  merge_commit_sha: mergeSha,
  user: author,
  base: { ref: base },
  head: { sha: head },
});

const acceptIssue = (world, shaToAccept) => {
  world.closedIssues = [{ number: 7, title: `Docs pipeline stopped: commits reached ${world.branch} without a pull request` }];
  world.issues[7] = { state: 'closed', state_reason: 'completed', closed_by: PERSON, body: `- \`${shaToAccept}\`: accepted` };
};

// One change since the last good run. merge: a squash merge of a pull request, so its commit carries the
// pull request author's name and GitHub as committer; push: a commit pushed straight to the branch.
function scenario({ branch = 'staging', changes = [] }) {
  const anchor = sha(`anchor-${branch}`);
  const world = {
    branch, anchor, head: anchor, commits: [], activity: [], pulls: {}, guard: {}, guardPr: {}, jobs: {},
    closedIssues: [], issues: {}, waits: 0,
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
  world.activity.push({ activity_type: 'pr_merge', actor: PERSON, after: anchor, timestamp: '2026-11-17T11:00:00Z' });
  if (world.commits.length) world.head = world.commits[world.commits.length - 1].sha;
  return world;
}

function fakeGitHub(world, broken) {
  return {
    async request(route, params = {}) {
      if (broken.includes(route)) throw Object.assign(new Error('fake outage'), { status: 500 });
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
          const runs = GUARD[state](world.guardPr[params.head_sha]);
          for (const r of runs) world.jobs[r.id] = r;
          const listed = runs.map((r) => ({ id: r.id, event: 'pull_request', head_sha: params.head_sha, path: '.github/workflows/pr-validate.yml' }));
          return { data: { total_count: runs.totalCount || listed.length, workflow_runs: listed } };
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
          return { data: world.pulls[params.commit_sha] || [] };
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
const PARAMS = ['github', 'context', 'core', 'process', 'setTimeout'];

async function decide(script, mode, world, broken = []) {
  const failed = [];
  const errors = [];
  const core = { info() {}, warning() {}, error: (m) => errors.push(String(m)), setFailed: (m) => failed.push(String(m)) };
  const context = { repo: { owner: 'tallyfy', repo: 'documentation' }, serverUrl: 'https://github.com', runId: 2 };
  const env = mode === 'pipeline'
    ? { GATE_MODE: 'pipeline', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_TRIGGER_RUN_ID: '1', GATE_TRIGGER_CONCLUSION: 'success', GATE_TRIGGER_HEAD: world.anchor }
    : { GATE_MODE: 'push', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_HEAD: world.head };
  const fakeTimeout = (fn) => {
    world.waits += 1;
    if (world.waits > 3) throw new Error('the gate kept waiting');
    fn();
  };
  const gate = new AsyncFunction(...PARAMS, script);
  await gate(fakeGitHub(world, broken), context, core, { env }, fakeTimeout);
  return { outcome: failed.length ? 'stop' : 'pass', text: [...failed, ...errors].join('\n'), waits: world.waits };
}

const lbMerge = (extra = {}) => ({ kind: 'merge', by: LB, prAuthor: LB, ...extra });

// [name, expected outcome, text a stop must give, world]. Every case runs in both modes.
const CASES = [
  ['their app merges its own pull request into staging, guard passed', 'pass', null, { changes: [lbMerge()] }],
  ['their app merges its own pull request into staging, guard failed', 'stop', 'ended failure', { changes: [lbMerge({ guard: 'failure' })] }],
  ['their app merges before the guard has finished', 'stop', 'had not finished', { changes: [lbMerge({ guard: 'pending' })] }],
  ['their app merges and no guard run exists', 'stop', 'never ran', { changes: [lbMerge({ guard: 'missing' })] }],
  ['their app merges and the newest run has no guard job', 'stop', 'has no job', { changes: [lbMerge({ guard: 'no-job' })] }],
  ['their pull request passed the guard only against another base', 'stop', 'has no job', { changes: [lbMerge({ guard: 'other-base' })] }],
  ['only another pull request with the same head passed the guard, in the newest run', 'stop', 'has no job', { changes: [lbMerge({ guard: 'other-pr' })] }],
  ['an older run passed, but the newest run has no guard job yet', 'stop', 'has no job', { changes: [lbMerge({ guard: 'newest-has-no-job' })] }],
  ['an older guard run was cancelled and the newest passed', 'pass', null, { changes: [lbMerge({ guard: 'cancelled-then-success' })] }],
  ['the newest guard run was cancelled after an older pass', 'stop', 'ended cancelled', { changes: [lbMerge({ guard: 'success-then-cancelled' })] }],
  ['the newest run has two guard jobs of that name', 'stop', 'jobs named', { changes: [lbMerge({ guard: 'duplicate' })] }],
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
  ['their merge that made the starting point is not judged again', 'pass', null, { anchorIsTheirMerge: true }],
  ['an entry with no readable actor that made the starting point is not judged again', 'pass', null, { anchorActorless: true }],
  ['their merge with no passed guard that a person accepted', 'pass', null, { changes: [lbMerge({ guard: 'pending' })], acceptFirst: true }],
  ['github-actions pushes generated files', 'pass', null, { changes: [{ kind: 'push', by: ACTIONS }] }],
  ['nothing changed since the last good run', 'pass', null, { changes: [] }],
  ['a push or merge that names no commit is not judged', 'pass', null, { noCommitActivity: true }],
  ['who made a change cannot be read', 'stop', 'could not read', { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, actorless: true }] }],
  ['the pull requests of their merge cannot be read', 'stop', 'could not decide',
    { changes: [lbMerge()], broken: ['GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls'] }],
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
  if (spec.anchorIsTheirMerge) {
    // The last good run started from their merge, whose guard reads as failed now (a later re-run).
    const head = sha('anchor-merge-head');
    world.activity = [{ activity_type: 'pr_merge', actor: LB, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
    world.pulls[world.anchor] = [pullRequest(202, world.anchor, LB, 'staging', head)];
    world.guard[head] = 'failure';
    world.guardPr[head] = 202;
  }
  if (spec.anchorActorless) {
    world.activity = [{ activity_type: 'push', actor: null, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
  }
  if (spec.acceptFirst) acceptIssue(world, world.commits[0].sha);
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
        got = { outcome: 'crash', text: String(err && err.message), waits: 0 };
      }
      const problems = [];
      if (got.outcome !== want) problems.push(`expected ${want}, got ${got.outcome}`);
      if (got.waits) problems.push(`waited ${got.waits} time(s); the gate never waits`);
      if (want === 'stop' && got.outcome === 'stop' && reason && !got.text.includes(reason)) problems.push(`the stop does not say "${reason}"`);
      if (/crashed|kept waiting/.test(got.text)) problems.push('the gate crashed');
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
  ['a run without the guard job counted as passed', 'if (!job) return `the newest', "if (!job) return ''; if (false) return `the newest"],
  ['the oldest guard run decides', '(a === null || Number(r.id) > Number(a.id) ? r : a), null);', '(a === null || Number(r.id) < Number(a.id) ? r : a), null);'],
  ['a guard job for another pull request or base accepted', 'jobs.filter((j) => j && j.name === jobName)', "jobs.filter((j) => j && String(j.name).startsWith('LaunchBrightly PR guard ('))"],
  ['two guard jobs of one name trusted', 'if (named.length > 1) throw', 'if (false) throw'],
  ['a short list of guard runs trusted', 'if (runs.length !== data.total_count) throw', 'if (false) throw'],
  ['a short list of guard jobs trusted', 'if (jobs.length !== listed.total_count) throw', 'if (false) throw'],
  ['the pull request author not checked', 'if (!isLaunchBrightly(author.login, author.id)) {', 'if (false) {'],
  ['the pull request base not checked', 'if (base !== LB_BRANCH) return', 'if (false) return'],
  ['a merge with no pull request let through', 'if (!pr) return `no merged pull request', "if (!pr) return ''; if (false) return `no merged pull request"],
  ['their id not checked', '=== LB_BOT && id === LB_BOT_ID', '=== LB_BOT'],
  ['any app\'s merge let through on their terms', "if (a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)) {", "if (a.activity_type === 'pr_merge') {"],
  ['a push by their app let through on their terms', "a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)", 'isLaunchBrightly(who, a.actor.id)'],
  ['their pull requests on staging not checked when a person merges',
    'if (branch === LB_BRANCH && bots.includes(LB_BOT) && isLaunchBrightly(author.login, author.id)) {', 'if (false) {'],
  ['a person\'s pull request held to their rules', 'bots.includes(LB_BOT) && isLaunchBrightly(author.login, author.id)', 'bots.includes(LB_BOT)'],
  ['an unreadable actor let through', 'if (!who) {', 'if (!who) { continue;'],
  ['the anchor\'s unreadable entry judged again', 'if (a.after === anchor.sha) continue;', 'if (false) continue;'],
  ['their merge at the anchor judged again', 'if (a.after === anchor.sha) {', 'if (false) {'],
];

const realWrong = await runCases(scripts, 'real');
console.log(`\n${CASES.length} cases in each of 2 workflows: ${CASES.length * 2 - realWrong.length} right, ${realWrong.length} wrong.`);

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
