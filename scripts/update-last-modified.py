#!/usr/bin/env python3
"""
Update lastUpdated field in MDX frontmatter based on Git history.
This script reads the Git last modified date for each MDX file and updates
the frontmatter accordingly. Runs in the documentation repository where 
content is authored.

    python scripts/update-last-modified.py --dir=src/content/docs
    python scripts/update-last-modified.py --promotion-base origin/main [--check]
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

Subset promotions (tallyfy/documentation#492): the pipeline never rewrites dates
on main (#56), and a squash promotion carries a page's content without the
staging commit that moved its lastUpdated. --promotion-base REF, run on a
promotion branch, gives each page whose content the branch changes since it
left REF the date of its newest authored change in the branch's own history,
by the rule above with the Related articles block left out, and rewrites that
one line only. A page already showing a later date keeps it, so shipping an
older staging change after a newer one never moves a date back. --check
reports instead of writing: exit 0 every such page carries its date, 1 one
does not, 2 the answer could not be read.
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


RELATED_HEADING = "## Related articles"


def authored_key(text):
    """formatting_key of the page above its Related articles block. generate-related-articles.py
    rewrites everything from the first "## Related articles" on, and a subset ship may copy
    staging's cards by hand (#500), so neither is an authored change to the page (#492)."""
    return formatting_key((text or "").split(RELATED_HEADING, 1)[0])


