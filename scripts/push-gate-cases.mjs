#!/usr/bin/env node
// push-gate-cases.mjs: what the push gate decides, both ways, with no network (tallyfy/documentation#548).
//
// The push gate is an inline script in generate-ids.yml and documentation-pipeline.yml, and it may run no
// code from the repository. So this test takes the script out of each workflow file, runs it against a fake
// GitHub API, and checks what it decides: a stop (core.setFailed) or a pass, and how many times it waited.
// Then it plants faults in the script one at a time, and each must turn at least one case red, so a test
// that cannot fail is caught.
//
//   node scripts/push-gate-cases.mjs [--repo PATH]
//
// Exit 0: every case and every planted fault went the right way. Exit 1: one did not. Exit 2: could not run
// (a workflow or its gate script is missing, the two scripts differ, a planted fault's text is not in the
// script exactly once, or a planted fault does not compile).

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

const sha = (label) => createHash('sha1').update(label).digest('hex');
const GUARD = 'LaunchBrightly PR guard (into staging)';
const GUARD_OTHER_BASE = 'LaunchBrightly PR guard (into other-branch)';
const MAX_WAITS = 18; // LB_GUARD_POLLS in the gate
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

const run = (id, name, status, conclusion, slug = 'github-actions') => ({ id, name, app: { slug }, status, conclusion });
const RUNS = {
  success: () => [run(1, GUARD, 'completed', 'success')],
  failure: () => [run(1, GUARD, 'completed', 'failure')],
  pending: () => [run(1, GUARD, 'in_progress', null)],
  missing: () => [],
  lookalike: () => [run(1, GUARD, 'completed', 'success', 'launchbrightly')],
  'other-base': () => [run(1, GUARD_OTHER_BASE, 'completed', 'success')],
  'cancelled-then-success': () => [run(1, GUARD, 'completed', 'cancelled'), run(2, GUARD, 'completed', 'success')],
  'success-then-cancelled': () => [run(1, GUARD, 'completed', 'success'), run(2, GUARD, 'completed', 'cancelled')],
};

const pullRequest = (number, mergeSha, author, base, head) => ({
  number,
  merged_at: '2026-11-17T12:00:00Z',
  merge_commit_sha: mergeSha,
  user: author,
  base: { ref: base },
  head: { sha: head },
});

// One change since the last good run. merge: a squash merge of a pull request, so its commit carries the
// pull request author's name and GitHub as committer; push: a commit pushed straight to the branch.
function scenario({ branch = 'staging', changes = [] }) {
  const anchor = sha(`anchor-${branch}`);
  const world = { branch, anchor, head: anchor, commits: [], activity: [], pulls: {}, checks: {}, closedIssues: [], issues: {} };
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
      world.checks[head] = [...(ch.guard || ['success'])];
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
        case 'GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs':
          return { data: { workflow_runs: [{ id: 1, head_branch: world.branch, conclusion: 'success', head_sha: world.anchor }] } };
        case 'GET /repos/{owner}/{repo}/branches/{branch}':
          return { data: { commit: { sha: world.head } } };
        case 'GET /repos/{owner}/{repo}/compare/{basehead}':
          return { data: { status: world.commits.length ? 'ahead' : 'identical', total_commits: world.commits.length, commits: world.commits } };
        case 'GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls':
          return { data: world.pulls[params.commit_sha] || [] };
        case 'GET /repos/{owner}/{repo}/activity':
          return { data: world.activity, headers: {} };
        case 'GET /repos/{owner}/{repo}/commits/{ref}/check-runs': {
          const queue = world.checks[params.ref] || ['missing'];
          const state = queue.length > 1 ? queue.shift() : queue[0];
          if (state === 'broken') throw Object.assign(new Error('fake outage'), { status: 500 });
          const runs = RUNS[state]().filter((r) => r.name === params.check_name);
          return { data: { total_count: runs.length, check_runs: runs } };
        }
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
  let waits = 0;
  const core = { info() {}, warning() {}, error() {}, setFailed: (m) => failed.push(String(m)) };
  const context = { repo: { owner: 'tallyfy', repo: 'documentation' }, serverUrl: 'https://github.com', runId: 2 };
  const env = mode === 'pipeline'
    ? { GATE_MODE: 'pipeline', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_TRIGGER_RUN_ID: '1', GATE_TRIGGER_CONCLUSION: 'success', GATE_TRIGGER_HEAD: world.anchor }
    : { GATE_MODE: 'push', GATE_BRANCH: world.branch, GATE_RUN_ID: '2', GATE_HEAD: world.head };
  const fakeTimeout = (fn) => {
    waits += 1;
    if (waits > 3 * MAX_WAITS) throw new Error('the gate kept waiting past any limit');
    fn();
  };
  const gate = new AsyncFunction(...PARAMS, script);
  await gate(fakeGitHub(world, broken), context, core, { env }, fakeTimeout);
  return { outcome: failed.length ? 'stop' : 'pass', why: failed[0] || '', waits };
}

