#!/usr/bin/env python3
"""
Update lastUpdated field in MDX frontmatter based on Git history.
This script reads the Git last modified date for each MDX file and updates
the frontmatter accordingly. Runs in the documentation repository where 
content is authored.

    python scripts/update-last-modified.py --dir=src/content/docs
    python scripts/update-last-modified.py --self-test

--self-test proves the date parser reads every form git prints, on the Python
the pipeline pins (3.10), and refreshes a page in a scratch git repository.
Exit 0 passed, 1 a case failed.

Which commits count (owner decision 2026-10-02, tallyfy/work-queue#3466): the
date is the newest commit to the page that a person authored and that changed
more than formatting. Pipeline bot commits ("GitHub Action", any "[bot]"
author) are skipped, and so is a commit whose only change to the page is
whitespace or the lastUpdated line itself. A page with no such commit keeps the
lastUpdated it has.

Owner decision 217 (2026-10-03): content commits by tallyfy-workhorse[bot]
count, because it lands content pull requests a person reviewed. Every other
bot stays out, which now includes two identities the filter used to read as
people: "GitHub Actions Bot", the identity the pipeline's sync job commits as
(tallyfy/work-queue#3544), and "Cursor Agent". A formatting-only or
lastUpdated-only commit still never counts, whoever made it.
"""

import os
import re
import sys
import argparse
import tempfile
import frontmatter
import subprocess
from pathlib import Path
from datetime import datetime

def parse_git_date(git_date):
    """The YYYY-MM-DD date of a `git log --format=%aI` value.

    Git prints a UTC date with a trailing `Z` (2026-09-23T01:40:52Z) and any other
    offset in full (2026-09-22T20:37:48-05:00). The pipeline pins Python 3.10, whose
    datetime.fromisoformat rejects the `Z`; 3.11 and later accept it. So the `Z` is
    rewritten to +00:00 first. Before this, every page whose newest commit was dated in
    UTC was skipped with "Invalid isoformat string" and kept a stale lastUpdated: 587
    such lines in each of staging runs 35813737212 and 35813745697 on 2026-09-23
    (tallyfy/documentation#295). The date is the author's own calendar date, as before.
    Raises ValueError on anything that is not an ISO 8601 date.
    """
    text = git_date.strip()
    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).date().isoformat()

# Authors whose commits never set a page's date: the documentation pipeline commits as
# "GitHub Action" (action@github.com), and GitHub Apps commit as "<name>[bot]". Measured
# 2026-10-02 on src/content/docs history: 1,043 commits by "GitHub Action", mostly "Push
# related articles", and 4 by "tallyfy-workhorse[bot]" in the newest 400.
#
# "github actions bot" is the sync job's identity ("Commit and push changes" in
# documentation-pipeline.yml, email `<>`). It has 6 commits on staging, and one of them,
# 2d1ce39bd on 2026-02-25, touches src/content/docs, which no rule above caught
# (tallyfy/work-queue#3544).
# "Cursor Agent" (cursoragent@cursor.com) is an AI agent that committed once, b469a2bbf on
# 2026-05-12, and carries no "[bot]" suffix. Measured 2026-10-03: it sets no page's date today,
# because both pages it touched have a later person edit.
BOT_AUTHOR_NAMES = {"github action", "github-actions", "github actions bot", "cursor agent"}
BOT_AUTHOR_EMAILS = {"action@github.com", "cursoragent@cursor.com"}

# The one app whose commits DO count (owner decision 217, 2026-10-03). tallyfy-workhorse[bot]
# lands content pull requests that a person reviewed, so its content edits are authored
# changes. Matched on the name and on GitHub's noreply address for an app,
# "<app user id>+tallyfy-workhorse[bot]@users.noreply.github.com". Measured 2026-10-03: four
# commits in src/content/docs history, all as 322529570+tallyfy-workhorse[bot]@... Every other
# "[bot]" author stays excluded.
COUNTED_APP_NAME = "tallyfy-workhorse[bot]"
COUNTED_APP_EMAIL_SUFFIX = "+tallyfy-workhorse[bot]@users.noreply.github.com"


def is_counted_app(name, email):
    """True for tallyfy-workhorse[bot], the one app whose content commits count."""
    n = (name or "").strip().lower()
    e = (email or "").strip().lower()
    return n == COUNTED_APP_NAME and e.endswith(COUNTED_APP_EMAIL_SUFFIX)