def _git_out(cwd, *args):
    result = subprocess.run(['git', *args], capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout


def get_git_last_modified(file_path, key=formatting_key):
    """The date of the newest commit to file_path that a person authored and that changed
    more than formatting, as YYYY-MM-DD, or None when there is none.

    Until 2026-10-02 this was simply the newest commit (`git log -1`), so a related
    articles refresh by the pipeline bot set the public "last updated" date: 40 of 40
    sampled pages after staging run 36952690737 (tallyfy/work-queue#3466).

    key decides which commits changed more than formatting. The staging date job uses
    formatting_key; a promotion uses authored_key, so a card copy does not set the date (#492)."""
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
            if rc_after == 0 and rc_before == 0 and key(after) == key(before):
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

_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _frontmatter_lines(text):
    """(lines with their endings, index of the closing ---) or None when the page has no front
    matter block. Lines end at "\\n" only, so joining them gives back the same bytes; str.splitlines
    would also split at characters such as U+2028."""
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return lines, i
    return None


def last_updated_text(text):
    """The value written after `lastUpdated:` in the front matter, as text, or None."""
    found = _frontmatter_lines(text or "")
    if found is None:
        return None
    lines, end = found
    for line in lines[1:end]:
        if line.startswith("lastUpdated:"):
            return line[len("lastUpdated:"):].strip()
    return None


def set_last_updated(file_path, date_text):
    """Write `lastUpdated: <date_text>` into the page's front matter and change no other byte,
    so CRLF card lines and the YAML layout survive. A page with no such line gets one before the
    first top-level key that sorts after it, which is where the date job's YAML dump puts it.
    True when the file changed. Raises ValueError for a page with no front matter."""
    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    found = _frontmatter_lines(text)
    if found is None:
        raise ValueError(f"{file_path} has no front matter block")
    lines, end = found
    for i in range(1, end):
        if lines[i].startswith("lastUpdated:"):
            body = lines[i].rstrip("\r\n")
            lines[i] = f"lastUpdated: {date_text}" + lines[i][len(body):]
            break
    else:
        ending = lines[0][3:] or "\n"
        at = end
        for i in range(1, end):
            match = _TOP_LEVEL_KEY.match(lines[i])
            if match and match.group(1) > "lastUpdated":
                at = i
                break
        lines.insert(at, f"lastUpdated: {date_text}{ending}")
    new = "".join(lines)
    if new == text:
        return False
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    return True


def carry_promotion_dates(base, docs_dir, check=False):
    """Give each page whose content HEAD changes since it left `base` the date of its newest
    authored change, or with check=True only report the pages that lack it (#492).

    Pages come from `git diff` between merge-base(base, HEAD) and HEAD under docs_dir. A page
    whose authored_key is unchanged (a card copy, a rewrap, a date edit) is left alone, as is
    every page the branch does not change. Exit 0 done or nothing to do, 1 (check only) a page
    lacks its date, 2 the branch, the base or a page could not be read."""
    docs = os.path.realpath(docs_dir)
    if not os.path.isdir(docs):
        print(f"❌ Directory not found: {docs}")
        return 2
    rc, top = _git_out(docs, 'rev-parse', '--show-toplevel')
    if rc != 0 or not top.strip():
        print(f"❌ {docs} is not inside a git checkout")
        return 2
    top = os.path.realpath(top.strip())
    rc, merge_base = _git_out(top, 'merge-base', base, 'HEAD')
    merge_base = merge_base.strip()
    if rc != 0 or not merge_base:
        print(f"❌ Could not find where HEAD left {base!r}, so no page was judged")
        return 2
    rc, names = _git_out(top, 'diff', '--name-only', '--no-renames', '-z', merge_base, 'HEAD',
                         '--', os.path.relpath(docs, top))
    if rc != 0:
        print(f"❌ git diff {merge_base[:12]} HEAD failed, so no page was judged")
        return 2
    print(f"📁 Pages this branch changes since {merge_base[:12]}, where it left {base}:")
    lacking, carried, unchanged, no_date, errors = [], 0, 0, [], 0
    for rel in sorted(n for n in names.split('\0') if n.endswith('.mdx')):
        if os.path.basename(rel) == "404.mdx":
            continue
        rc_new, new = _git_out(top, 'show', f'HEAD:{rel}')
        if rc_new != 0:
            continue  # the branch deletes it
        rc_old, old = _git_out(top, 'show', f'{merge_base}:{rel}')
        if rc_old == 0 and authored_key(old) == authored_key(new):
            unchanged += 1
            continue
        path = os.path.join(top, rel)
        date = get_git_last_modified(path, key=authored_key)
        if date is None:
            no_date.append(rel)
            print(f"⚠️  {rel}: no person-authored change found, so its lastUpdated is left as it is")
            continue
        with open(path, 'r', encoding='utf-8', newline='') as f:
            current = last_updated_text(f.read())
        if current == date:
            carried += 1
            print(f"⏭️  {rel}: lastUpdated {date} already")
            continue
        shown = (current or "").strip("'\"")
        if _ISO_DATE.fullmatch(shown) and shown > date:
            # An older staging change shipped after a newer one: its cherry-pick is the newest
            # commit, so the rule gives the older date, but the page already carries the newer
            # change and its date. Never move a date back.
            carried += 1
            print(f"⏭️  {rel}: lastUpdated {shown} is later than the change it carries ({date}), so it stays")
            continue
        lacking.append(rel)
        if check:
            print(f"❌ {rel}: lastUpdated is {current}, but its newest authored change is dated {date}")
            continue
        try:
            set_last_updated(path, date)
        except (OSError, ValueError) as exc:
            errors += 1
            print(f"❌ {rel}: could not write lastUpdated {date}: {exc}")
            continue
        print(f"✅ {rel}: lastUpdated {current} -> {date}")
    print("=" * 60)
    print(f"Pages with an authored change: {len(lacking) + carried + len(no_date)}; "
          f"already dated: {carried}; {'lacking' if check else 'carried now'}: {len(lacking)}; "
          f"no date to give: {len(no_date)}; changed only in cards, layout or date: {unchanged}")
    if errors:
        return 2
    if check and lacking:
        print("To fix, run on the promotion branch and commit the result: "
              f"python scripts/update-last-modified.py --promotion-base {base}")
        return 1
    return 0


def main(argv=None):
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

    parser.add_argument(
        '--promotion-base',
        metavar='REF',
        help='On a promotion branch: give each page it changes since it left REF (such as '
             'origin/main) the date of that change, and no other page (#492)'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='With --promotion-base: report the pages that lack their date and exit 1, writing nothing'
    )
    
    args = parser.parse_args(argv)
    
    if args.self_test:
        return self_test()

    if args.check and not args.promotion_base:
        parser.error('--check needs --promotion-base')

    if args.promotion_base:
        return carry_promotion_dates(args.promotion_base, args.dir, check=args.check)
    
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

    _promotion_self_test(case)

    failed = cases.count(False)
    if failed:
        print(f"SELF-TEST FAILED: {failed} of {len(cases)} case(s).")
        return 1
    print(f"SELF-TEST PASSED: {len(cases)} of {len(cases)} case(s).")
    return 0


def _promotion_self_test(case):
    """Subset promotions (tallyfy/documentation#492), on a scratch repository with a `main` and a
    `staging` branch built the way this repository's are: people's commits, the staging date job
    run for real and committed as the pipeline bot, and the generator's card commits.

    The promotion branch cherry-picks two staging changes, as a subset ship does, then copies
    staging's cards by hand under #500. Against a script that cannot carry dates, every carry
    arm fails. Against a carry that judges commits with the cards included, page a takes the
    card copy's date (2026-11-05). Against one that runs the date job on the whole tree, page d
    moves. The last arms are the full promotion that follows (acceptance criterion 2)."""
    import contextlib
    import io

    person = ("A Person", "person@example.com")
    bot = ("GitHub Action", "action@github.com")
    names = ('a.mdx', 'b.mdx', 'c.mdx', 'd.mdx', 'e.mdx', 'f.mdx')

    def page(page_id, title, last_updated, one, two, card):
        # The form the pipeline's YAML dump writes: sorted keys, no newline at the end, and the
        # generator's CRLF after each card.
        return (f"---\nid: {page_id}\nlastUpdated: {last_updated}\ntitle: {title}\n---\n\n"
                f"{one}\n\n{two}\n\n## Related articles\n<CardGrid>\n"
                f"<LinkTitleCard header=\"<b>X</b>\" href=\"/products/x/\" > {card} </LinkTitleCard>\r\n"
                f"</CardGrid>")

    def last_updated_of(text):
        found = re.search(r"^lastUpdated:[ \t]*(.*?)[ \t]*\r?$", text or "", re.MULTILINE)
        return found.group(1) if found else None

    def cli(*argv):
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = main(list(argv))
        except SystemExit as exc:  # argparse refusing an option it does not know
            rc = exc.code
        except Exception as exc:  # noqa: BLE001 - an exception is a result here
            rc = f"raised {exc!r}"
        return rc, out.getvalue()

    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp, 'docs')
        docs.mkdir()

        def write(name, text):
            Path(docs, name).write_bytes(text.encode('utf-8'))

        def read(name):
            return Path(docs, name).read_bytes().decode('utf-8')

        def show(ref, name):
            done = subprocess.run(['git', 'show', f'{ref}:docs/{name}'], cwd=tmp, capture_output=True)
            return done.stdout.decode('utf-8') if done.returncode == 0 else None

        def commit(message, date, who, *extra):
            _git(tmp, 'add', '-A')
            _git(tmp, 'commit', '-q', *extra, '-m', message, date=date, author=who)
            return _git(tmp, 'rev-parse', 'HEAD').strip()

        def date_job():
            # The staging pipeline's own step: the whole tree, then a bot commit.
            with contextlib.redirect_stdout(io.StringIO()):
                process_directory(str(docs))
            if _git(tmp, 'status', '--porcelain').strip():
                commit("Update lastUpdated dates from Git history", None, bot)

        def cards_job(card, *pages):
            # The generator rewrites each card block and ends each card line in CRLF.
            for name in pages:
                text = read(name)
                block = text.split("## Related articles", 1)[1]
                old_card = re.search(r"> (.*) </LinkTitleCard>", block).group(1)
                write(name, text.split("## Related articles", 1)[0] + "## Related articles" + block
                      .replace(f"> {old_card} </LinkTitleCard>", f"> {card} </LinkTitleCard>")
                      .replace("</LinkTitleCard>\n", "</LinkTitleCard>\r\n"))
            commit("Push related articles", None, bot)

        _git(tmp, 'init', '-q', '-b', 'main')
        write('a.mdx', page('a', 'A', '2026-10-01', 'A says one thing.', 'A second paragraph.', 'Old card.'))
        # b and d are stale on main on purpose (2020-01-01, where their history says 2026-10-01),
        # so a carry that judged every page in the diff would move b, and one that ran the date
        # job on the whole tree would move d. The staging date job does move both.
        write('b.mdx', page('b', 'B', '2020-01-01', 'B body.', 'B more.', 'Old card.'))
        write('c.mdx', page('c', 'C', '2026-10-01', 'C body.', 'C more.', 'Old card.'))
        write('d.mdx', page('d', 'D', '2020-01-01', 'D body.', 'D more.', 'Old card.'))
        write('f.mdx', page('f', 'F', '2026-10-01', 'F says one thing.', 'F second paragraph.', 'Old card.'))
        commit("pages", "2026-10-01T12:00:00+00:00", person)

        _git(tmp, 'checkout', '-q', '-b', 'staging')
        # 20:30 at -06:00 is 2026-11-03 in UTC; the date is the author's own calendar date.
        write('a.mdx', read('a.mdx').replace('A says one thing.', 'A says the right thing.'))
        s1 = commit("Correct page a", "2026-11-02T20:30:00-06:00", person)
        date_job()
        cards_job('New card.', 'a.mdx', 'b.mdx', 'd.mdx')
        write('c.mdx', read('c.mdx').replace('C body.', 'C body, corrected on staging only.'))
        commit("Correct page c", "2026-11-03T10:00:00+00:00", person)
        date_job()
        # A new page with no lastUpdated line yet; the date job gives it one.
        write('e.mdx', "---\nid: e\ntitle: E\n---\n\nE is new.")
        s4 = commit("Add page e", "2026-11-04T09:00:00+00:00", person)
        date_job()
        # Two changes to page f, the older one shipped last (the last arm below).
        write('f.mdx', read('f.mdx').replace('F says one thing.', 'F says the older thing.'))
        f_older = commit("Older change to page f", "2026-10-20T12:00:00+00:00", person)
        write('f.mdx', read('f.mdx').replace('F second paragraph.', 'F second paragraph, newer.'))
        f_newer = commit("Newer change to page f", "2026-11-04T12:00:00+00:00", person)
        date_job()

        # The subset ship: cherry-pick two staging changes onto main, then copy staging's cards
        # for a and b by hand (#500), dated later than either change.
        _git(tmp, 'checkout', '-q', '-b', 'promo', 'main')
        _git(tmp, 'cherry-pick', s1)
        _git(tmp, 'cherry-pick', s4)
        _git(tmp, 'cherry-pick', f_newer)
        for name in ('a.mdx', 'b.mdx'):
            ours, theirs = read(name), show('staging', name)
            write(name, ours.split("## Related articles", 1)[0] + "## Related articles"
                  + theirs.split("## Related articles", 1)[1])
        commit("Copy staging's cards for a and b", "2026-11-05T12:00:00+00:00", person)
        before = {name: read(name) for name in names}

        rc, out = cli('--promotion-base', 'main', '--dir', str(docs), '--check')
        case("492: --check fails a subset promotion whose changed pages lack their dates",
             rc == 1 and 'docs/a.mdx' in out and 'docs/e.mdx' in out, f"exit {rc}")
        case("492: --check writes nothing", {n: read(n) for n in names} == before)
        rc, out = cli('--promotion-base', 'main', '--dir', str(docs))
        after = {name: read(name) for name in names}
        case("492: a changed page gets the date of the change it carries, not of the card copy",
             rc == 0 and last_updated_of(after['a.mdx']) == "2026-11-02",
             f"exit {rc}, lastUpdated {last_updated_of(after['a.mdx'])}")
        case("492: only that page's lastUpdated line changes, CRLF card lines included",
             after['a.mdx'] == before['a.mdx'].replace("lastUpdated: 2026-10-01", "lastUpdated: 2026-11-02", 1)
             and "\r\n" in after['a.mdx'])
        case("492: a new page with no date gets one where the date job puts it, so it equals staging's",
             after['e.mdx'] == show('staging', 'e.mdx'), repr(after['e.mdx'][:60]))
        case("492: a page whose only change is a card copy keeps its date, though it is stale",
             after['b.mdx'] == before['b.mdx'] and last_updated_of(after['b.mdx']) == "2020-01-01",
             f"lastUpdated {last_updated_of(after['b.mdx'])}")
        case("492: a page the promotion does not touch keeps its date, though staging's differs",
             after['d.mdx'] == before['d.mdx'] and last_updated_of(after['d.mdx']) == "2020-01-01"
             and last_updated_of(show('staging', 'd.mdx')) == "2026-10-01",
             f"lastUpdated {last_updated_of(after['d.mdx'])}")
        case("492: a page changed only on staging is not touched", after['c.mdx'] == before['c.mdx'])
        case("492: a page whose newer staging change ships first gets that change's date",
             last_updated_of(after['f.mdx']) == "2026-11-04", f"lastUpdated {last_updated_of(after['f.mdx'])}")
        rc, out = cli('--promotion-base', 'main', '--dir', str(docs), '--check')
        case("492: --check passes once the dates are carried", rc == 0, f"exit {rc}")
        rc, out = cli('--promotion-base', 'main', '--dir', str(docs))
        case("492: carrying again changes nothing", rc == 0 and {n: read(n) for n in names} == after,
             f"exit {rc}")
        rc, out = cli('--promotion-base', 'zq-no-such-branch', '--dir', str(docs), '--check')
        case("492: --check against a base that does not resolve exits 2, never a pass", rc == 2, f"exit {rc}")

        # GitHub's squash merge of the promotion, dated at the merge.
        # --allow-empty so the arms below still run, and fail, against a script that carried nothing.
        commit("Carry the dates", "2026-11-05T12:30:00+00:00", person, '--allow-empty')
        _git(tmp, 'checkout', '-q', 'main')
        _git(tmp, 'merge', '-q', '--squash', 'promo')
        shipped = commit("Promote a and e (squash)", "2026-11-05T13:00:00+00:00", person)

        def full_promotion(source):
            # A true merge, as a full promotion pull request lands (#283, #294), in git's own
            # conflict style whatever this machine's config says.
            return subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c', 'merge.conflictStyle=merge',
                                   'merge', '--no-ff', '-q', '-m', 'Promote staging to main', source],
                                  cwd=tmp, capture_output=True, text=True,
                                  env=dict(os.environ, GIT_AUTHOR_NAME=person[0], GIT_AUTHOR_EMAIL=person[1],
                                           GIT_COMMITTER_NAME=person[0], GIT_COMMITTER_EMAIL=person[1]))

        def abandon_merge():
            # Leaves the scratch repository usable for the next arm whether or not the merge stopped.
            if Path(tmp, '.git', 'MERGE_HEAD').exists():
                _git(tmp, 'merge', '--abort')

        # Acceptance criterion 2: the full promotion still brings staging's dates across.
        _git(tmp, 'checkout', '-q', '-b', 'full', shipped)
        merge = full_promotion('staging')
        case("AC2: the full promotion after a carried subset ship merges with no conflict",
             merge.returncode == 0, (merge.stdout + merge.stderr).strip()[:200])
        dates = {name: (last_updated_of(show('full', name)), last_updated_of(show('staging', name))) for name in names}
        case("AC2: after it every page's lastUpdated is staging's, page c's staging-only change included",
             all(ours == theirs and ours for ours, theirs in dates.values()) and dates['c.mdx'][0] == "2026-11-03",
             str(dates))
        rc, out = cli('--promotion-base', shipped, '--dir', str(docs), '--check')
        case("AC2: --check passes on the full promotion with nothing carried by hand", rc == 0, f"exit {rc}")
        abandon_merge()

        # The cost of carrying: staging edits page a again before the next full promotion. The
        # merge then conflicts on a's lastUpdated line, and on nothing else.
        _git(tmp, 'checkout', '-q', '-b', 'staging2', 'staging')
        write('a.mdx', read('a.mdx').replace('A second paragraph.', 'A second paragraph, edited again.'))
        commit("Edit page a again", "2026-11-07T09:00:00+00:00", person)
        date_job()
        cards_job('New card.', 'a.mdx')
        _git(tmp, 'checkout', '-q', '-b', 'full2', shipped)
        merge = full_promotion('staging2')
        conflicted = _git(tmp, 'diff', '--name-only', '--diff-filter=U').split()
        marked, inside = [], False
        for line in read('a.mdx').splitlines():
            if line.startswith(('<<<<<<<', '>>>>>>>')):
                inside = line.startswith('<<<<<<<')
            elif inside and line != '=======':
                marked.append(line)
        case("cost: a page staging edits again after a carried ship conflicts only on its lastUpdated line",
             merge.returncode == 1 and conflicted == ['docs/a.mdx'] and len(marked) == 2
             and all(line.startswith('lastUpdated:') for line in marked), f"{conflicted} {marked}")
        abandon_merge()

        # A second subset ship brings f's older change after its newer one. The cherry-pick is
        # now f's newest commit, dated 2026-10-20, but the page already carries the newer change.
        _git(tmp, 'checkout', '-q', '-b', 'promo2', shipped)
        _git(tmp, 'cherry-pick', f_older)
        rc, out = cli('--promotion-base', shipped, '--dir', str(docs))
        rc_check, _ = cli('--promotion-base', shipped, '--dir', str(docs), '--check')
        case("492: shipping an older change after a newer one never moves the date back",
             rc == 0 and rc_check == 0 and last_updated_of(read('f.mdx')) == "2026-11-04"
             and 'F says the older thing.' in read('f.mdx'),
             f"exit {rc}, check {rc_check}, lastUpdated {last_updated_of(read('f.mdx'))}")

if __name__ == "__main__":
    exit(main())