const lbMerge = (extra = {}) => ({ kind: 'merge', by: LB, prAuthor: LB, ...extra });

const CASES = [
  ['their app merges its own pull request into staging, guard passed', 'pass', { changes: [lbMerge()] }],
  ['their app merges its own pull request into staging, guard failed', 'stop', { changes: [lbMerge({ guard: ['failure'] })] }],
  ['their app merges its own pull request into staging, no guard check', 'stop', { changes: [lbMerge({ guard: ['missing'] })] }],
  ['their app merges before the guard ends, then the guard passes', 'pass', { changes: [lbMerge({ guard: ['pending', 'pending', 'success'] })] }],
  ['their app merges and the guard never ends', 'stop', { changes: [lbMerge({ guard: ['pending'] })] }],
  ['their app merges, and only a look-alike check from another app passed', 'stop', { changes: [lbMerge({ guard: ['lookalike'] })] }],
  ['their pull request passed the guard only against another base', 'stop', { changes: [lbMerge({ guard: ['other-base'] })] }],
  ['an older guard run was cancelled and the newest passed', 'pass', { changes: [lbMerge({ guard: ['cancelled-then-success'] })] }],
  ['the newest guard run was cancelled after an older pass', 'stop', { changes: [lbMerge({ guard: ['success-then-cancelled'] })] }],
  ['their app merges its own pull request into main', 'stop', { branch: 'main', changes: [lbMerge()] }],
  ['their app\'s merge shows up on main as the merge of its staging pull request', 'stop', { branch: 'main', changes: [lbMerge({ base: 'staging' })] }],
  ['their app merges a pull request a person opened', 'stop', { changes: [lbMerge({ prAuthor: PERSON })] }],
  ['their pull request into another branch lands on staging', 'stop', { changes: [lbMerge({ base: 'other-branch' })] }],
  ['their app merges a commit no pull request has', 'stop', { changes: [lbMerge({ prAuthor: PERSON, commitAuthor: PERSON, noPullRequest: true })] }],
  ['their app merges with a merge commit, not a squash', 'stop', { mergeCommit: true }],
  ['their app pushes straight to staging', 'stop', { changes: [{ kind: 'push', by: LB }] }],
  ['their app pushes, as a push, the merge commit of its own passing pull request', 'stop', { changes: [lbMerge()], pushInstead: true }],
  ['an app with their login but another id merges', 'stop', { changes: [{ kind: 'merge', by: LOOKALIKE, prAuthor: LOOKALIKE }] }],
  ['another app merges its own pull request into staging', 'stop', { changes: [{ kind: 'merge', by: OTHER_APP, prAuthor: OTHER_APP }] }],
  ['another app merges their pull request, guard passed', 'stop', { changes: [{ kind: 'merge', by: OTHER_APP, prAuthor: LB }] }],
  ['a person merges a person\'s pull request', 'pass', { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON }] }],
  ['a person merges their pull request, guard passed', 'pass', { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB }] }],
  ['a person merges their pull request, guard failed', 'stop', { changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: ['failure'] }] }],
  ['on main, a person merges their pull request straight in with a failed guard (as before this change)', 'pass', {
    branch: 'main', changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, guard: ['failure'] }],
  }],
  ['on main, a person merges a promotion that carries their commit', 'pass', {
    branch: 'main',
    changes: [
      { kind: 'merge', by: PERSON, prAuthor: LB, base: 'staging' },
      { kind: 'merge', by: PERSON, prAuthor: PERSON },
    ],
    promotion: true,
  }],
  ['main merged back into staging brings their commit from a pull request into main', 'stop', {
    changes: [{ kind: 'merge', by: PERSON, prAuthor: LB, base: 'main' }],
  }],
  ['an accepted merge of theirs with no guard is the starting point', 'pass', { anchorAccepted: true, maxWaits: 0 }],
  ['github-actions pushes generated files', 'pass', { changes: [{ kind: 'push', by: ACTIONS }] }],
  ['nothing changed since the last good run', 'pass', { changes: [] }],
  ['a push or merge that names no commit is not judged', 'pass', { noCommitActivity: true }],
  ['who made a change cannot be read', 'stop', { changes: [{ kind: 'merge', by: PERSON, prAuthor: PERSON, actorless: true }] }],
  ['the pull requests of their merge cannot be read', 'stop', { changes: [lbMerge()], broken: ['GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls'] }],
  ['the guard result cannot be read', 'stop', { changes: [lbMerge({ guard: ['broken'] })] }],
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
    world.checks[head] = ['success'];
    world.activity.unshift({ activity_type: 'pr_merge', actor: LB, after: merge.sha, timestamp: '2026-11-17T12:30:00Z' });
    world.head = merge.sha;
  }
  if (spec.anchorAccepted) {
    // The last good run started from their merge, which had no guard; a person accepted it on the gate's issue.
    const head = sha('accepted-head');
    world.activity = [{ activity_type: 'pr_merge', actor: LB, after: world.anchor, timestamp: '2026-11-17T11:00:00Z' }];
    world.pulls[world.anchor] = [pullRequest(202, world.anchor, LB, 'staging', head)];
    world.checks[head] = ['missing'];
    world.closedIssues = [{ number: 7, title: `Docs pipeline stopped: commits reached ${world.branch} without a pull request` }];
    world.issues[7] = { state: 'closed', state_reason: 'completed', closed_by: PERSON, body: `- \`${world.anchor}\`: accepted` };
  }
  if (spec.noCommitActivity) {
    world.activity.unshift({ activity_type: 'push', actor: OTHER_APP, after: null, timestamp: '2026-11-17T12:40:00Z' });
  }
  return world;
}