def is_bot_author(name, email):
    """True when a commit's author is a pipeline or app bot whose commits never set a
    page's date. tallyfy-workhorse[bot] is not one of them (owner decision 217)."""
    if is_counted_app(name, email):
        return False
    n = (name or "").strip().lower()
    e = (email or "").strip().lower()
    return n in BOT_AUTHOR_NAMES or n.endswith("[bot]") or e in BOT_AUTHOR_EMAILS


_LAST_UPDATED_LINE = re.compile(r"^lastUpdated:.*$", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


def formatting_key(text):
    """The page with every whitespace run and the lastUpdated line removed. Two versions
    with the same key differ only in formatting, so a commit between them is not an
    authored change."""
    return _WHITESPACE.sub("", _LAST_UPDATED_LINE.sub("", text or ""))


def _git_out(cwd, *args):
    result = subprocess.run(['git', *args], capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout


def get_git_last_modified(file_path):
    """The date of the newest commit to file_path that a person authored and that changed
    more than formatting, as YYYY-MM-DD, or None when there is none.

    Until 2026-10-02 this was simply the newest commit (`git log -1`), so a related
    articles refresh by the pipeline bot set the public "last updated" date: 40 of 40
    sampled pages after staging run 36952690737 (tallyfy/work-queue#3466)."""
    try:
        # realpath on both sides: git prints the top level with symlinks resolved (macOS
        # /var is /private/var), and a relative path built across that difference would
        # name no file, which would read as "content changed" on every commit.
        path = os.path.realpath(file_path)
        folder = os.path.dirname(path)
        rc, top = _git_out(folder, 'rev-parse', '--show-toplevel')
        if rc != 0 or not top.strip():
            return None
        rel = os.path.relpath(path, os.path.realpath(top.strip()))
        # Newest first. A tab cannot appear in a name or an email.
        rc, log = _git_out(folder, 'log', '--format=%H%x09%an%x09%ae%x09%aI', '--', path)
        if rc != 0:
            return None
        for line in log.splitlines():
            parts = line.split('\t')
            if len(parts) != 4:
                continue
            sha, name, email, date = parts
            if is_bot_author(name, email):
                continue
            rc_after, after = _git_out(folder, 'show', f'{sha}:{rel}')
            rc_before, before = _git_out(folder, 'show', f'{sha}^:{rel}')
            if rc_after == 0 and rc_before == 0 and formatting_key(after) == formatting_key(before):
                continue  # whitespace or the lastUpdated line only
            # The page was created here, deleted here, or changed in content.
            return parse_git_date(date)
        return None
    except Exception as e:
        print(f"Error getting git date for {file_path}: {e}")
        return None

def update_file_last_modified(file_path):
    """Update the lastUpdated field in a file's frontmatter."""
    try:
        # Read the file with frontmatter
        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        
        # Get Git last modified date
        git_date = get_git_last_modified(file_path)
        
        if git_date:
            # For Astro, we need to write the date as an unquoted YAML date
            # python-frontmatter will write date objects without quotes
            from datetime import datetime
            date_obj = datetime.strptime(git_date, '%Y-%m-%d').date()
            
            # Check if we need to update
            current_last_updated = post.get('lastUpdated')
            
            # Force update if current is a string (needs to be date object for Astro)
            # or if the date value has changed
            if isinstance(current_last_updated, str):
                # Always update strings to date objects for proper YAML formatting
                needs_update = True
            elif hasattr(current_last_updated, 'date'):
                needs_update = current_last_updated.date() != date_obj
            else:
                needs_update = current_last_updated != date_obj
            
            if needs_update:
                # Update the lastUpdated field with date object
                # This will be written as: lastUpdated: 2025-08-15 (without quotes)
                post['lastUpdated'] = date_obj
                
                # Write the file back - frontmatter.dumps will write dates without quotes
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(frontmatter.dumps(post))
                
                print(f"✅ Updated {file_path}: lastUpdated = {git_date}")
                return True
            else:
                print(f"⏭️  Skipped {file_path}: already up-to-date")
                return False
        else:
            print(f"⚠️  No person-authored content commit for {file_path}; lastUpdated left as it is")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def process_directory(dir_path):
    """Process all MDX files in a directory recursively."""
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    # Files to skip
    skip_list = ["404.mdx"]
    
    # Walk through all MDX files
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.mdx') and file not in skip_list:
                file_path = os.path.join(root, file)
                result = update_file_last_modified(file_path)
                
                if result is True:
                    updated_count += 1
                elif result is False:
                    skipped_count += 1
                else:
                    error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Update lastUpdated dates in MDX frontmatter from Git history'
    )
    
    # Add arguments
    parser.add_argument(
        '--dir', 
        type=str, 
        default='src/content/docs',
        help='Directory path containing MDX files (default: src/content/docs)'
    )
    
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Prove the git date parser and the page refresh work, then exit'
    )
    
    args = parser.parse_args()
    
    if args.self_test:
        return self_test()
    
    # Resolve the directory path
    dir_path = Path(args.dir).resolve()
    
    if not dir_path.exists():
        print(f"❌ Directory not found: {dir_path}")
        return 1
    
    print(f"📁 Processing MDX files in: {dir_path}")
    print("=" * 60)
    
    # Process all files
    updated, skipped, errors = process_directory(str(dir_path))
    
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   ✅ Updated: {updated} files")
    print(f"   ⏭️  Skipped: {skipped} files")
    if errors > 0:
        print(f"   ❌ Errors: {errors} files")
    
    # Return non-zero exit code if there were errors
    return 1 if errors > 0 else 0

