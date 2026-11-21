# Repo skills

These folders are this repo's Claude Code skills. They live in `.skills/`, a folder Claude Code does not scan, so a session lists each skill once instead of once more for every git worktree of this repo. tallyfy/client, tallyfy/api-v2 and tallyfy/website-astro use the same layout. The three moved here from the repo's `.claude` folder on 2026-11-21 (tallyfy/documentation#569).

## How a session gets them

Claude Code does not look in `.skills/`. It sees a skill only through the user-level folder `~/.claude/skills/<name>`:

- On a developer's machine, a link there points at the skill's folder in a locked worktree of this repo that stays on `staging`, the skills pin. Git does not carry the links, so each machine adds them once, as below.
- Each SKILL.md carries a `paths:` line, so the skill is listed while a session works on files that match it, which is this repo's files. The patterns are loose on purpose: a folder named `documentation` or `src/content/docs` in another repo can match too, and the cost there is three extra lines in that session's skill list. `**/documentation/**` matches when the session started above this repo, for example in `~/GitHub`. The other patterns (`src/content/docs/**`, `screenshots/**` and `scripts/asset_management/**`) match when it started in this repo or one of its worktrees, because a pattern is read against the path from where the session started.
- No workflow here runs Claude Code, so no runner needs them.
- Codex reads them through the relative links in `.agents/skills/`.
- This repo's Pangram skill is `docs-pangram-check`. tallyfy/website-astro has a different skill named `pangram-check`, and two folders under `~/.claude/skills/` cannot share a name.

## A machine runs the pinned copy

A session on a developer's machine runs the pinned copy of a skill and of its scripts, not the copy on the branch being worked on. So a branch's edits to a skill reach sessions only after the change merges into `staging` and the pin is fast-forwarded. To try a changed script before then, run it from `.skills/<name>/scripts/` in your checkout. The asset scripts in `scripts/asset_management/` are not part of any skill folder and always run from your checkout.

## Adding the links on a machine

Set `DOCS` to the absolute path of your documentation checkout. If this machine already has the pin (`git -C "$DOCS" worktree list` shows `.claude/worktrees/skills-pin`), leave out the `worktree add` and `worktree lock` lines. A name under `~/.claude/skills/` that is already a folder, not a link, is left alone: some machines keep their own copy of `documentation-asset-manager` there.

```bash
DOCS=/absolute/path/to/documentation
if [ -n "$DOCS" ] && [ -d "$DOCS/.git" ]; then
  git -C "$DOCS" fetch origin staging &&
  git -C "$DOCS" worktree add -b skills-pin "$DOCS/.claude/worktrees/skills-pin" origin/staging &&
  git -C "$DOCS" worktree lock --reason "skills pin: ~/.claude/skills links point here" "$DOCS/.claude/worktrees/skills-pin" &&
  mkdir -p ~/.claude/skills &&
  for s in article-image-generator docs-pangram-check documentation-asset-manager; do
    if [ -d ~/.claude/skills/$s ] && [ ! -L ~/.claude/skills/$s ]; then
      echo "left alone: ~/.claude/skills/$s is a folder, not a link"
    else
      ln -sfn "$DOCS/.claude/worktrees/skills-pin/.skills/$s" ~/.claude/skills/$s
    fi
  done
else
  echo "DOCS is not a documentation checkout: $DOCS"
fi
```

To take a later change to the skills: `git -C "$DOCS/.claude/worktrees/skills-pin" pull --ff-only origin staging`.

To add a skill: put it in `.skills/<name>/` with a `paths:` line like the others, add its link in `.agents/skills/` (`ln -s ../../.skills/<name> .agents/skills/<name>`), and add its name to the loop above.