async function runCases(scripts, label) {
  const wrong = [];
  for (const [name, want, spec] of CASES) {
    const maxWaits = spec.maxWaits === undefined ? MAX_WAITS : spec.maxWaits;
    for (const [mode, script] of Object.entries(scripts)) {
      let got;
      try {
        got = await decide(script, mode, worldFor(spec), spec.broken || []);
      } catch (err) {
        got = { outcome: 'crash', why: String(err && err.message), waits: 0 };
      }
      const ok = got.outcome === want && got.waits <= maxWaits;
      if (!ok) wrong.push(`${name} [${mode}]: expected ${want} within ${maxWaits} wait(s), got ${got.outcome} after ${got.waits}${got.why ? `: ${got.why}` : ''}`);
      if (label === 'real') console.log(`${ok ? 'ok  ' : 'FAIL'} ${want.padEnd(4)} ${name} [${mode}]${ok ? '' : ` -> ${got.outcome} after ${got.waits} wait(s): ${got.why}`}`);
    }
  }
  return wrong;
}

// Each planted fault is one exact edit to the gate script. Each must make at least one case go wrong.
const FAULTS = [
  ['their merge allowed on any branch', 'if (branch !== LB_BRANCH) return', 'if (false) return'],
  ['the guard result ignored', "if (newest.conclusion !== 'success') {", 'if (false) {'],
  ['a missing guard counted as passed', "if (newest && newest.status === 'completed') {", "if (!newest) return ''; if (newest.status === 'completed') {"],
  ['an unfinished guard counted as finished', "if (newest && newest.status === 'completed') {", 'if (newest) {'],
  ['the oldest guard run decides', 'const newest = runs.reduce((a, r) => (a === null || Number(r.id) > Number(a.id) ? r : a), null);', 'const newest = runs[0] || null;'],
  ['a guard judged against another base accepted', 'const LB_GUARD_CHECK = `LaunchBrightly PR guard (into ${LB_BRANCH})`;', 'const LB_GUARD_CHECK = `LaunchBrightly PR guard (into other-branch)`;'],
  ['a check from any app accepted', 'r.app && r.app.slug === LB_GUARD_APP', 'true'],
  ['the pull request author not checked', 'if (!isLaunchBrightly(author.login, author.id)) {', 'if (false) {'],
  ['the pull request base not checked', 'if (base !== LB_BRANCH) return', 'if (false) return'],
  ['a merge with no pull request let through', 'if (!pr) return `no merged pull request', "if (!pr) return ''; if (false) return `no merged pull request"],
  ['their id not checked', '=== LB_BOT && id === LB_BOT_ID', '=== LB_BOT'],
  ['any app\'s merge let through on their terms', "if (a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)) {", "if (a.activity_type === 'pr_merge') {"],
  ['a push by their app let through on their terms', "a.activity_type === 'pr_merge' && isLaunchBrightly(who, a.actor.id)", 'isLaunchBrightly(who, a.actor.id)'],
  ['their commits on staging not checked when a person merges', 'if (branch === LB_BRANCH && bots.includes(LB_BOT)) {', 'if (false) {'],
  ['an unreadable actor let through', 'if (!who) {', 'if (!who) { continue;'],
  ['an accepted commit still waited for', 'if ((await acceptedOnce()).has(sha)) return', 'if (false) return'],
  ['no wait for an unfinished guard', 'const LB_GUARD_POLLS = 18;', 'const LB_GUARD_POLLS = 0;'],
  ['no limit on the wait', 'if (lbPollsLeft <= 0) return why;', 'if (false) return why;'],
];

const scripts = {};
for (const [mode, path] of Object.entries(WORKFLOWS)) {
  const s = gateScript(join(repoRoot, path));
  if (!s) cannotRun(`no push-gate script found in ${path}`);
  scripts[mode] = s;
}
if (scripts.pipeline !== scripts.push) cannotRun('the push-gate scripts in the two workflows differ');

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