# ---------------------------------------------------------------------------
# Self-test (tallyfy/documentation#295).
#
# The pipeline pins Python 3.10, and only 3.10 rejects git's `Z`. A test run on
# 3.11 or later would pass on the broken code too, so the parse arms run against
# a datetime that refuses a trailing `Z` exactly as 3.10 does. On 3.10 that is
# what the real one already does; on later versions it is what keeps the arms
# able to fail.
# ---------------------------------------------------------------------------

class _Py310Datetime(datetime):
    @classmethod
    def fromisoformat(cls, date_string):
        if date_string[-1:] in ("Z", "z"):
            raise ValueError(f"Invalid isoformat string: {date_string!r}")
        return super().fromisoformat(date_string)


def _git(repo, *args, date=None, author=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Self Test", GIT_AUTHOR_EMAIL="self-test@example.com",
               GIT_COMMITTER_NAME="Self Test", GIT_COMMITTER_EMAIL="self-test@example.com")
    if author:
        env["GIT_AUTHOR_NAME"], env["GIT_AUTHOR_EMAIL"] = author
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(['git', '-c', 'commit.gpgsign=false', *args], cwd=repo, env=env,
                          capture_output=True, text=True, check=True).stdout


def self_test():
    cases = []

    def case(name, ok, detail=""):
        cases.append(ok)
        print(f"  [{'ok' if ok else 'FAILED'}] {name}{(' - ' + detail) if detail else ''}")

    def parsed(value):
        try:
            return parse_git_date(value)
        except Exception as exc:  # noqa: BLE001 - an exception is a result here
            return f"raised {exc!r}"

    print(f"Self-test on Python {sys.version.split()[0]}: git dates parse the way 3.10 needs.")
    module = sys.modules[__name__]
    real = module.datetime
    module.datetime = _Py310Datetime
    try:
        got = parsed("2026-09-23T01:40:52Z")
        case("a UTC date ending in Z parses under Python 3.10 rules", got == "2026-09-23", got)
        got = parsed("2026-09-22T20:37:48-05:00")
        case("an offset date keeps the author's own calendar date", got == "2026-09-22", got)
        got = parsed("2026-09-23T01:40:52+00:00\n")
        case("+00:00, which git 2.43 prints for UTC (2.55 prints Z), still parses", got == "2026-09-23", got)
        got = parsed("2026-13-45T99:00:00Z")
        case("a malformed date raises ValueError rather than returning a date",
             got.startswith("raised ValueError"), got)
    finally:
        module.datetime = real

    # A real page in a scratch repository, refreshed through the script's own path.
    with tempfile.TemporaryDirectory() as tmp:
        _git(tmp, 'init', '-q')
        utc_page = Path(tmp, 'utc.mdx')
        offset_page = Path(tmp, 'offset.mdx')
        utc_page.write_text("---\ntitle: UTC\nlastUpdated: 2020-01-01\n---\n\nBody.\n", encoding='utf-8')
        offset_page.write_text("---\ntitle: Offset\nlastUpdated: 2020-01-01\n---\n\nBody.\n", encoding='utf-8')
        _git(tmp, 'add', 'offset.mdx')
        _git(tmp, 'commit', '-q', '-m', 'offset page', date="2026-09-22T20:37:48-05:00")
        _git(tmp, 'add', 'utc.mdx')
        _git(tmp, 'commit', '-q', '-m', 'utc page', date="2026-09-23T01:40:52+00:00")
        printed = _git(tmp, 'log', '-1', '--format=%aI', '--', 'utc.mdx').strip()
        module.datetime = _Py310Datetime
        try:
            refreshed = update_file_last_modified(str(utc_page))
            refreshed_offset = update_file_last_modified(str(offset_page))
        finally:
            module.datetime = real
        utc_now = frontmatter.load(str(utc_page)).get('lastUpdated')
        offset_now = frontmatter.load(str(offset_page)).get('lastUpdated')
        case("a page whose newest commit is dated in UTC gets its lastUpdated refreshed",
             refreshed is True and str(utc_now) == "2026-09-23",
             f"git printed {printed}, lastUpdated is now {utc_now}")
        case("a page whose newest commit carries an offset is refreshed to that date",
             refreshed_offset is True and str(offset_now) == "2026-09-22",
             f"lastUpdated is now {offset_now}")

    # Which commits count (tallyfy/work-queue#3466). Each page gets a person's content commit,
    # then a later commit that must NOT move the date. Against the old `git log -1` every one
    # of these pages takes the later date, so each arm can fail.
    bot = ("GitHub Action", "action@github.com")
    # Any app other than tallyfy-workhorse[bot]. Until decision 217 this case used workhorse.
    app = ("google-labs-jules[bot]", "161369871+google-labs-jules[bot]@users.noreply.github.com")
    workhorse = ("tallyfy-workhorse[bot]", "322529570+tallyfy-workhorse[bot]@users.noreply.github.com")
    sync_bot = ("GitHub Actions Bot", "")
    cursor = ("Cursor Agent", "cursoragent@cursor.com")
    person = ("A Person", "person@example.com")
    with tempfile.TemporaryDirectory() as tmp:
        _git(tmp, 'init', '-q')

        def commit(page, text, date, who):
            Path(tmp, page).write_text(text, encoding='utf-8')
            _git(tmp, 'add', page)
            _git(tmp, 'commit', '-q', '-m', f'{page} by {who[0]}', date=date, author=who)

        head = "---\ntitle: T\nlastUpdated: 2020-01-01\n---\n\n"
        commit('bot.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('bot.mdx', head + "Written by a person.\n\n## Related articles\n- x\n", "2026-09-20T12:00:00Z", bot)
        commit('app.mdx', head + "Written by a person.\n", "2026-09-11T12:00:00+00:00", person)
        commit('app.mdx', head + "Written by a person, then an app.\n", "2026-09-21T12:00:00Z", app)
        commit('wrap.mdx', head + "One long line of real prose here.\n", "2026-09-12T12:00:00+00:00", person)
        commit('wrap.mdx', head + "One long line\nof real   prose here.\n\n", "2026-09-22T12:00:00+00:00", person)
        commit('stamp.mdx', head + "Body.\n", "2026-09-13T12:00:00+00:00", person)
        commit('stamp.mdx', head.replace("2020-01-01", "2026-09-13") + "Body.\n", "2026-09-23T12:00:00+00:00", person)
        commit('edit.mdx', head + "First.\n", "2026-09-14T12:00:00+00:00", person)
        commit('edit.mdx', head + "First.\n\n## Related articles\n- x\n", "2026-09-15T12:00:00Z", bot)
        commit('edit.mdx', head + "First, then edited by a person.\n\n## Related articles\n- x\n", "2026-09-24T12:00:00+00:00", person)
        commit('onlybot.mdx', head + "Generated.\n", "2026-09-16T12:00:00Z", bot)

        # Owner decision 217 (2026-10-03). Every page below starts with a person's edit on
        # 2026-09-10, so the filter before decision 217, which skipped workhorse and counted
        # "GitHub Actions Bot", answers wrongly on each of them.
        commit('wh.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('wh.mdx', head + "Corrected by workhorse.\n", "2026-09-17T13:09:31-05:00", workhorse)
        # A workhorse content edit, then a workhorse rewrap and a person's lastUpdated-only
        # commit, neither of which may move the date. A fix that trusted workhorse without
        # the formatting rule would answer 2026-09-25 here.
        commit('wh-format.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('wh-format.mdx', head + "Corrected by workhorse, one line.\n", "2026-09-20T12:00:00+00:00", workhorse)
        commit('wh-format.mdx', head + "Corrected by workhorse,\none line.\n\n", "2026-09-25T12:00:00+00:00", workhorse)
        commit('wh-format.mdx', head.replace("2020-01-01", "2026-09-20") + "Corrected by workhorse,\none line.\n\n",
               "2026-09-26T12:00:00+00:00", person)
        # A workhorse content edit, then content edits by another app and by the pipeline bot,
        # neither of which may move the date. A fix that counted every "[bot]" would answer
        # 2026-09-25 here.
        commit('wh-others.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('wh-others.mdx', head + "Corrected by workhorse.\n", "2026-09-20T12:00:00+00:00", workhorse)
        commit('wh-others.mdx', head + "Corrected by workhorse, then another app.\n", "2026-09-25T12:00:00Z", app)
        commit('wh-others.mdx', head + "Corrected by workhorse, then another app.\n\n## Related articles\n- x\n",
               "2026-09-26T12:00:00Z", bot)
        # The sync job's identity, "GitHub Actions Bot" with an empty email (work-queue#3544).
        commit('syncbot.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('syncbot.mdx', head + "Written by a person, then merged by sync.\n", "2026-09-20T12:00:00Z", sync_bot)
        # An AI agent with no "[bot]" suffix is still a bot (decision 217: other bots stay out).
        commit('cursor.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('cursor.mdx', head + "Written by a person, then an agent.\n", "2026-09-20T12:00:00Z", cursor)
        # Someone else naming themselves tallyfy-workhorse[bot] is not the app.
        commit('wh-impostor.mdx', head + "Written by a person.\n", "2026-09-10T12:00:00+00:00", person)
        commit('wh-impostor.mdx', head + "Not the app.\n", "2026-09-20T12:00:00Z",
               ("tallyfy-workhorse[bot]", "someone@example.com"))

        def date_of(page):
            return get_git_last_modified(str(Path(tmp, page)))

        got = date_of('bot.mdx')
        case("a pipeline bot commit after a person's edit does not move the date",
             got == "2026-09-10", f"got {got}")
        got = date_of('app.mdx')
        case("an app '[bot]' commit (not workhorse) after a person's edit does not move the date",
             got == "2026-09-11", f"got {got}")
        got = date_of('wh.mdx')
        case("217: a tallyfy-workhorse[bot] content edit moves the date to its own date",
             got == "2026-09-17", f"got {got}")
        got = date_of('wh-format.mdx')
        case("217: a workhorse rewrap and a lastUpdated-only commit after it do not move the date",
             got == "2026-09-20", f"got {got}")
        got = date_of('wh-others.mdx')
        case("217: other apps and the pipeline bot after a workhorse edit do not move the date",
             got == "2026-09-20", f"got {got}")
        got = date_of('syncbot.mdx')
        case("3544: a 'GitHub Actions Bot' commit with an empty email does not move the date",
             got == "2026-09-10", f"got {got}")
        got = date_of('cursor.mdx')
        case("217: a 'Cursor Agent' commit, a bot with no '[bot]' suffix, does not move the date",
             got == "2026-09-10", f"got {got}")
        got = date_of('wh-impostor.mdx')
        case("217: the workhorse name with some other email is not the app, so it does not count",
             got == "2026-09-10", f"got {got}")
        got = date_of('wrap.mdx')
        case("a person's whitespace-only rewrap does not move the date",
             got == "2026-09-12", f"got {got}")
        got = date_of('stamp.mdx')
        case("a commit that changes only the lastUpdated line does not move the date",
             got == "2026-09-13", f"got {got}")
        got = date_of('edit.mdx')
        case("control: a person's content edit after a bot commit does move the date",
             got == "2026-09-24", f"got {got}")
        got = date_of('onlybot.mdx')
        case("a page only bots have touched has no date to give, so it is left alone",
             got is None, f"got {got}")
        before = frontmatter.load(str(Path(tmp, 'onlybot.mdx'))).get('lastUpdated')
        update_file_last_modified(str(Path(tmp, 'onlybot.mdx')))
        after = frontmatter.load(str(Path(tmp, 'onlybot.mdx'))).get('lastUpdated')
        case("and its lastUpdated is unchanged", str(before) == str(after) == "2020-01-01",
             f"{before} then {after}")

    failed = cases.count(False)
    if failed:
        print(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0

if __name__ == "__main__":
    exit(main())